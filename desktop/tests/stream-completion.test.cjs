const {test}=require('node:test'),assert=require('node:assert/strict');
const http=require('node:http');
const {EventEmitter}=require('node:events');
const {streamCompletion}=require('../src/stream-completion.cjs');
const packet=(delta,finish_reason=null)=>`data: ${JSON.stringify({choices:[{delta,finish_reason}]})}\n\n`;
async function fixture(handler,work){
 const server=http.createServer(handler);await new Promise(r=>server.listen(0,'127.0.0.1',r));
 let requests=0;
 const request=(url,options,callback)=>{requests++;assert.equal(url,'https://api.siliconflow.cn/v1/chat/completions');assert.equal(options.timeout,undefined);return http.request(`http://127.0.0.1:${server.address().port}`,options,callback);};
 try{await work(request,()=>requests);}finally{server.closeAllConnections();await new Promise(r=>server.close(r));}
}
test('real HTTP SSE: fragmented UTF-8, reasoning activity, stop and no reasoning leakage',async()=>{
 await fixture((req,res)=>{let body='';req.on('data',s=>body+=s);req.on('end',()=>{
  assert.equal(JSON.parse(body).stream,true);res.writeHead(200,{'Content-Type':'text/event-stream'});
  const data=Buffer.from(': ping\r\n\r\n'+packet({reasoning_content:'internal secret reasoning'})+packet({content:'你好，世界'})+packet({},'stop')+'data: [DONE]\n\n');
  for(let i=0;i<data.length;i+=2)res.write(data.subarray(i,i+2));res.end();
 });},async request=>{
  const events=[];const result=await streamCompletion({key:'fixture'},{model:'fixture'},{onProgress:p=>events.push(p)},request);
  assert.equal(result.choices[0].message.content,'你好，世界');assert.equal(result.choices[0].finish_reason,'stop');
  assert.ok(events.some(e=>e.phase==='reasoning'));assert.ok(!JSON.stringify(events).includes('internal secret'));
  assert.equal(events.at(-1).outputChars,5);
 });
});
test('no 180s total cutoff, even before response headers; manual cancel terminates',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});
 let captured, destroyed=false;
 const req=new EventEmitter();req.end=()=>{};req.destroy=()=>{destroyed=true;};
 const request=(_,options)=>{captured=options;return req;};
 const controller=new AbortController();let settled=false;
 const promise=streamCompletion({key:'fixture'},{model:'fixture'},{signal:controller.signal},request);
 const check=assert.rejects(promise,/已停止/).then(()=>{settled=true;});
 t.mock.timers.tick(20*60*1000);await Promise.resolve();
 assert.equal(settled,false);assert.equal(captured.timeout,undefined);assert.equal(destroyed,false);
 controller.abort();await check;assert.equal(destroyed,true);
});
test('mid-stream cancel closes socket and makes exactly one request',async()=>{
 await fixture((_,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});res.write(packet({content:'partial'}));},async(request,count)=>{
  const controller=new AbortController();
  await assert.rejects(streamCompletion({key:'fixture'},{},{signal:controller.signal,onProgress:p=>{if(p.phase==='writing')queueMicrotask(()=>controller.abort());}},request),/已停止/);
  assert.equal(count(),1);
 });
});
test('reject HTTP errors, non-SSE, truncated stream and malformed frames without retry',async()=>{
 for(const scenario of [401,402,429,503,'json','truncated','broken'])await fixture((_,res)=>{
  if(typeof scenario==='number'){res.writeHead(scenario);return res.end('secret provider error');}
  res.writeHead(200,{'Content-Type':scenario==='json'?'application/json':'text/event-stream'});
  res.end(scenario==='json'?'{}':scenario==='broken'?'data: bad\n\n':packet({content:'partial'}));
 },async(request,count)=>{
  await assert.rejects(streamCompletion({key:'fixture'},{},{},request),e=>!e.message.includes('secret')&&/无效|不足|限额|503|流式|完成标记/.test(e.message));assert.equal(count(),1);
 });
});
test('length finish stays explicit so callers reject partial reports',async()=>{
 await fixture((_,res)=>{res.writeHead(200,{'Content-Type':'text/event-stream'});res.end(packet({content:'partial'},'length')+'data: [DONE]\n\n');},async request=>{
  assert.equal((await streamCompletion({key:'fixture'},{},{},request)).choices[0].finish_reason,'length');
 });
});
