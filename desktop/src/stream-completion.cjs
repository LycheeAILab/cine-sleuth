const https = require('node:https');
const MAX_EVENT_BYTES = 1024 * 1024, MAX_CONTENT_BYTES = 2 * 1024 * 1024, PREVIEW_CHARS = 8000;

function cancelled() { return Object.assign(Error('已停止本次生成；已有文件保留，不会自动重新请求'), {name: 'AbortError'}); }
function httpError(status) {
  return Error(status === 401 ? '硅基流动 API Key 无效' : status === 402 ? '硅基流动账户余额不足' :
    status === 429 ? '硅基流动请求繁忙或达到限额，请稍后手动重试' : `硅基流动请求失败（${status}），不会自动重试`);
}

// Native HTTPS has no fetch/Undici headers deadline. There is deliberately no
// wall-clock generation timeout, no redirects and no automatic paid retry.
function streamCompletion(config, body, {signal, onProgress = () => {}} = {}, request = https.request) {
  return new Promise((resolve, reject) => {
    let req, response, settled = false, buffer = '', content = '', reasoningChars = 0, finish = null, contentBytes = 0, wireBytes = 0, events = 0, reasoningPreview = '';
    let eventLines = [], eventBytes = 0, lastEmit = 0, lastPhase = '';
    const progress = (phase, force = false) => {
      const now = Date.now();
      if (force || phase !== lastPhase || now - lastEmit >= 200) {
        lastEmit = now; lastPhase = phase;
        onProgress({phase, model: body.model, outputChars: content.length, reasoningChars, reasoningPreview, outputPreview: content.slice(-PREVIEW_CHARS), wireBytes, events, lastActivityAt: now});
      }
    };
    const settle = (error, value) => {
      if (settled) return;
      settled = true; signal?.removeEventListener('abort', abort);
      if (error) reject(error); else resolve(value);
      response?.destroy(); req?.destroy();
    };
    const abort = () => settle(cancelled());
    const complete = () => {
      if (!finish) return settle(Error('模型连接已结束，但未返回完成标记；未保存不完整结果，请手动重试'));
      if (!['stop','length'].includes(finish)) return settle(Error('模型未正常完成正文生成，未保存不完整结果'));
      progress('validating', true);
      settle(null, {choices: [{message: {content}, finish_reason: finish}]});
    };
    const event = () => {
      if (!eventLines.length) return;
      const data = eventLines.join('\n'); eventLines = []; eventBytes = 0; events++;
      if (data.trim() === '[DONE]') return complete();
      let value;
      try { value = JSON.parse(data); } catch { return settle(Error('模型流式响应格式无效，未保存不完整结果')); }
      if (value.error) return settle(Error('模型在生成过程中返回错误，请检查供应商状态；不会自动重试'));
      const choice = value.choices?.[0], delta = choice?.delta;
      if (typeof delta?.reasoning_content === 'string') {
        reasoningChars += delta.reasoning_content.length;
        reasoningPreview = (reasoningPreview + delta.reasoning_content).slice(-PREVIEW_CHARS);
      }
      if (typeof delta?.content === 'string') {
        contentBytes += Buffer.byteLength(delta.content);
        if (contentBytes > MAX_CONTENT_BYTES) return settle(Error('模型正文超过 2 MB，已停止接收；已有报告保留'));
        content += delta.content;
      }
      if (choice?.finish_reason) finish = choice.finish_reason;
      // Preview only provider-returned text, in bounded memory; never add reasoning to saved reports.
      progress(delta?.content ? 'writing' : delta?.reasoning_content ? 'reasoning' : lastPhase || 'waiting');
    };
    const line = value => {
      if (value === '') event();
      else if (value.startsWith('data:')) {
        const part = value.slice(5).replace(/^ /, ''); eventBytes += Buffer.byteLength(part);
        if (eventBytes > MAX_EVENT_BYTES) return settle(Error('模型单条流式消息超过 1 MB，响应格式异常；已有报告保留'));
        eventLines.push(part);
      }
    };
    if (signal?.aborted) return abort();
    signal?.addEventListener('abort', abort, {once: true});
    progress('connecting', true);
    if (settled) return;
    try {
      req = request('https://api.siliconflow.cn/v1/chat/completions', {
        method: 'POST', agent: false, headers: {Authorization: 'Bearer ' + config.key, 'Content-Type': 'application/json', Accept: 'text/event-stream'},
      }, res => {
        if (settled) { res.destroy(); return; }
        response = res;
        if (res.statusCode !== 200) return settle(httpError(res.statusCode));
        if (!(res.headers['content-type'] || '').includes('text/event-stream')) return settle(Error('供应商未返回流式响应，请检查所选模型是否支持流式输出'));
        res.setEncoding('utf8'); progress('waiting', true);
        res.on('data', chunk => {
          if (settled) return;
          wireBytes += Buffer.byteLength(chunk);
          // Wire overhead/heartbeats are not retained output and must not limit a long stream.
          buffer += chunk;
          let index;
          while (!settled && (index = buffer.indexOf('\n')) >= 0) {
            const value = buffer.slice(0, index).replace(/\r$/, ''); buffer = buffer.slice(index + 1);
            if (Buffer.byteLength(value) > MAX_EVENT_BYTES) return settle(Error('模型单行流式消息超过 1 MB，响应格式异常；已有报告保留'));
            line(value);
          }
          if (!settled && Buffer.byteLength(buffer) > MAX_EVENT_BYTES) settle(Error('模型流式消息缺少分隔或超过 1 MB；已有报告保留'));
        });
        res.on('end', () => { if (!settled) { if (buffer) line(buffer.replace(/\r$/, '')); event(); if (!settled) complete(); } });
        res.on('error', () => settle(Error('生成过程中连接中断；未保存不完整结果，不会自动重试')));
        res.on('aborted', () => settle(Error('供应商中断了生成连接；未保存不完整结果，不会自动重试')));
      });
      req.on('error', () => settle(signal?.aborted ? cancelled() : Error('无法连接硅基流动或连接已中断；请检查网络或供应商状态，不会自动重试')));
      req.end(JSON.stringify({...body, stream: true}));
    } catch { settle(Error('无法建立模型连接，不会自动重试')); }
  });
}
module.exports = {streamCompletion, cancelled};
