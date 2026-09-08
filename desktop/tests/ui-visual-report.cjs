const {chromium}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});
try{for(const width of [1220,980]){
 const page=await browser.newPage({viewport:{width,height:680}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  let listener,saved=null,count=0;
  window.reportCalls=[];
  window.cine={onEvent:fn=>listener=fn,state:async()=>({user:{displayName:'测试账号'},tasks:[{id:'local',jobId:'job',fileName:'测试原片.mp4',status:'completed'}]}),updateState:async()=>({status:'disabled',currentVersion:'dev'}),results:async()=>({status:'completed',chunks:[]}),summaryRead:async()=>null,
   reportRead:async()=>saved,reportGenerate:async id=>{count++;window.reportCalls.push('generate');listener({type:'report-progress',id,message:'正在提取首帧…'});await new Promise(r=>setTimeout(r,150));if(count===1)throw Error('原视频已移动，请重新选择原片');saved={title:'离线图文报告',segments:3,model:'测试模型'};return saved;},reportOpen:async()=>{window.reportCalls.push('open');return '已打开';},reportExport:async()=>{window.reportCalls.push('export');return '已导出';}};
 });
 await page.goto('file:///'+path.resolve(__dirname,'../src/index.html').replaceAll('\\','/'));
 await page.getByRole('button',{name:'查看结果'}).click();
 await page.locator('#generate-report').click();await page.locator('#report-status').filter({hasText:'原视频已移动'}).waitFor();
 assert.equal(await page.locator('#generate-report').isEnabled(),true);
 await page.locator('#generate-report').click();await page.locator('#open-report').waitFor();
 assert.equal(await page.locator('#generate-report').isVisible(),false);
 await page.locator('#open-report').click();await page.locator('#export-report').click();
 assert.deepEqual(await page.evaluate(()=>window.reportCalls),['generate','generate','open','export']);
 await page.screenshot({path:path.resolve(__dirname,`../test-output/html-controls-${width}.png`),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
 await page.locator('#back').click();await page.getByRole('button',{name:'查看结果'}).click();await page.locator('#open-report').waitFor();await page.close();
}}finally{await browser.close();}console.log('PASS: report controls, progress, error/retry, saved history, open/export and 1220/980 geometry');
})().catch(e=>{console.error(e);process.exitCode=1;});
