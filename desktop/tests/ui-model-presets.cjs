const {chromium}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict'),path=require('node:path');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});
 try{for(const width of [1220,980]){
  const page=await browser.newPage({viewport:{width,height:840}});
  await page.addInitScript(()=>{let user=null,config={configured:false,model:''};window.calls={list:0,save:[],summary:0};
   window.cine={onEvent:()=>{},state:async()=>({user,tasks:[]}),updateState:async()=>({status:'idle',currentVersion:'2.0.1'}),modelStatus:async()=>config,modelList:async()=>{window.calls.list++;return ['test/custom','deepseek-ai/DeepSeek-V3.2'];},modelSave:async input=>{window.calls.save.push(input);config={configured:true,model:input.model};return config;},modelClear:async()=>{config={configured:false,model:''};},summarize:async()=>window.calls.summary++};
   window.signIn=()=>{user={id:'test',displayName:'测试用户'};};window.restoreCustom=()=>{config={configured:true,model:'saved/legacy'};};
  });
  await page.goto('file:///'+path.resolve(__dirname,'../src/index.html').replaceAll('\\','/'));
  await page.locator('#nav-settings').click();assert.equal(await page.locator('.model-card').count(),4);
  await page.getByRole('button',{name:'Kimi K2.6 Moonshot'}).click();assert.equal(await page.locator('#model-preset').inputValue(),'Pro/moonshotai/Kimi-K2.6');
  assert.equal(await page.locator('#load-models').isDisabled(),true);assert.equal(await page.evaluate(()=>window.calls.list),0);
  await page.evaluate(async()=>{window.signIn();await refresh();});await page.locator('#nav-settings').click();
  await page.getByRole('button',{name:'GLM 5.1 智谱'}).click();await page.locator('#model-key').fill('test-key-not-real');await page.locator('#save-settings').click();
  assert.equal(await page.locator('#model-key').inputValue(),'');assert.equal(await page.evaluate(()=>window.calls.save[0].model),'Pro/zai-org/GLM-5.1');
  await page.locator('#load-models').click();assert.equal(await page.locator('#model-preset').inputValue(),'Pro/zai-org/GLM-5.1');
  assert.equal(await page.locator('#model-preset option[value="deepseek-ai/DeepSeek-V3.2"]').count(),1);
  await page.screenshot({path:path.resolve(__dirname,`../test-output/model-presets-${width}.png`),fullPage:true});
  await page.evaluate(()=>window.restoreCustom());await page.locator('#nav-settings').click();assert.equal(await page.locator('#model-id').inputValue(),'saved/legacy');assert.equal(await page.locator('#custom-model').isVisible(),true);
  await page.locator('#clear-settings').click();assert.equal(await page.locator('#load-models').isDisabled(),true);
  assert.equal(await page.evaluate(()=>window.calls.summary),0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.close();
 }}finally{await browser.close();}
 console.log('Offline model choices, no-key browsing, provider-ID mapping, legacy model, sync preservation and no generation: PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
