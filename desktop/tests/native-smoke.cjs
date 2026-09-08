const {_electron}=require(process.env.CINE_PLAYWRIGHT||'playwright');const path=require('node:path');const fs=require('node:fs/promises');const assert=require('node:assert/strict');
(async()=>{
 const folder=path.resolve(__dirname,'../test-output/native');await fs.mkdir(folder,{recursive:true});
 const wrapper=path.join(folder,'entry.cjs');
 await fs.writeFile(wrapper,`const {app,shell}=require('electron');app.setPath('userData',${JSON.stringify(path.join(folder,'session'))});app.setAsDefaultProtocolClient=()=>true;shell.openExternal=async url=>{global.lastExternal=url;};app.on('browser-window-created',(_,win)=>win.hide());require(${JSON.stringify(path.resolve(__dirname,'../src/main.cjs'))});`);
 const env={...process.env};delete env.ELECTRON_RUN_AS_NODE;
 const electron=await _electron.launch({executablePath:path.resolve(__dirname,'../node_modules/electron/dist/electron.exe'),args:[wrapper],env});
 try{
  const page=await electron.firstWindow();await page.getByRole('button',{name:/登录 LycheeAILab/}).waitFor();
  const secure=await electron.evaluate(({BrowserWindow})=>{const p=BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();return{sandbox:p.sandbox,contextIsolation:p.contextIsolation,nodeIntegration:p.nodeIntegration};});
  assert.deepEqual(secure,{sandbox:true,contextIsolation:true,nodeIntegration:false});
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  await page.locator('#login').click();await page.getByText('请在浏览器完成 Lab 授权').waitFor();
  const external=await electron.evaluate(()=>global.lastExternal);assert.equal(new URL(external).origin,'https://lab.lycheeai.com.cn');assert.equal(new URL(external).searchParams.get('codeChallengeMethod'),'S256');
  await page.screenshot({path:path.join(folder,'native.png')});
 }finally{await electron.close();}
 console.log('Native Electron startup, isolated preload/IPC, sandbox, and browser authorization URL passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
