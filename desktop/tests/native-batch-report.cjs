// Real Electron IPC and packaged media, with fake identity/model evidence only.
const {_electron}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {hashFile,saveJson}=require('../src/pipeline.cjs');
(async()=>{
 const folder=await fs.mkdtemp(path.resolve(__dirname,'../test-output/native-batch-report-'));
 const video=path.resolve(__dirname,'../test-output/media/示例视频.mp4'),id='11111111-1111-4111-8111-111111111111',owner='native-test';
 const dir=path.join(folder,'session/tasks',owner,id);
 await saveJson(path.join(dir,'task.json'),{id,userId:owner,jobId:id,status:'completed',fileName:'原生报告测试.mp4',createdAt:new Date().toISOString()});
 await saveJson(path.join(dir,'manifest.json'),{source:{path:video,duration_seconds:4,sha256:await hashFile(video)},chunks:[{chunk_id:'a',source_start_seconds:0,duration_seconds:4}]});
 const wrapper=path.join(folder,'entry.cjs'),source=path.resolve(__dirname,'../src');
 await fs.writeFile(wrapper,`const {app,shell,dialog}=require('electron');app.setPath('userData',${JSON.stringify(path.join(folder,'session'))});app.setAsDefaultProtocolClient=()=>true;shell.openPath=async file=>{global.opened=file;return '';};dialog.showSaveDialog=async()=>({filePath:${JSON.stringify(path.join(folder,'export.html'))}});app.on('browser-window-created',(_,win)=>win.hide());
 const {LabClient}=require(${JSON.stringify(path.join(source,'lab-client.cjs'))});LabClient.prototype.initialize=async function(){this.tokens={test:true};};LabClient.prototype.api=async function(route,options){if(options?.method==='POST')throw Error('Unexpected cloud mutation');if(route==='/api/desktop-auth/me')return {user:{id:'native-test',displayName:'测试用户'}};if(route.endsWith('/model-results'))return {status:'completed',chunks:[{chunkKey:'a',status:'completed',result:{media_fingerprint:{media_visible:true},shots:Array.from({length:12},(_,i)=>({start:i/3,end:(i+1)/3,visuals:'测试图'}))}}]};throw Error('Unexpected route');};
 const {ModelSettings}=require(${JSON.stringify(path.join(source,'model-settings.cjs'))});ModelSettings.prototype.read=async()=>({key:'fixture',model:'test'});global.modelCalls=0;
 ModelSettings.prototype.call=async(_,__,body,options)=>{global.modelCalls++;const input=JSON.parse(body.messages[1].content);if(global.modelCalls===2)throw Error('测试网络中断');options.onProgress?.({phase:'writing',outputChars:100,reasoningChars:0,lastActivityAt:Date.now()});const report=input.shots?{title:'原生分批报告',overview:'本地测试',sections:[],segments:input.shots.map(s=>({title:'测试图',evidence_ids:[s.evidence_id],analysis:'测试图',video_generation_prompt:'彩色测试图'})),uncertainties:'测试数据'}:{title:'全片概览',overview:'十二个测试镜头',sections:[],uncertainties:'测试数据'};return {choices:[{message:{content:JSON.stringify(report)},finish_reason:'stop'}]};};
 require(${JSON.stringify(path.join(source,'main.cjs'))});`);
 const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
 const electron=await _electron.launch({executablePath:path.resolve(__dirname,'../node_modules/electron/dist/electron.exe'),args:[wrapper],env});
 try{
  const page=await electron.firstWindow();await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#generate-report').click();await page.locator('#generation-activity[data-status="failed"]').waitFor();assert.match(await page.locator('#generation-message').textContent(),/测试网络中断/);assert.equal(await electron.evaluate(()=>global.modelCalls),2);const checkpoint=JSON.parse(await fs.readFile(path.join(folder,'session/reports/native-test',id,'batches.json'),'utf8'));assert.equal(Object.keys(checkpoint.completed).length,1);await page.reload();await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#generate-report').click();await page.locator('#open-report').waitFor({timeout:60000});assert.equal(await electron.evaluate(()=>global.modelCalls),4);
  await page.locator('#open-report').click();await page.locator('#export-report').click();await page.getByText('HTML 已导出，图片已内嵌，可离线打开',{exact:true}).waitFor();
  assert.match(await fs.readFile(path.join(folder,'export.html'),'utf8'),/data:image\/jpeg;base64,/);const draft=JSON.parse(await fs.readFile(path.join(folder,'session/reports/native-test',id,'draft.json'),'utf8'));assert.equal(draft.report.segments.length,12);
  const opened=await electron.evaluate(()=>global.opened);assert.ok(opened.startsWith(path.join(folder,'session/reports/native-test')));
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  console.log('PASS: real Electron batching → disk checkpoint → failed second request → reload/resume only remainder → 12 frames → exported HTML; no real paid calls');
 }finally{await electron.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
