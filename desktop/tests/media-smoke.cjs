// Explicit runtime integration check: node tests/media-smoke.cjs
const {spawn}=require('node:child_process');const fs=require('node:fs/promises');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../test-output/media'),runtime=path.resolve(__dirname,'../runtime');
function run(command,args,input,env=process.env){return new Promise((resolve,reject)=>{const child=spawn(command,args,{windowsHide:true,env,stdio:['pipe','pipe','pipe']});let out='',err='';child.stdout.on('data',d=>out+=d);child.stderr.on('data',d=>err+=d);child.on('error',reject);child.on('close',code=>resolve({code,out,err}));child.stdin.end(input);});}
(async()=>{await fs.mkdir(root,{recursive:true});const source=path.join(root,'示例视频.mp4');
  let result=await run(path.join(runtime,'ffmpeg.exe'),['-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-c:a','aac',source]);assert.equal(result.code,0,result.err);
  const worker=path.join(runtime,'cine-media/cine-media.exe');
  const env={...process.env,PATH:runtime+path.delimiter+path.join(process.env.SystemRoot,'System32'),PYTHONUTF8:'1'};
  result=await run(worker,[],JSON.stringify({video:source,outputDir:path.join(root,'prepared')}),env);assert.equal(result.code,0,result.err);
  const manifest=JSON.parse(await fs.readFile(JSON.parse(result.out).manifest,'utf8'));assert.equal(manifest.chunks.length,1);assert.equal(manifest.source.has_audio,true);assert.ok(manifest.source.duration_seconds>=4);assert.ok((await fs.stat(manifest.chunks[0].path)).size<12*1024*1024);
  result=await run(worker,[],JSON.stringify({url:'https://example.com/invalid',outputDir:path.join(root,'invalid-link')}),env);assert.notEqual(result.code,0);assert.match(result.err,/Douyin/);
  result=await run(worker,['--douk','https://example.com/invalid',path.join(root,'invalid.mp4')],undefined,env);assert.notEqual(result.code,0);assert.doesNotMatch(result.err,/ModuleNotFoundError/);
  console.log('Packaged runtime: Chinese path, video+audio probe, proxy encoding, no Python/FFmpeg on PATH, and invalid-link rejection passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
