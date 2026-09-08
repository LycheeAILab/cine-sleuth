const fs = require('node:fs/promises');
const {createReadStream} = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createHash,randomUUID} = require('node:crypto');
const https = require('node:https');
const {pipeline} = require('node:stream/promises');
const {setTimeout:delay} = require('node:timers/promises');

async function saveJson(file,value) {await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(file+'.tmp',JSON.stringify(value,null,2));await fs.rename(file+'.tmp',file);}
async function hashFile(file) {const hash=createHash('sha256');for await(const block of createReadStream(file)) hash.update(block);return hash.digest('hex');}
function uploadTarget(value) {
  const url=new URL(value);
  if(url.protocol!=='https:'||!url.hostname.endsWith('.myqcloud.com')||url.username||url.password||(url.port&&url.port!=='443'))throw Error('Lab 上传地址无效');
  return url;
}
async function uploadOriginal(value,source,type,signal) {
  const url=uploadTarget(value),size=(await fs.stat(source)).size;
  await new Promise((resolve,reject)=>{
    const request=https.request(url,{method:'PUT',headers:{'Content-Type':type,'Content-Length':size},signal},response=>{
      response.resume();response.on('end',()=>response.statusCode>=200&&response.statusCode<300?resolve():reject(Error(`原视频上传失败（${response.statusCode}）`)));
      response.on('error',reject);
    });
    request.setTimeout(900000,()=>request.destroy(Error('原视频上传超时，可稍后继续')));
    request.on('error',reject);pipeline(createReadStream(source),request).catch(reject);
  });
}
function renderPrompt(markdown,manifest,chunk) {
  const prompt=markdown.match(/```text\s*([\s\S]*?)\s*```/)?.[1]||markdown;
  const values={CHUNK_ID:chunk.chunk_id,GLOBAL_OFFSET_SECONDS:chunk.source_start_seconds,CHUNK_DURATION_SECONDS:chunk.duration_seconds,
    TOTAL_DURATION_SECONDS:manifest.source.duration_seconds,OVERLAP_BEFORE_SECONDS:chunk.overlap_before_seconds,OVERLAP_AFTER_SECONDS:chunk.overlap_after_seconds};
  return prompt.replace(/{{([A-Z_]+)}}/g,(match,key)=>key in values?String(values[key]):match);
}
function prepareMedia(worker,request,runtime,signal) {
  return new Promise((resolve,reject)=>{
    const child=spawn(worker,[],{windowsHide:true,env:{...process.env,PATH:runtime+path.delimiter+process.env.PATH,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'},stdio:['pipe','pipe','pipe']});
    let output='',error='';
    const stop=()=>{if(child.pid)spawn('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'}).on('error',()=>child.kill());};
    signal.addEventListener('abort',stop,{once:true});
    const timeout=setTimeout(stop,20*60*1000);
    child.stdout.on('data',data=>{output+=data.toString('utf8');});
    child.stderr.on('data',data=>{error=(error+data.toString('utf8')).slice(-4000);});
    child.on('error',reject);child.stdin.on('error',()=>{});
    child.on('close',code=>{
      clearTimeout(timeout);signal.removeEventListener('abort',stop);
      if(signal.aborted)return reject(Error('已暂停，本地进度已保留'));
      if(code!==0)return reject(Error(error.trim()||'媒体准备失败，请换用本地视频重试'));
      try {resolve(JSON.parse(output));}catch{reject(Error('媒体工具返回无效结果'));}
    });
    child.stdin.end(JSON.stringify(request));
  });
}
class AnalysisPipeline {
  constructor({client,root,runtime,promptFile,notify,prepare=prepareMedia,upload=uploadOriginal}) {
    Object.assign(this,{client,root,runtime,promptFile,notify,prepare,upload});this.running=null;
  }
  async tasks(userId) {
    const dir=path.join(this.root,userId);await fs.mkdir(dir,{recursive:true});
    const tasks=[];
    for(const name of await fs.readdir(dir)) {
      if(!/^[a-f0-9-]{36}$/.test(name))continue;
      try{const item=JSON.parse(await fs.readFile(path.join(dir,name,'task.json'),'utf8'));if(item.userId===userId)tasks.push(item);}catch{}
    }
    return tasks.sort((a,b)=>b.createdAt.localeCompare(a.createdAt));
  }
  async start(user,source) {
    if(this.running)throw Error('已有任务正在处理');
    const task={id:randomUUID(),userId:user.id,fileName:source.video?path.basename(source.video):'链接视频',source,createdAt:new Date().toISOString(),status:'preparing',stage:'正在准备视频',completed:0,total:0};
    await saveJson(path.join(this.root,user.id,task.id,'task.json'),task);
    this.launch(task);return task;
  }
  async resume(user,id) {
    if(this.running)throw Error('已有任务正在处理');
    if(!/^[a-f0-9-]{36}$/.test(id))throw Error('任务编号无效');
    const task=JSON.parse(await fs.readFile(path.join(this.root,user.id,id,'task.json'),'utf8'));
    if(task.userId!==user.id)throw Error('任务不属于当前账号');
    this.launch(task);return task;
  }
  launch(task) {
    const controller=new AbortController();this.running={task,controller};
    this.running.promise=this.run(task,controller.signal).catch(async error=>{
      task.status=controller.signal.aborted?'paused':'failed';task.stage=controller.signal.aborted?'已暂停；服务端已提交的分析可能继续完成':error.message;
      await this.update(task);
    }).finally(()=>{this.running=null;this.notify({type:'idle'});});
  }
  async update(task) {await saveJson(path.join(this.root,task.userId,task.id,'task.json'),task);this.notify({type:'task',task});}
  async pause() {if(this.running){this.running.controller.abort();await this.running.promise;}}
  async run(task,signal) {
    const dir=path.join(this.root,task.userId,task.id),manifestFile=path.join(dir,'manifest.json');
    let manifest;
    try{manifest=JSON.parse(await fs.readFile(manifestFile,'utf8'));}catch{}
    if(!manifest) {
      task.status='preparing';task.stage=task.source.url?'正在从链接下载并准备视频…':'正在探测视频并准备分析片段…';await this.update(task);
      await this.prepare(path.join(this.runtime,'cine-media','cine-media.exe'),{...task.source,outputDir:dir},this.runtime,signal);
      manifest=JSON.parse(await fs.readFile(manifestFile,'utf8'));
    }
    signal.throwIfAborted();
    if(await hashFile(manifest.source.path)!==manifest.source.sha256)throw Error('原视频已变更，请重新导入');
    const ext=path.extname(manifest.source.path).toLowerCase();
    const mediaType={'.mp4':'video/mp4','.m4v':'video/mp4','.mov':'video/quicktime','.webm':'video/webm','.mkv':'video/x-matroska'}[ext];
    task.total=manifest.chunks.length;task.fileName=path.basename(manifest.source.path);task.status='uploading';task.stage='正在注册 Lab 任务…';await this.update(task);
    const post=(route,body)=>this.client.api(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{}),signal});
    const job=task.jobId?await this.client.api(`/api/cine-sleuth/jobs/${task.jobId}`,{signal}):await post('/api/cine-sleuth/jobs',{
      fileName:task.fileName,mediaType,sizeBytes:manifest.source.size_bytes,durationSeconds:manifest.source.duration_seconds,checksumSha256:manifest.source.sha256,
      clientRequestId:`desktop-${task.id}`,chunkCount:manifest.chunks.length,
    });
    task.jobId=job.jobId;await this.update(task);
    if(job.originalVideo.status!=='ready'){
      task.stage='正在上传原视频到 Lab…';await this.update(task);
      await this.upload(job.upload.url,manifest.source.path,mediaType,signal);
      await post(`/api/cine-sleuth/jobs/${task.jobId}/upload-complete`);
    }
    const prompt=await fs.readFile(this.promptFile,'utf8');task.completed=0;
    for(const chunk of manifest.chunks) {
      signal.throwIfAborted();
      task.status='analyzing';task.stage=`模型分析中 · ${task.completed+1} / ${task.total}`;await this.update(task);
      const route=`/api/cine-sleuth/jobs/${task.jobId}/chunks/${encodeURIComponent(chunk.chunk_id)}`;
      let state=await this.client.api(route,{signal}).catch(error=>{if(error.status===404)return null;throw error;});
      if(state?.status!=='completed'&&state?.status!=='processing'){
        const video=await fs.readFile(chunk.path);
        if(video.length>12*1024*1024)throw Error('分析片段超过 Lab 12 MB 限制，请重新导入');
        const form=new FormData();form.set('jobId',task.jobId);form.set('chunkKey',chunk.chunk_id);form.set('prompt',renderPrompt(prompt,manifest,chunk));form.set('video',new Blob([video],{type:'video/mp4'}),`${chunk.chunk_id}.mp4`);
        try {await this.client.api('/api/cine-sleuth/analyze',{method:'POST',body:form,signal:AbortSignal.any([signal,AbortSignal.timeout(360000)])});}
        catch(error){if(signal.aborted)throw error;if(error.status&&error.status!==409&&error.status<500)throw error;}
        state=await this.client.api(route,{signal});
      }
      const deadline=Date.now()+7*60*1000;
      while(state.status==='processing'||state.status==='queued') {
        if(Date.now()>deadline)throw Error('Lab 仍在分析，请稍后点击继续');
        await delay(3000,undefined,{signal});state=await this.client.api(route,{signal});
      }
      if(state.status!=='completed')throw Error(state.errorMessage||'片段分析失败，可点击继续');
      task.completed++;await this.update(task);
    }
    await post(`/api/cine-sleuth/jobs/${task.jobId}/complete`);
    const result=await this.client.api(`/api/cine-sleuth/jobs/${task.jobId}/model-results`,{signal});
    await saveJson(path.join(dir,'model-results.json'),result);
    task.status='completed';task.stage='模型分析完成，结果已保存到 Lab';await this.update(task);
  }
}
module.exports={AnalysisPipeline,saveJson,renderPrompt,hashFile,uploadTarget};
