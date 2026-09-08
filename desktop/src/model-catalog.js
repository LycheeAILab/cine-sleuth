// Verified against SiliconFlow's official release notes / usage guides on 2026-09-08.
// Catalog visibility never implies that the user's provider account has access or balance.
(function(root){
 const models=Object.freeze([
  {id:'deepseek-ai/DeepSeek-V4-Flash',name:'DeepSeek V4 Flash',family:'DeepSeek'},
  {id:'deepseek-ai/DeepSeek-V3.2',name:'DeepSeek V3.2',family:'DeepSeek'},
  {id:'Pro/moonshotai/Kimi-K2.6',name:'Kimi K2.6',family:'Moonshot'},
  {id:'Pro/zai-org/GLM-5.1',name:'GLM 5.1',family:'智谱'}
 ].map(Object.freeze));
 if(typeof module==='object'&&module.exports)module.exports=models;else root.cineModelCatalog=models;
})(globalThis);
