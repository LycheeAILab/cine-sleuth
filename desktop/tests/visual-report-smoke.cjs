// Real bundled media worker + offline browser; no cloud/model requests.
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {hashFile,saveJson,prepareMedia}=require('../src/pipeline.cjs');
const {reportMarkdown}=require('../src/visual-report.cjs');
const {chromium}=require(process.env.CINE_PLAYWRIGHT||'playwright');
function run(command,args){return new Promise((resolve,reject)=>{const child=spawn(command,args,{windowsHide:true,stdio:['ignore','ignore','pipe']});let error='';child.stderr.on('data',d=>error+=d);child.on('error',reject);child.on('close',code=>code?reject(Error(error)):resolve());});}
(async()=>{
 const root=await fs.mkdtemp(path.resolve(__dirname,'../test-output/html-')),runtime=path.resolve(__dirname,'../runtime');
 const video=path.join(root,'中文原片.mp4');
 await run(path.join(runtime,'ffmpeg.exe'),['-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-t','4','-c:v','libx264',video]);
 const segments=[{id:'seg-1',title:'第一镜',start_seconds:0,end_seconds:2,analysis:'观察到彩色测试图。<script>window.injected=true</script>',video_generation_prompt:'彩色图形，固定镜头。'},{id:'seg-2',title:'第二镜',start_seconds:2.02,end_seconds:4,analysis:'动态图形变化。',video_generation_prompt:'彩色动态图形持续变化。'}];
 await saveJson(path.join(root,'segments.json'),{source_sha256:await hashFile(video),segments});
 await fs.writeFile(path.join(root,'input.md'),reportMarkdown({title:'镜探 · 图文拉片报告',overview:'本地测试视频，用于验证首帧和离线阅读。',sections:[{title:'画面与节奏',body:'两段时间范围。'}],segments,uncertainties:'测试素材，不作剧情推断。'},{source:{duration_seconds:4},transcript:[]}));
 const outputDir=path.join(root,'output');
 await prepareMedia(path.join(runtime,'cine-media/cine-media.exe'),{action:'visual-report',video,segments:path.join(root,'segments.json'),report:path.join(root,'input.md'),outputDir},runtime,new AbortController().signal);
 const frames=JSON.parse(await fs.readFile(path.join(outputDir,'frames.json'),'utf8'));
 assert.equal(frames.segments.length,2);assert.equal(frames.segments[0].frame_index,0);assert.equal(frames.segments[1].frame_index,49);assert.ok(Math.abs(frames.segments[1].frame_seconds-49/24)<0.001);
 const standalone=path.join(root,'离线报告.html');await fs.copyFile(path.join(outputDir,'report.html'),standalone);
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{for(const width of [1220,980,390]){
  const page=await browser.newPage({viewport:{width,height:840}});const network=[];page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
  await page.goto(pathToFileURL(standalone).href);await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
  assert.equal(await page.locator('img').count(),2);assert.equal(await page.locator('script').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(network,[]);
  await page.screenshot({path:path.join(root,`report-${width}.png`),fullPage:true});await page.close();
 }}finally{await browser.close();}
 console.log('PASS: bundled worker, Chinese paths, exact first-frame indices, embedded offline images, XSS and 1220/980/390 layout. Demo: '+standalone);
})().catch(error=>{console.error(error);process.exitCode=1;});
