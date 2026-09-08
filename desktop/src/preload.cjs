const {contextBridge,ipcRenderer} = require('electron');
const methods=['state','login','logout','devices','select','start','resume','pause','removeRecord','history','results','export','modelStatus','modelSave','modelClear','modelList','summaryRead','summarize','summaryExport','reportRead','reportGenerate','reportOpen','reportExport','generationState','generationCancel','updateState','updateCheck','updateInstall'];
const api=Object.fromEntries(methods.map(method=>[method,async(...args)=>{
  const result=await ipcRenderer.invoke('cine:'+method,...args);
  if(!result.ok)throw Error(result.message);return result.value;
}]));
api.onEvent=callback=>{const listener=(_,value)=>callback(value);ipcRenderer.on('cine:event',listener);return()=>ipcRenderer.removeListener('cine:event',listener);};
contextBridge.exposeInMainWorld('cine',Object.freeze(api));
