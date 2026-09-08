const {_electron}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {saveJson}=require('../src/pipeline.cjs');
(async()=>{
 const folder=await fs.mkdtemp(path.resolve(__dirname,'../test-output/native-records-'));
 const id='11111111-1111-4111-8111-111111111111',jobId='22222222-2222-4222-8222-222222222222',owner='records-test';
 const dir=path.join(folder,'session/tasks',owner,id);
 await saveJson(path.join(dir,'task.json'),{id,jobId,userId:owner,status:'failed',source:{url:'https://v.douyin.com/test'},fileName:'失败链接测试',stage:'链接解析已尝试 3 次，仍未成功。请换一个链接，或导入本地视频。',createdAt:new Date().toISOString()});
 const sentinel=path.join(dir,'kept-report.html');await fs.writeFile(sentinel,'keep');
 const wrapper=path.join(folder,'entry.cjs'),source=path.resolve(__dirname,'../src');
 await fs.writeFile(wrapper,`const {app,dialog}=require('electron');app.setPath('userData',${JSON.stringify(path.join(folder,'session'))});app.setAsDefaultProtocolClient=()=>true;app.on('browser-window-created',(_,win)=>win.hide());global.choice=0;global.dialogs=[];dialog.showMessageBox=async(_,options)=>{global.dialogs.push(options);return {response:global.choice};};
 const {LabClient}=require(${JSON.stringify(path.join(source,'lab-client.cjs'))});LabClient.prototype.initialize=async function(){this.tokens={test:true};};LabClient.prototype.api=async function(route,options){if(options?.method&&options.method!=='GET')throw Error('Unexpected cloud mutation');if(route==='/api/desktop-auth/me')return {user:{id:'records-test',displayName:'测试'}};if(route==='/api/cine-sleuth/jobs')return {jobs:[{jobId:'${jobId}',status:'failed',fileName:'失败链接测试'}],nextCursor:null};if(route==='/api/cine-sleuth/jobs/${jobId}')return {jobId:'${jobId}'};throw Error('Unexpected route');};require(${JSON.stringify(path.join(source,'main.cjs'))});`);
 const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
 const electron=await _electron.launch({executablePath:path.resolve(__dirname,'../node_modules/electron/dist/electron.exe'),args:[wrapper],env});
 try{
  const page=await electron.firstWindow();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const width of [1220,980]){
    await page.setViewportSize({width,height:680});await page.getByRole('button',{name:'移除',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    const boxes=await page.locator('.task-actions button').evaluateAll(buttons=>buttons.map(b=>{const r=b.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom};}));
    for(let a=0;a<boxes.length;a++)for(let b=a+1;b<boxes.length;b++)assert.ok(boxes[a].right<=boxes[b].x||boxes[b].right<=boxes[a].x||boxes[a].bottom<=boxes[b].y||boxes[b].bottom<=boxes[a].y);
    await page.screenshot({path:path.join(folder,`records-${width}.png`),fullPage:true});
  }
  await page.getByRole('button',{name:'移除',exact:true}).click();assert.equal(await page.locator('#tasks .task-row').count(),1);
  await electron.evaluate(()=>{global.choice=1;});await page.getByRole('button',{name:'移除',exact:true}).click();
  await page.getByText('已从本机列表移除，云端历史和文件已保留',{exact:true}).waitFor();
  assert.equal(await page.locator('#tasks .task-row').count(),0);
  await page.locator('#nav-history').click();await page.getByText('本机列表暂无可显示的历史。',{exact:true}).waitFor();
  await page.reload();assert.equal(await page.locator('#tasks .task-row').count(),0);
  assert.equal(await fs.readFile(sentinel,'utf8'),'keep');assert.equal(JSON.parse(await fs.readFile(path.join(dir,'task.json'),'utf8')).status,'failed');
  const dialogs=await electron.evaluate(()=>global.dialogs);assert.equal(dialogs.length,2);assert.equal(dialogs[0].defaultId,0);assert.match(dialogs[0].detail,/云端历史/);assert.deepEqual(errors,[]);
  console.log('PASS native local-only remove: cancel/confirm, persistence, cloud-list filter, files retained, 1220/980 layout; no cloud writes');
 }finally{await electron.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
