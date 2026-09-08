const {chromium}=require(process.env.CINE_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{for(const [width,height] of [[1220,840],[980,680]]){
  const page=await browser.newPage({viewport:{width,height}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{let listener;window.cine={state:async()=>({tasks:[],user:null}),onEvent:fn=>listener=fn,updateState:async()=>({status:'idle',currentVersion:'2.0.0'})};window.emitUpdate=state=>listener({type:'update',state:{currentVersion:'2.0.0',version:'2.0.1',...state}});});
  await page.goto('file:///'+path.resolve(__dirname,'../src/index.html').replaceAll('\\','/'));
  assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).colorScheme),'light');
  assert.equal((await page.locator('#nav-updates').innerText()).trim(),'');
  await page.locator('#nav-updates').click();assert.equal(await page.locator('#nav-updates').getAttribute('aria-expanded'),'true');
  const panel=await page.locator('#update-panel').boundingBox();assert.ok(panel.x>=0&&panel.y>=0&&panel.x+panel.width<=width&&panel.y+panel.height<=height);
  for(const status of ['checking','current','downloading','ready','error','disabled']){
   await page.evaluate(status=>window.emitUpdate({status,percent:47}),status);
   assert.equal(await page.locator('#nav-updates').getAttribute('data-status'),status);
   assert.equal(await page.locator('#install-update').isVisible(),status==='ready');
   assert.equal(await page.locator('#update-progress').isVisible(),status==='downloading');
   assert.equal(await page.locator('#update-dot').isVisible(),['ready','error'].includes(status));
  }
  await page.evaluate(()=>window.emitUpdate({status:'downloading',percent:47}));
  await page.screenshot({path:path.resolve(__dirname,`../test-output/update-panel-${width}.png`)});
  await page.keyboard.press('Escape');assert.equal(await page.locator('#update-panel').isVisible(),false);
  assert.equal(await page.locator('#nav-updates').evaluate(e=>e===document.activeElement),true);
  await page.locator('#nav-updates').click();await page.locator('#location').click();assert.equal(await page.locator('#update-panel').isVisible(),false);
  assert.equal(await page.locator('#import-view').isVisible(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.deepEqual(errors,[]);await page.close();
 }}finally{await browser.close();}
 console.log('Light theme, icon-only update entry, six update states, panel bounds, Escape/outside close: PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
