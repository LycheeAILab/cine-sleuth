const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {assemble,validateReport,reportMarkdown,VisualReports}=require('../src/visual-report.cjs');
const {hashFile,saveJson}=require('../src/pipeline.cjs');
const {ModelSettings}=require('../src/model-settings.cjs');
const id='11111111-1111-4111-8111-111111111111';
function fixture(){
 const manifest={source:{duration_seconds:4},chunks:[{chunk_id:'a',source_start_seconds:0,duration_seconds:3},{chunk_id:'b',source_start_seconds:2,duration_seconds:2}]};
 const data={status:'completed',chunks:[{chunkKey:'a',status:'completed',result:{media_fingerprint:{media_visible:true},shots:[{start:'00:00.000',end:'00:02.000',visuals:'红色'},{start:2,end:3,visuals:'蓝色'}]}},{chunkKey:'b',status:'completed',result:{candidates:[{content:{parts:[{text:JSON.stringify({media_fingerprint:{media_visible:true},shots:[{start:0,end:2,visuals:'蓝色'}]})}]}}]}}]};
 const report={title:'测试报告',overview:'全片总结',sections:[{title:'声音设计',body:'无声'}],segments:[{title:'红色',evidence_ids:['shot-1'],analysis:'红色画面',video_generation_prompt:'红色画面，固定镜头'},{title:'蓝色',evidence_ids:['shot-2','shot-3'],analysis:'蓝色连续镜头',video_generation_prompt:'蓝色画面，固定镜头'}],uncertainties:'无身份推断'};
 return {manifest,data,report};
}
test('global timeline uses manifest offsets; merged segments reference every shot exactly once',()=>{
 const {manifest,data,report}=fixture(),evidence=assemble(data,manifest),value=validateReport(JSON.stringify(report),evidence);
 assert.equal(evidence.shots[2].start_seconds,2);assert.equal(value.segments[1].end_seconds,4);
 assert.match(reportMarkdown(value,evidence),/\{\{frame:seg-2\}\}/);
 report.segments.pop();assert.throws(()=>validateReport(JSON.stringify(report),evidence),/遗漏/);
 data.chunks[0].result.shots[0].end='bad';assert.throws(()=>assemble(data,manifest),/时间码/);
});
test('invalid visibility, duplicate evidence, injected markers and incomplete analysis are refused',()=>{
 const {manifest,data,report}=fixture(),evidence=assemble(data,manifest);
 report.segments[1].evidence_ids.push('shot-1');assert.throws(()=>validateReport(JSON.stringify(report),evidence),/重复/);
 report.segments[1].evidence_ids.pop();report.title='{{frame:bad}}';assert.throws(()=>validateReport(JSON.stringify(report),evidence),/格式/);
 data.chunks[0].result.media_fingerprint.media_visible=false;assert.throws(()=>assemble(data,manifest),/看见/);
 data.status='processing';assert.throws(()=>assemble(data,manifest),/完成/);
});
test('report worker retry reuses model draft, preserves account boundaries and checks original hash',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-report-test-'));
 try{
  const {manifest,data,report}=fixture();const video=path.join(root,'source.mp4');await fs.writeFile(video,'fixture');
  manifest.source.path=video;manifest.source.sha256=await hashFile(video);
  await saveJson(path.join(root,'tasks','owner',id,'manifest.json'),manifest);
  let calls=0,works=0;
  const engine={root:path.join(root,'tasks'),tasks:async owner=>owner==='owner'?[{id,userId:owner,jobId:id}]:[]};
  const models={visualReport:async()=>{calls++;return {report:validateReport(JSON.stringify(report),assemble(data,manifest)),model:'test',createdAt:new Date().toISOString()};}};
  const reports=new VisualReports({root:path.join(root,'reports'),engine,models,runtime:root,notify:()=>{},chooseVideo:async()=>video,prepare:async(_,request)=>{works++;if(works===1)throw Error('frame failure');await fs.mkdir(request.outputDir);await fs.writeFile(path.join(request.outputDir,'report.html'),'<html>test</html>');}});
  await assert.rejects(reports.generate('owner',id,data),/frame failure/);assert.equal(reports.busy,false);
  assert.equal((await reports.generate('owner',id,data)).segments,2);assert.equal(calls,1);assert.equal(works,2);
  assert.ok((await reports.file('owner',id)).endsWith('report.html'));assert.equal(await reports.read('other',id),null);
  await assert.rejects(reports.generate('other',id,data),/本机缺少/);assert.equal(calls,1);
  await fs.writeFile(video,'different video');await assert.rejects(reports.generate('owner',id,data),/不是此任务/);assert.equal(calls,1);
  assert.throws(()=>reports.directory('../outside',id),/归属/);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
test('BYOK report generation validates output, avoids local path leakage and does not retry',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-report-model-'));
 try{
  const {manifest,data,report}=fixture();manifest.source.path='C:/private/video.mov';let count=0;
  const vault={isEncryptionAvailable:()=>true,encryptString:s=>Buffer.from(s),decryptString:b=>b.toString()};
  const models=new ModelSettings(root,vault,async(_,options)=>{count++;assert.ok(!options.body.includes('private/video'));return {ok:true,json:async()=>({choices:[{message:{content:JSON.stringify(report)},finish_reason:'stop'}]})};});
  await models.save('owner',{key:'test-key',model:'test-model'});
  assert.equal((await models.visualReport('owner',assemble(data,manifest))).report.segments.length,2);assert.equal(count,1);
  models.request=async()=>({ok:false,status:503});await assert.rejects(models.visualReport('owner',assemble(data,manifest)),/503/);assert.equal(models.busy,false);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
