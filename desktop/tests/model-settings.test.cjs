const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');const {ModelSettings}=require('../src/model-settings.cjs');
test('BYOK is isolated, hidden, retained on blank; streaming receives cancellation and does not retry',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'cine-model-'));let calls=0;
 const vault={isEncryptionAvailable:()=>true,encryptString:s=>Buffer.from(s),decryptString:b=>b.toString()};
 const options={signal:new AbortController().signal,onProgress:()=>{}};
 const models=new ModelSettings(root,vault,async()=>({ok:false,status:401}),async(config,body,passed)=>{
  calls++;assert.equal(config.key,'test-key');assert.equal(body.stream,true);assert.equal(passed,options);
  return {choices:[{message:{content:'摘要'},finish_reason:'stop'}]};
 });
 try{
  await models.save('a',{key:'test-key',model:'test/model'});await models.save('a',{key:'',model:'test/other'});
  assert.deepEqual(await models.status('a'),{configured:true,model:'test/other'});assert.deepEqual(await models.status('b'),{configured:false,model:''});
  await assert.rejects(models.summarize('a',{status:'processing',chunks:[]}),/完成/);assert.equal(calls,0);
  const data={status:'completed',chunks:[{status:'completed',result:{text:'证据'}}]};
  assert.equal((await models.summarize('a',data,options)).text,'摘要');assert.equal(calls,1);
  models.stream=async()=>{calls++;throw Error('503');};await assert.rejects(models.summarize('a',data),/503/);assert.equal(calls,2);assert.equal(models.busy,false);
  await assert.rejects(models.models('a'),/Key 无效/);await models.clear('a');assert.equal((await models.status('a')).configured,false);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
