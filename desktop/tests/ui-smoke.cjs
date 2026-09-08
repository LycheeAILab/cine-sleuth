// CINE_PLAYWRIGHT can point at an existing Playwright install.
const {chromium}=require(process.env.CINE_PLAYWRIGHT||'playwright');const assert=require('node:assert/strict');const path=require('node:path');const fs=require('node:fs/promises');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{for(const width of [1220,980]){
  const page=await browser.newPage({viewport:{width,height:840}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   let listener;const state={user:null,tasks:[],running:null};
   window.testUpdate=value=>listener({type:'update',state:{currentVersion:'2.0.0',...value}});
   window.cine={updateState:async()=>({status:'idle',currentVersion:'2.0.0'}),updateCheck:async()=>({status:'ready',currentVersion:'2.0.0',version:'2.0.1'}),updateInstall:async()=>{},onEvent:fn=>{listener=fn;},state:async()=>structuredClone(state),login:async()=>{state.user={id:'test',displayName:'测试用户'};listener({type:'auth',user:state.user});return '已登录';},logout:async()=>{state.user=null;state.tasks=[];},devices:async()=>{},select:async()=>({name:'测试视频.mp4',sizeBytes:100000}),start:async()=>{
    const task={id:'11111111-1111-4111-8111-111111111111',jobId:'22222222-2222-4222-8222-222222222222',fileName:'测试视频.mp4',status:'completed',stage:'模型分析完成',total:1,completed:1};state.tasks=[task];listener({type:'task',task});listener({type:'idle'});return task;
   },pause:async()=>{},resume:async()=>{},history:async()=>({jobs:state.tasks,nextCursor:null}),modelStatus:async()=>({configured:true,model:'test/model'}),modelSave:async()=>({configured:true,model:'test/model'}),modelClear:async()=>{},modelList:async()=>['test/model'],summaryRead:async()=>null,summarize:async()=>({text:'测试总结',model:'test/model',createdAt:new Date().toISOString()}),results:async()=>({status:'completed',chunks:[{chunkKey:'chunk-001',status:'completed',result:{media_fingerprint:{media_visible:true,visual_medium:'实拍',visible_subjects:['测试画面']},transcript:[{text:'<img src=x onerror=alert(1)>',time:'00:01'}]}}]}),export:async()=> '已导出'};
  });
  await page.goto('file:///'+path.resolve(__dirname,'../src/index.html').replaceAll('\\','/'));
  assert.equal(await page.locator('#start').isDisabled(),true);
  await page.screenshot({path:path.resolve(__dirname,`../test-output/desktop-${width}.png`),fullPage:true});
  await page.locator('#login').click();await page.locator('#select').click();await page.locator('#consent').check();assert.equal(await page.locator('#start').isEnabled(),true);
  await page.locator('#tab-link').click();assert.equal(await page.locator('#start').isDisabled(),true);await page.locator('#url').fill('https://v.douyin.com/example');assert.equal(await page.locator('#start').isEnabled(),true);
  await page.locator('#tab-local').click();await page.locator('#start').click();await page.getByRole('button',{name:'查看结果'}).click();await page.getByText('模型分析结果',{exact:true}).waitFor();assert.equal(await page.locator('#result img').count(),0);
  await page.screenshot({path:path.resolve(__dirname,`../test-output/results-${width}.png`),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.locator('#summarize').click();await page.locator('#summary').filter({hasText:'测试总结'}).waitFor();await page.locator('#nav-settings').click();await page.locator('#model-id').fill('test/model');await page.locator('#save-settings').click();await page.screenshot({path:path.resolve(__dirname,`../test-output/settings-${width}.png`),fullPage:true});assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).userSelect),'none');await page.locator('#nav-updates').click();await page.locator('#check-update').click();await page.locator('#install-update').waitFor();await page.screenshot({path:path.resolve(__dirname,`../test-output/updates-${width}.png`),fullPage:true});assert.deepEqual(errors,[]);await page.close();
 }}finally{await browser.close();}
 console.log('Renderer UI: 1220/980px, login, local/link selection, consent gating, results, and untrusted text rendering passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
