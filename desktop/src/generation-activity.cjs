const {randomUUID} = require('node:crypto');
const {cancelled} = require('./stream-completion.cjs');
const phases = {connecting:'正在连接模型', waiting:'连接已建立，等待模型输出', reasoning:'模型正在推理', writing:'正在接收正文', validating:'正在校验完整输出'};
class GenerationActivity {
  constructor(notify) { this.notify = notify; this.busy = false; this.value = null; }
  read(owner) { return owner && this.value?.owner === owner ? this.publicValue() : null; }
  publicValue() { if (!this.value) return null; const {owner, ...value} = this.value; return structuredClone(value); }
  emit() { this.notify({type:'generation-activity', activity:this.publicValue()}); }
  cancel(owner, operationId) {
    if (!this.busy || owner !== this.value?.owner || operationId !== this.value.operationId) throw Error('当前没有可停止的生成任务');
    this.value.cancelling = true; this.emit(); this.controller.abort();
  }
  async run(owner, id, kind, work) {
    if (this.busy) throw Error('已有生成任务，请等待完成或先停止');
    if (!owner) throw Error('请先登录 Lab');
    this.busy = true; this.controller = new AbortController();
    const signal = this.controller.signal;
    this.value = {owner,id,kind,operationId:randomUUID(),status:'running',startedAt:Date.now(),lastActivityAt:Date.now(),steps:[],outputChars:0,reasoningChars:0};
    const stage = message => {
      if (signal.aborted) throw cancelled();
      this.value.message = message; this.value.lastActivityAt = Date.now();
      if (this.value.steps.at(-1)?.message !== message) this.value.steps.push({message,at:Date.now()});
      this.value.steps = this.value.steps.slice(-12); this.emit();
    };
    const onProgress = data => {
      if (signal.aborted) return;
      Object.assign(this.value, data);
      const message = (data.batchLabel ? data.batchLabel+' · ' : '') + phases[data.phase];
      if (message !== this.value.message) stage(message); else this.emit();
    };
    try {
      stage('正在读取已完成的视频分析证据');
      const result = await work({signal,onProgress,stage});
      if (signal.aborted) throw cancelled();
      this.value.status = result === null ? 'cancelled' : 'completed';
      this.value.message = result === null ? '已取消，没有生成新报告' : '已完成并保存到本机';
      return result;
    } catch (error) {
      this.value.status = signal.aborted ? 'cancelled' : 'failed';
      this.value.message = signal.aborted ? cancelled().message : error.message;
      throw signal.aborted ? cancelled() : error;
    } finally { this.busy = false; this.value.finishedAt = Date.now(); this.emit(); }
  }
}
module.exports = {GenerationActivity};
