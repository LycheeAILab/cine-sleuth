const {app,BrowserWindow,ipcMain,dialog,shell,safeStorage} = require('electron');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const {pathToFileURL} = require('node:url');
const {LabClient} = require('./lab-client.cjs');
const {SCHEME,labOrigin,beginLogin,acceptCallback} = require('./auth.cjs');
const {AnalysisPipeline} = require('./pipeline.cjs');
const base=labOrigin(process.env.CINESLEUTH_LAB_URL,app.isPackaged);
const page=pathToFileURL(path.join(__dirname,'index.html')).href;
let win,client,engine,pending,user,authenticating=false,selectedVideo=null;
const notify=payload=>{if(win&&!win.isDestroyed())win.webContents.send('cine:event',payload);};
async function handleCallback(value) {
  try {
    if(!client||engine?.running||authenticating)throw Error('请先结束当前操作，再重新登录');
    const input=acceptCallback(value,pending);pending=null;authenticating=true;
    await client.exchange(input);user=(await client.api('/api/desktop-auth/me')).user;
    selectedVideo=null;notify({type:'auth',user});
    if(win.isMinimized())win.restore();win.show();win.focus();
  }catch(error){notify({type:'error',message:error.message});}
  finally{authenticating=false;}
}
if(!app.requestSingleInstanceLock())app.quit();
else {
  app.on('second-instance',(_,argv)=>{
    const value=argv.find(arg=>arg.startsWith(`${SCHEME}:`));if(value)void handleCallback(value);
    if(win){if(win.isMinimized())win.restore();win.show();win.focus();}
  });
  app.on('open-url',(event,url)=>{event.preventDefault();void handleCallback(url);});
  app.whenReady().then(async()=>{
    const root=app.getPath('userData');await fs.mkdir(root,{recursive:true});
    const tokenFile=path.join(root,'desktop-session.enc');
    const storage={
      async read(){try{
        if(!safeStorage.isEncryptionAvailable())return null;
        const value=JSON.parse(safeStorage.decryptString(await fs.readFile(tokenFile)));
        return value.origin===base?value.tokens:null;
      }catch{return null;}},
      async write(tokens){
        if(!safeStorage.isEncryptionAvailable())throw Error('Windows 安全存储不可用，无法保存登录');
        await fs.writeFile(tokenFile+'.tmp',safeStorage.encryptString(JSON.stringify({origin:base,tokens})));await fs.rename(tokenFile+'.tmp',tokenFile);
      },
      async clear(){await fs.rm(tokenFile,{force:true});}
    };
    client=new LabClient(base,storage);await client.initialize();
    const runtime=app.isPackaged?path.join(process.resourcesPath,'runtime'):path.resolve(__dirname,'../runtime');
    engine=new AnalysisPipeline({client,root:path.join(root,'tasks'),runtime,
      promptFile:app.isPackaged?path.join(process.resourcesPath,'segment-prompt.md'):path.resolve(__dirname,'../../plugins/cine-sleuth/skills/cine-sleuth/references/multimodal-segment-prompt.md'),notify});
    if(app.isPackaged)app.setAsDefaultProtocolClient(SCHEME);
    else app.setAsDefaultProtocolClient(SCHEME,process.execPath,[path.resolve(__dirname,'..')]);
    async function currentUser(){user=(await client.api('/api/desktop-auth/me')).user;return user;}
    function idle(){if(engine.running||authenticating)throw Error('请先暂停当前任务，再操作登录');}
    function handle(name,fn){ipcMain.handle('cine:'+name,async(event,...args)=>{
      if(event.sender!==win.webContents||event.senderFrame?.url!==page)throw Error('请求来源无效');
      try{return {ok:true,value:await fn(...args)};}catch(error){return {ok:false,message:error.message};}
    });}
    handle('state',async()=>{
      let authError=null;
      if(client.tokens){try{await currentUser();}catch(error){authError=error.message;if(error.status===401)user=null;}}
      else user=null;
      return {user,authError,base,running:engine.running?.task.id||null,tasks:user?await engine.tasks(user.id):[]};
    });
    handle('login',async()=>{idle();pending=beginLogin(base,os.hostname());await shell.openExternal(pending.url);return '请在浏览器完成 Lab 授权';});
    handle('logout',async()=>{idle();await client.logout();user=null;pending=null;selectedVideo=null;});
    handle('devices',()=>shell.openExternal(base+'/desktop-devices'));
    handle('select',async()=>{
      const result=await dialog.showOpenDialog(win,{title:'选择视频',properties:['openFile'],filters:[{name:'视频',extensions:['mp4','mov','webm','mkv','m4v']}]});
      if(result.canceled)return null;selectedVideo=result.filePaths[0];
      return {name:path.basename(selectedVideo),sizeBytes:(await fs.stat(selectedVideo)).size};
    });
    handle('start',async(input)=>{
      if(!input||input.consent!==true)throw Error('请确认片源授权及云端上传');
      if(input.mode==='local'&&!selectedVideo)throw Error('请先选择视频');
      if(!['local','link'].includes(input.mode))throw Error('导入方式无效');
      const source=input.mode==='local'?{video:selectedVideo}:{url:String(input.url||'').trim()};
      if(source.url!==undefined&&(!source.url||source.url.length>4000))throw Error('请输入有效分享链接');
      return engine.start(await currentUser(),source);
    });
    handle('resume',async(id)=>engine.resume(await currentUser(),id));
    handle('pause',()=>engine.pause());
    handle('history',async(before)=>{
      await currentUser();if(before&&!/^[a-f0-9-]{36}$/.test(before))throw Error('分页参数无效');
      return client.api('/api/cine-sleuth/jobs'+(before?'?before='+encodeURIComponent(before):''));
    });
    async function results(id){await currentUser();if(!/^[a-f0-9-]{36}$/.test(id))throw Error('任务编号无效');return client.api(`/api/cine-sleuth/jobs/${id}/model-results`);}
    handle('results',results);
    handle('export',async(id)=>{
      const value=await results(id);
      const choice=await dialog.showSaveDialog(win,{title:'导出模型原始结果',defaultPath:`CineSleuth-${id}.json`,filters:[{name:'JSON 模型结果',extensions:['json']}]});
      if(!choice.canceled){await fs.writeFile(choice.filePath,JSON.stringify(value,null,2));return '模型结果已导出';}
      return '已取消导出';
    });
    win=new BrowserWindow({width:1220,height:840,minWidth:980,minHeight:680,backgroundColor:'#111416',title:'镜探 · CineSleuth',
      webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
    win.removeMenu();win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    win.webContents.on('will-navigate',(event,url)=>{if(url!==page)event.preventDefault();});
    win.webContents.session.setPermissionRequestHandler((_,__,callback)=>callback(false));
    let closing=false;
    win.on('close',event=>{
      if(!engine.running||closing)return;
      event.preventDefault();
      void dialog.showMessageBox(win,{type:'question',message:'任务正在处理中',detail:'退出将暂停本地流程。已提交到 Lab 的模型分析可能继续完成，可稍后恢复。',buttons:['继续处理','暂停并退出'],defaultId:0,cancelId:0})
        .then(async choice=>{if(choice.response===1){await engine.pause();closing=true;win.close();}});
    });
    await win.loadFile(path.join(__dirname,'index.html'));
    const callback=process.argv.find(arg=>arg.startsWith(`${SCHEME}:`));if(callback)void handleCallback(callback);
  }).catch(error=>{dialog.showErrorBox('镜探启动失败',error.message);app.quit();});
}
app.on('window-all-closed',()=>app.quit());
