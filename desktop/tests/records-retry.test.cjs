const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');
const {HiddenRecords}=require('../src/hidden-records.cjs');
const {AnalysisPipeline}=require('../src/pipeline.cjs');
const {LabClient}=require('../src/lab-client.cjs');
test('local tombstones survive reload, isolate accounts and preserve files/cloud records',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-hide-'));
  try{
    const task={id:'11111111-1111-4111-8111-111111111111',jobId:'22222222-2222-4222-8222-222222222222'};
    const media=path.join(root,'kept.mp4');await fs.writeFile(media,'untouched');
    await new HiddenRecords(root).hide('alice',task);
    const reloaded=new HiddenRecords(root);
    assert.equal((await reloaded.filter('alice',[task])).length,0);
    assert.equal((await reloaded.filter('alice',[{jobId:task.jobId}])).length,0);
    assert.equal((await reloaded.filter('bob',[task])).length,1);
    assert.equal(await fs.readFile(media,'utf8'),'untouched');
    await assert.rejects(reloaded.hide('alice',{id:'../../unsafe'}));
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
test('link parsing retries exactly three times, never creates cloud analysis; other failures are not retried',async()=>{
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-retry-'));
  try{
    for(const code of ['LINK_RESOLUTION_FAILED','INVALID_VIDEO']){
      let attempts=0,requests=0;
      const engine=new AnalysisPipeline({client:{api:async()=>{requests++;}},root,runtime:root,notify:()=>{},wait:async()=>{},prepare:async()=>{attempts++;throw Object.assign(Error('bad'),{code});}});
      const task=await engine.start({id:'alice'},{url:'https://v.douyin.com/test'});await engine.running.promise;
      assert.equal(attempts,code==='LINK_RESOLUTION_FAILED'?3:1);assert.equal(requests,0);assert.equal(task.status,'failed');
      if(attempts===3)assert.match(task.stage,/已尝试 3 次.*本地视频/);
    }
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
test('timeout messages cover response body and headers without replaying a request or clearing login',async()=>{
  for(const phase of ['headers','body']){
    let calls=0;
    const error=new DOMException('The operation was aborted due to timeout','TimeoutError');
    const client=new LabClient('https://example.invalid',{});
    client.request=async()=>{calls++;if(phase==='headers')throw error;return{ok:true,text:async()=>{throw error;}};};
    client.tokens={accessToken:'fake',expiresAt:Date.now()+1000000};
    await assert.rejects(client.api('/api/test',{method:'POST'}),e=>e.code==='LAB_TIMEOUT'&&e.message.includes('不会自动重复提交'));
    assert.equal(calls,1);assert.equal(client.tokens.accessToken,'fake');
  }
});
test('transient status reads retry; authentication failures and manual pause do not',async()=>{
  let reads=0;
  const engine=new AnalysisPipeline({wait:async()=>{},client:{api:async()=>{if(++reads<3)throw Object.assign(Error('timeout'),{status:504});return{status:'completed'};}}});
  assert.equal((await engine.readChunk('/chunks/one',new AbortController().signal)).status,'completed');assert.equal(reads,3);
  reads=0;engine.client.api=async()=>{reads++;throw Object.assign(Error('denied'),{status:401});};
  await assert.rejects(engine.readChunk('/chunks/one',new AbortController().signal));assert.equal(reads,1);
});
