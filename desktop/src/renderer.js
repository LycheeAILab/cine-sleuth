const $=id=>document.getElementById(id);
const api=window.cine;
let state={tasks:[],user:null},mode='local',selected=false,view='import',previousView='import',resultId=null,nextCursor=null,loading=false;
function notice(text){$('notice').textContent=text||'';$('notice').classList.toggle('hidden',!text);}
async function perform(fn){try{return await fn();}catch(error){notice(error.message);}}
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}
function switchView(value){view=value;for(const item of ['import','history','result','settings','updates'])$(item+'-view').classList.toggle('hidden',item!==value);$('location').textContent=value==='import'?'新建分析':value==='history'?'分析历史':value==='settings'?'模型设置':value==='updates'?'软件更新':'模型结果';$('nav-settings').classList.toggle('active',value==='settings');$('nav-import').classList.toggle('active',value==='import');$('nav-history').classList.toggle('active',value==='history');}
function setBusy(){const blocked=Boolean(state.running)||loading;$('start').disabled=blocked||!state.user||!$('consent').checked||(mode==='local'?!selected:!$('url').value.trim());$('login').disabled=blocked;$('logout').disabled=blocked;}
async function refresh(){state=await api.state();$('account-name').textContent=state.user?.displayName||'尚未登录';$('login').classList.toggle('hidden',!!state.user);$('logout').classList.toggle('hidden',!state.user);$('devices').classList.toggle('hidden',!state.user);if(state.authError)notice(state.authError);renderTasks();setBusy();}
const statusNames={preparing:'准备中',uploading:'上传中',analyzing:'分析中',queued:'等待分析',processing:'处理中',completed:'已完成',failed:'失败',paused:'已暂停'};
function taskRow(task,local){
  const row=element('article',undefined,'task-row'),pill=element('span',statusNames[task.status]||task.status,'pill '+task.status),info=element('div',undefined,'task-info');
  info.append(element('div',task.fileName||task.jobId,'task-title'));
  const interrupted=local&&['preparing','uploading','analyzing'].includes(task.status)&&state.running!==task.id;
  info.append(element('div',interrupted?'本地流程已中断，可以继续':task.stage||task.errorMessage||`${new Date(task.createdAt).toLocaleString('zh-CN')} · ${task.entryPoint==='desktop'?'桌面端':'CineSleuth'}`,'task-detail'));
  if(local&&task.total){const progress=element('progress');progress.max=task.total;progress.value=task.completed;info.append(progress);}
  const actions=element('div',undefined,'task-actions');
  if(local&&state.running===task.id){const pause=element('button','暂停');pause.onclick=()=>perform(async()=>{pause.disabled=true;await api.pause();await refresh();});actions.append(pause);}
  else if(local&&task.status!=='completed'){const resume=element('button','继续');resume.disabled=!!state.running;resume.onclick=()=>perform(async()=>{resume.disabled=true;await api.resume(task.id);await refresh();});actions.append(resume);}
  if(task.jobId){const result=element('button','查看结果');result.onclick=()=>perform(()=>showResult(task.jobId));actions.append(result);}
  row.append(pill,info,actions);return row;
}
function renderTasks(){const list=$('tasks');list.replaceChildren();if(!state.tasks.length)list.append(element('div','还没有任务，先导入一段视频。','empty'));for(const task of state.tasks)list.append(taskRow(task,true));}
async function history(more=false){const body=await api.history(more?nextCursor:null);if(!more)$('history').replaceChildren();for(const task of body.jobs)$('history').append(taskRow(task,false));if(!more&&!body.jobs.length)$('history').append(element('div','当前账户暂无云端任务。','empty'));nextCursor=body.nextCursor;$('more').classList.toggle('hidden',!nextCursor);}
function evidence(raw){if(raw?.candidates){const text=(raw.candidates[0]?.content?.parts||[]).map(p=>p.text||'').join('\n').replace(/^```(?:json)?\s*/i,'').replace(/\s*```$/,'');try{return JSON.parse(text);}catch{return raw;}}return raw;}
const labels={media_fingerprint:'画面识别',chunk:'片段信息',transcript:'台词与字幕',shots:'镜头证据',scenes:'场景',audio:'声音',audio_events:'声音事件',uncertainties:'不确定项',visual_segments:'视觉段落',sound_design:'声音设计',screen_text:'画面文字',narrative:'叙事结构'};
async function showResult(id){const data=await api.results(id);resultId=id;previousView=view==='result'?previousView:view;switchView('result');$('result').replaceChildren();$('summary').replaceChildren();$('summary').classList.add('hidden');$('export-summary').classList.add('hidden');$('summarize').disabled=data.status!=='completed';const saved=await api.summaryRead(id);renderSummary(saved);
  if(!data.chunks.length)$('result').append(element('div','还没有模型结果。可以返回任务继续分析。','empty'));
  for(const chunk of data.chunks){const card=element('article',undefined,'result-chunk');card.append(element('h2',`${chunk.chunkKey} · ${statusNames[chunk.status]||chunk.status}`));
    const value=evidence(chunk.result);if(!value)card.append(element('p',chunk.errorMessage||'此片段尚未完成','observation'));
    else for(const [key,content] of Object.entries(value)){const detail=element('details'),summary=element('summary',labels[key]||key);detail.open=['media_fingerprint','transcript','shots'].includes(key);detail.append(summary,element('pre',typeof content==='string'?content:JSON.stringify(content,null,2)));card.append(detail);}
    $('result').append(card);
  }
}
$('login').onclick=()=>perform(async()=>notice(await api.login()));
$('logout').onclick=()=>perform(async()=>{await api.logout();notice('已退出当前设备');$('history').replaceChildren();$('result').replaceChildren();switchView('import');selected=false;$('file-name').textContent='选择一段视频';await refresh();});
$('devices').onclick=()=>perform(()=>api.devices());
$('select').onclick=()=>perform(async()=>{const file=await api.select();if(file){selected=true;$('file-name').textContent=file.name;$('file-meta').textContent=`${(file.sizeBytes/1024/1024).toFixed(1)} MB · 最长 5 分钟`;}setBusy();});
for(const name of ['local','link'])$('tab-'+name).onclick=()=>{mode=name;for(const item of ['local','link']){$(item+'-input').classList.toggle('hidden',item!==name);$('tab-'+item).classList.toggle('active',item===name);$('tab-'+item).setAttribute('aria-selected',String(item===name));}setBusy();};
$('consent').onchange=setBusy;$('url').oninput=setBusy;
$('start').onclick=()=>perform(async()=>{loading=true;setBusy();notice('');try{await api.start({mode,url:$('url').value,consent:$('consent').checked});await refresh();}finally{loading=false;setBusy();}});
$('nav-import').onclick=()=>switchView('import');$('nav-history').onclick=()=>perform(async()=>{switchView('history');await history();});
$('refresh-history').onclick=()=>perform(()=>history());$('more').onclick=()=>perform(()=>history(true));$('back').onclick=()=>switchView(previousView);
$('export').onclick=()=>perform(async()=>notice(await api.export(resultId)));
api.onEvent(event=>{if(event.type==='update')renderUpdate(event.state);else if(event.type==='error')notice(event.message);else if(event.type==='auth'){notice('已登录 LycheeAILab');void perform(()=>refresh());}else if(event.type==='task'){
  state.running=event.task.id;const index=state.tasks.findIndex(task=>task.id===event.task.id);if(index>=0)state.tasks[index]=event.task;else state.tasks.unshift(event.task);renderTasks();setBusy();
}else if(event.type==='idle')void perform(()=>refresh());});
void perform(()=>refresh());

