const {test}=require('node:test'),assert=require('node:assert/strict');
const {GenerationActivity}=require('../src/generation-activity.cjs');
test('activity is owner isolated, cancellable, blocks concurrent paid runs, unlocks on exit',async()=>{
 const events=[],activity=new GenerationActivity(e=>events.push(e));
 const job=activity.run('owner','job','report',({signal,onProgress})=>new Promise((resolve,reject)=>{
  onProgress({phase:'reasoning',reasoningChars:20});signal.addEventListener('abort',()=>reject(Error('aborted')));
 }));
 const check=assert.rejects(job,/已停止/);
 assert.equal(activity.busy,true);assert.equal(activity.read('other'),null);
 await assert.rejects(activity.run('owner','other','summary',()=>{}),/已有/);
 assert.throws(()=>activity.cancel('other',activity.value.operationId),/没有/);
 assert.throws(()=>activity.cancel('owner','stale'),/没有/);
 activity.cancel('owner',activity.value.operationId);await check;
 assert.equal(activity.busy,false);assert.equal(activity.read('owner').status,'cancelled');
 assert.ok(events.every(e=>!('owner' in e.activity)));
 assert.equal(await activity.run('owner','job','summary',async({stage})=>{stage('正在保存完整总结');return 'saved';}),'saved');
 assert.equal(activity.read('owner').status,'completed');assert.ok(activity.value.finishedAt);
});
