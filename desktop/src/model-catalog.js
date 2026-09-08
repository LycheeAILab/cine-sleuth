// Verified against SiliconFlow's official release notes / usage guides on 2026-09-08.
// Catalog visibility never implies that the user's provider account has access or balance.
(function(root){
 const models=Object.freeze([
  {id:'zai-org/GLM-5.3',name:'GLM 5.3',family:'智谱'},
  {id:'deepseek-ai/DeepSeek-V4-Flash',name:'DeepSeek V4 Flash',family:'DeepSeek'},
  {id:'deepseek-ai/DeepSeek-V4-Pro',name:'DeepSeek V4 Pro',family:'DeepSeek'},
  {id:'Pro/moonshotai/Kimi-K2.6',name:'Kimi K2.6',family:'Moonshot'},
  {id:'MiniMaxAI/MiniMax-M2.5',name:'MiniMax M2.5',family:'MiniMax',notice:'平台公告：MiniMax M2.5 将于 2026-09-11 下线，请在届时选择其他模型。'}
 ].map(Object.freeze));
 if(typeof module==='object'&&module.exports)module.exports=models;else root.cineModelCatalog=models;
})(globalThis);