function renderSummary(value){$('summary').textContent=value?`${value.model} · ${new Date(value.createdAt).toLocaleString('zh-CN')}\n\n${value.text}`:'';$('summary').classList.toggle('hidden',!value);$('export-summary').classList.toggle('hidden',!value);}
function settingsStatus(value){$('model-key').value='';$('key-status').textContent=value.configured?'已保存 Key；留空可保留原 Key':'尚未配置';$('model-id').value=value.model||'';}
$('nav-settings').onclick=()=>perform(async()=>{switchView('settings');$('model-key').value='';$('model-id').value='';$('key-status').textContent='尚未配置';if(!state.user){notice('请先登录 Lab');return;}settingsStatus(await api.modelStatus());});
$('save-settings').onclick=()=>perform(async()=>{settingsStatus(await api.modelSave({key:$('model-key').value,model:$('model-id').value}));notice('模型设置已保存');});
$('load-models').onclick=()=>perform(async()=>{const button=$('load-models');button.disabled=true;try{const items=await api.modelList();$('models').replaceChildren(...items.map(id=>{const option=element('option');option.value=id;return option;}));notice(`已获取 ${items.length} 个模型，点击模型输入框选择`);}finally{button.disabled=false;}});
$('clear-settings').onclick=()=>perform(async()=>{await api.modelClear();settingsStatus({});notice('模型配置已删除');});
$('summarize').onclick=()=>perform(async()=>{const id=resultId;$('summarize').disabled=true;$('summarize').textContent='正在生成总结…';try{const value=await api.summarize(id);if(resultId===id)renderSummary(value);notice('总结已生成并保存在本机');}finally{$('summarize').disabled=false;$('summarize').textContent='生成总结';}});
$('export-summary').onclick=()=>perform(async()=>notice(await api.summaryExport(resultId)));

function renderUpdate(value){$('app-version').textContent='镜探 '+value.currentVersion;const messages={idle:'自动检查更新已开启',checking:'正在检查更新…',current:'已是最新版本',downloading:`正在下载 ${value.version||''} · ${value.percent||0}%`,ready:`${value.version} 已下载，可以重启安装`,error:value.error,disabled:'开发模式不检查更新'};$('update-status').textContent=messages[value.status]||'';$('check-update').disabled=['checking','downloading','ready','disabled'].includes(value.status);$('install-update').classList.toggle('hidden',value.status!=='ready');$('update-progress').classList.toggle('hidden',value.status!=='downloading');$('update-progress').value=value.percent||0;$('nav-updates').textContent=value.status==='ready'?'软件更新 · 可安装':'软件更新';}
$('nav-updates').onclick=()=>perform(async()=>{switchView('updates');renderUpdate(await api.updateState());});
$('check-update').onclick=()=>perform(async()=>renderUpdate(await api.updateCheck()));
$('install-update').onclick=()=>perform(()=>api.updateInstall());
void perform(async()=>renderUpdate(await api.updateState()));
