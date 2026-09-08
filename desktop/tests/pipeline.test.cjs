const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');
const {AnalysisPipeline,saveJson,hashFile,uploadTarget}=require('../src/pipeline.cjs');
test('upload destination never receives a Lab token and rejects foreign or insecure hosts',()=>{
  assert.equal(uploadTarget('https://bucket.cos.ap-test.myqcloud.com/key?signature=abc').protocol,'https:');
  for(const url of ['http://bucket.myqcloud.com/key','https://myqcloud.com.evil/key','https://user:pass@x.myqcloud.com/key'])assert.throws(()=>uploadTarget(url));
});
test('local and link imports use the same Lab pipeline; resume skips completed model calls',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-desktop-'));
  try{
    const promptFile=path.join(root,'prompt.md');await fs.writeFile(promptFile,'```text\nAnalyze {{CHUNK_ID}} at {{GLOBAL_OFFSET_SECONDS}}\n```');
    for(const mode of ['local','link']){
      let analyzed=0,uploaded=0,created=0,done=false;const id='11111111-1111-4111-8111-111111111111';
      const client={api:async(route,options)=>{
        if(route==='/api/cine-sleuth/jobs'){created++;const body=JSON.parse(options.body);assert.match(body.clientRequestId,/^desktop-/);assert.equal(body.chunkCount,1);return {jobId:id,originalVideo:{status:'pending'},upload:{url:'https://x.myqcloud.com/original'}};}
        if(route.endsWith('/upload-complete'))return {};
        if(route===`/api/cine-sleuth/jobs/${id}`)return {jobId:id,originalVideo:{status:'ready'}};
        if(route.includes('/chunks/')){if(done)return {status:'completed',result:{}};const error=Error('not found');error.status=404;throw error;}
        if(route.endsWith('/analyze')){analyzed++;assert.equal(options.body.get('jobId'),id);assert.equal(options.body.get('video').type,'video/mp4');done=true;if(mode==='link')throw Object.assign(Error('response timed out after completion'),{status:504});return {};}
        if(route.endsWith('/complete'))return {status:'completed'};
        if(route.endsWith('/model-results'))return {kind:'model_analysis',chunks:[{chunkKey:'chunk-001',status:'completed',result:{}}]};
        throw Error('Unexpected route '+route);
      }};
      const engine=new AnalysisPipeline({client,root,runtime:root,promptFile,notify:()=>{},upload:async()=>{uploaded++;},prepare:async(_,request)=>{
        assert.equal(Boolean(request.url),mode==='link');const video=path.join(request.outputDir,'source.mp4');await fs.writeFile(video,'test-video');
        await saveJson(path.join(request.outputDir,'manifest.json'),{source:{path:video,sha256:await hashFile(video),duration_seconds:5,size_bytes:10},chunks:[{chunk_id:'chunk-001',path:video,source_start_seconds:0,duration_seconds:5,overlap_before_seconds:0,overlap_after_seconds:0}]});
      }});
      const user={id:'test-user'},task=await engine.start(user,mode==='local'?{video:'input.mp4'}:{url:'https://v.douyin.com/example'});
      await engine.running.promise;assert.equal(task.status,'completed');assert.equal(analyzed,1);assert.equal(uploaded,1);
      await engine.resume(user,task.id);await engine.running.promise;assert.equal(analyzed,1);assert.equal(uploaded,1);assert.equal(created,1);
      assert.equal((await engine.tasks(user.id)).find(t=>t.id===task.id).status,'completed');
      await assert.rejects(engine.resume({id:'another-user'},task.id));
    }
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
