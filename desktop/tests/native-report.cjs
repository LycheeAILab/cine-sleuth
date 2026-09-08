// Real Electron IPC and packaged media, with fake identity/model evidence only.
const {_electron}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {hashFile,saveJson}=require('../src/pipeline.cjs');
(async()=>{
 const folder=await fs.mkdtemp(path.resolve(__dirname,'../test-output/native-report-'));
 const video=path.resolve(__dirname,'../test-output/media/示例视频.mp4'),id='11111111-1111-4111-8111-111111111111',owner='native-test';
 const dir=path.join(folder,'session/tasks',owner,id);
 await saveJson(path.join(dir,'task.json'),{id,userId:owner,jobId:id,status:'completed',fileName:'原生报告测试.mp4',createdAt:new Date().toISOString()});
 await saveJson(path.join(dir,'manifest.json'),{source:{path:video,duration_seconds:4,sha256:await hashFile(video)},chunks:[{chunk_id:'a',source_start_seconds:0,duration_seconds:4}]});
 const wrapper=path.join(folder,'entry.cjs'),source=path.resolve(__dirname,'../src');
 await fs.writeFile(wrapper,`const {app,shell,dialog}=require('electron');app.setPath('userData',${JSON.stringify(path.join(folder,'session'))});app.setAsDefaultProtocolClient=()=>true;shell.openPath=async file=>{global.opened=file;return '';};dialog.showSaveDialog=async()=>({filePath:${JSON.stringify(path.join(folder,'export.html'))}});app.on('browser-window-created',(_,win)=>win.hide());
 const {LabClient}=require(${JSON.stringify(path.join(source,'lab-client.cjs'))});LabClient.prototype.initialize=async function(){this.tokens={test:true};};LabClient.prototype.api=async function(route,options){if(options?.method==='POST')throw Error('Unexpected cloud mutation');if(route==='/api/desktop-auth/me')return {user:{id:'native-test',displayName:'测试用户'}};if(route.endsWith('/model-results'))return {status:'completed',chunks:[{chunkKey:'a',status:'completed',result:{media_fingerprint:{media_visible:true},shots:[{start:0,end:4,visuals:'测试图'}]}}]};throw Error('Unexpected route');};
 const {ModelSettings}=require(${JSON.stringify(path.join(source,'model-settings.cjs'))});ModelSettings.prototype.visualReport=async()=>({model:'test',createdAt:new Date().toISOString(),report:{title:'原生测试报告',overview:'本地测试',sections:[],segments:[{id:'seg-1',title:'测试图',start_seconds:0,end_seconds:4,analysis:'测试图',video_generation_prompt:'彩色测试图'}],uncertainties:'测试数据'}});
 require(${JSON.stringify(path.join(source,'main.cjs'))});`);
 const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
 const electron=await _electron.launch({executablePath:path.resolve(__dirname,'../node_modules/electron/dist/electron.exe'),args:[wrapper],env});
 try{
  const page=await electron.firstWindow();await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#generate-report').click();await page.locator('#open-report').waitFor({timeout:60000});
  await page.locator('#open-report').click();await page.locator('#export-report').click();await page.getByText('HTML 已导出，图片已内嵌，可离线打开',{exact:true}).waitFor();
  assert.match(await fs.readFile(path.join(folder,'export.html'),'utf8'),/data:image\/jpeg;base64,/);
  const opened=await electron.evaluate(()=>global.opened);assert.ok(opened.startsWith(path.join(folder,'session/reports/native-test')));
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  console.log('PASS: real isolated Electron IPC → source verification → frame worker → saved/open/export HTML, no real cloud/model mutations');
 }finally{await electron.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
