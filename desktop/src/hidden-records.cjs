const fs=require('node:fs/promises');
const path=require('node:path');
const {createHash}=require('node:crypto');
const {saveJson}=require('./pipeline.cjs');
const valid=id=>typeof id==='string'&&/^[a-f0-9-]{36}$/.test(id);
// Local tombstones only. Never mutate task files, media or Lab records.
class HiddenRecords {
  constructor(root){this.root=root;}
  file(user){if(!user)throw Error('请先登录');return path.join(this.root,createHash('sha256').update(String(user)).digest('hex')+'.json');}
  async read(user){try{const value=JSON.parse(await fs.readFile(this.file(user),'utf8'));if(!Array.isArray(value))throw Error('本机列表设置无效');return new Set(value);}catch(e){if(e.code==='ENOENT')return new Set();throw e;}}
  async hide(user,{id,jobId}){if(!valid(id)&&!valid(jobId))throw Error('任务编号无效');const hidden=await this.read(user);if(valid(id))hidden.add('local:'+id);if(valid(jobId))hidden.add('job:'+jobId);await saveJson(this.file(user),[...hidden]);}
  async filter(user,records){const hidden=await this.read(user);return records.filter(item=>!hidden.has('local:'+item.id)&&!hidden.has('job:'+item.jobId));}
}
module.exports={HiddenRecords};
