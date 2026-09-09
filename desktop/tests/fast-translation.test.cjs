const {test}=require('node:test');
const assert=require('node:assert/strict');
const {needsTranslation,translateFastReport,FIELDS}=require('../src/fast-translation.cjs');

function report(count,text){
  return {title:'极速表格',overview:'',sections:[],uncertainties:'无',segments:Array.from({length:count},(_,index)=>({id:`seg-${index+1}`,start_seconds:index,end_seconds:index+1,evidence_ids:[`shot-${index+1}`],...Object.fromEntries(FIELDS.map(field=>[field,field==='title'?`镜头 ${index+1}`:text]))}))};
}
test('English evidence is detected while Chinese evidence stays zero-call',()=>{
 assert.equal(needsTranslation(report(1,'人物在桥上缓慢行走，镜头保持固定。')),false);
 assert.equal(needsTranslation(report(1,'A young woman is walking slowly on a bridge while the camera remains static.')),true);
});
test('fast translation is structured, batched and resumable',async()=>{
 const source=report(9,'A person walks across a bridge in a wide cinematic shot.'),saved=[];let calls=0,checkpoint=null;
 const options={checkpoint:{read:async()=>checkpoint,write:async value=>{checkpoint=JSON.parse(JSON.stringify(value));}},stage:value=>saved.push(value)};
 const call=async(_,body)=>{calls++;const input=JSON.parse(body.messages[1].content);assert.equal(body.thinking_budget,1024);return {choices:[{finish_reason:'stop',message:{content:JSON.stringify({segments:input.segments.map(item=>Object.fromEntries(Object.entries(item).map(([key])=>[key,key==='id'?item.id:'已翻译中文'])))})}}]};};
 const first=await translateFastReport(source,{model:'test'},call,options);assert.equal(calls,2);assert.equal(first.segments[8].visuals,'已翻译中文');
 calls=0;const second=await translateFastReport(source,{model:'test'},call,options);assert.equal(calls,0);assert.deepEqual(second,first);assert.match(saved.at(-1),/复用/);
});
