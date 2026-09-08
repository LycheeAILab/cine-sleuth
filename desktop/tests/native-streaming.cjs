// Actual Electron + HTTP streaming transport. Only synthetic evidence, no real key or cloud call.
const {_electron}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {saveJson}=require('../src/pipeline.cjs');
(async()=>{
 const folder=await fs.mkdtemp(path.resolve(__dirname,'../test-output/native-stream-'));
 const id='11111111-1111-4111-8111-111111111111',owner='stream-test',session=path.join(folder,'session');
 await saveJson(path.join(session,'tasks',owner,id,'task.json'),{id,jobId:id,userId:owner,status:'completed',fileName:'流式测试.mp4',createdAt:new Date().toISOString()});
 const source=path.resolve(__dirname,'../src'),wrapper=path.join(folder,'entry.cjs');
 const waitMs=process.env.CINE_LONG_WAIT==='1'?185000:300;
 await fs.writeFile(wrapper,`const {app}=require('electron'),http=require('node:http');app.setPath('userData',${JSON.stringify(session)});app.setAsDefaultProtocolClient=()=>true;app.on('browser-window-created',(_,win)=>win.hide());
 const {LabClient}=require(${JSON.stringify(path.join(source,'lab-client.cjs'))});LabClient.prototype.initialize=async function(){this.tokens={test:true};};LabClient.prototype.api=async function(route){if(route==='/api/desktop-auth/me')return {user:{id:'${owner}',displayName:'测试用户'}};if(route.endsWith('/model-results'))return {status:'completed',chunks:[{status:'completed',result:{shots:[]}}]};throw Error('Unexpected cloud request');};
 const {ModelSettings}=require(${JSON.stringify(path.join(source,'model-settings.cjs'))});ModelSettings.prototype.read=async()=>({key:'fixture-key',model:'测试流式模型'});
 const {streamCompletion}=require(${JSON.stringify(path.join(source,'stream-completion.cjs'))});
 const originalCall=ModelSettings.prototype.call;
 global.requests=0;
 const packet=(delta,finish_reason=null)=>'data: '+JSON.stringify({choices:[{delta,finish_reason}]})+'\\n\\n';
 const server=http.createServer((req,res)=>{global.requests++;req.resume();
  const timer=setTimeout(()=>{res.writeHead(200,{'Content-Type':'text/event-stream'});res.write(packet({reasoning_content:'正在核对测试证据 <img src=x onerror=alert(1)>'}));
   setTimeout(()=>{if(res.destroyed)return;res.write(packet({content:'# 已完成的测试总结\\n\\n这是合成测试证据。'}));},500);
   if(global.requests===1)setTimeout(()=>{if(!res.destroyed)res.end(packet({},'stop')+'data: [DONE]\\n\\n');},1700);
  },global.requests===1?${waitMs}:10);res.on('close',()=>clearTimeout(timer));
 });server.listen(0,'127.0.0.1',()=>{
  ModelSettings.prototype.call=function(config,endpoint,body,options){if(!body)return originalCall.call(this,config,endpoint,body,options);return streamCompletion(config,body,options,(_,args,cb)=>http.request('http://127.0.0.1:'+server.address().port,args,cb));};
  require(${JSON.stringify(path.join(source,'main.cjs'))});
 });`);
 const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
 const electron=await _electron.launch({executablePath:path.resolve(__dirname,'../node_modules/electron/dist/electron.exe'),args:[wrapper],env});
 try{
  const page=await electron.firstWindow(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#summarize').click();
  await page.locator('#generation-activity[data-status="running"]').waitFor();
  assert.equal(await page.locator('#logout').isEnabled(),false);assert.equal(await page.locator('#generate-report').isEnabled(),false);
  const reject=await page.evaluate(()=>window.cine.summarize('11111111-1111-4111-8111-111111111111').catch(e=>e.message));assert.match(reject,/完成或暂停/);
  if(waitMs>180000){
   console.log('Long-wait regression: actual model response headers delayed 185 seconds; checking there is no 180-second cutoff.');
   await page.locator('#generation-wait').filter({hasText:'没有新数据'}).waitFor({timeout:70000});
   await page.reload();await page.locator('#generation-activity[data-status="running"]').waitFor();
   console.log('Activity restored after renderer reload; still waiting on the same request.');
  }
  await page.locator('#generation-activity[data-status="completed"]').waitFor({timeout:waitMs+15000});
  assert.equal(await electron.evaluate(()=>global.requests),1);
  assert.equal(JSON.parse(await fs.readFile(path.join(session,'summaries',owner,id+'.json'),'utf8')).text.includes('测试总结'),true);
  // Reload recovers the saved summary, even if the original renderer was replaced.
  await page.reload();await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#summary').filter({hasText:'测试总结'}).waitFor();
  await page.locator('#summarize').click();await page.locator('#generation-message').filter({hasText:'正在接收正文'}).waitFor();
  for(const width of [1220,980]){
   await page.setViewportSize({width,height:840});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:path.join(folder,'streaming-'+width+'.png'),fullPage:true});
  }
  await page.locator('#generation-reasoning-panel summary').click();assert.ok((await page.locator('#generation-reasoning').textContent()).includes('正在核对测试证据'));assert.equal(await page.locator('#generation-reasoning img').count(),0);await page.locator('#generation-counts').filter({hasText:'推理'}).waitFor();
  await page.locator('#nav-settings').click();assert.equal(await page.locator('#generation-activity').isVisible(),true);assert.equal(await page.locator('#save-settings').isEnabled(),false);
  await page.locator('#generation-stop').click();await page.locator('#generation-activity[data-status="cancelled"]').waitFor();
  assert.equal(await electron.evaluate(()=>global.requests),2);assert.equal(await page.locator('#logout').isEnabled(),true);
  assert.equal(JSON.parse(await fs.readFile(path.join(session,'summaries',owner,id+'.json'),'utf8')).text.includes('测试总结'),true);
  assert.deepEqual(errors,[]);console.log('PASS: Electron streaming, '+waitMs+'ms wait, owner busy guard, persistence, activity across views/reload, cancellation, prior result preserved, 1220/980 layout. Screenshots: '+folder);
 }finally{await electron.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
