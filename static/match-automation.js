/* One native workflow: strong matches -> ChatGPT -> approved preparation queue. */
window.MatchAutomation=(()=>{
 let button,panel,state={},busy=false,stopRequested=false,refreshing=false,recordsSignature=null;
 const text=(zh,fr)=>Locale.language==='zh'?zh:fr;
 function paint(){
  if(!panel)return;
  const active=['starting','running'].includes(state.phase);
  button.disabled=busy||active;
  const strong=allJobs.filter(job=>job.decision==='keep').length;
  button.textContent=active?text(`批量处理中 ${state.completed||0}/${state.total||strong}`,`Traitement en lot ${state.completed||0}/${state.total||strong}`):['blocked','stopped','interrupted'].includes(state.phase)?text('继续 / 重试批量处理','Reprendre le traitement en lot'):text(`批量处理高度匹配岗位（${strong}）`,`Traiter les bons résultats en lot (${strong})`);
  panel.replaceChildren();
  const title=document.createElement('strong');
  title.textContent=text('高度匹配 → ChatGPT 再审 → 通过后加入申请队列','Bons résultats → revue ChatGPT → file après validation');
  const note=document.createElement('p');
  const phases={idle:text('扫描完成后自动继续，也可以处理已有岗位。','La revue suit le scan. Vous pouvez aussi traiter les offres déjà enregistrées.'),starting:text('正在启动…','Démarrage…'),running:text('正在复核','Revue en cours'),done:text('本轮已完成','Lot terminé'),blocked:text('流程暂停，需要处理连接或资料问题','En pause : connexion ou informations à vérifier'),stopped:text('已停止','Arrêté'),interrupted:text('上次处理已中断，可继续','Le lot précédent a été interrompu. Vous pouvez reprendre.')};
  const failure=/No ChatGPT response|ChatGPT could not load this response/.test(state.error||'')?text('ChatGPT 没有返回有效回复。请检查平台 Chrome 中的登录和网络，然后点击“继续 / 重试批量处理”。','ChatGPT n’a pas répondu. Vérifiez la connexion dans Chrome dédié, puis reprenez le lot.'):state.error;
  note.textContent=stopRequested?text('停止请求已收到，当前复核结束后会停止。','Arrêt demandé : la revue en cours va se terminer.'):failure||phases[state.phase]||phases.idle;
  panel.append(title,note);
  if(state.current_title){const current=document.createElement('p');current.textContent=`${state.company||''} · ${state.current_title}`;panel.append(current);}
  if(Number.isFinite(state.total)){
   const progress=document.createElement('progress');progress.max=Math.max(1,state.total);progress.value=state.completed||0;progress.setAttribute('aria-label',text('复核进度','Avancement de la revue'));panel.append(progress);
   const counts=document.createElement('p');counts.textContent=text(`已复核 ${state.completed||0}/${state.total} · 已入队 ${state.enqueued||0} · 不适合 ${state.skipped||0} · 信息不足 ${state.unresolved||0}`,`Revues ${state.completed||0}/${state.total} · En file ${state.enqueued||0} · Écartées ${state.skipped||0} · Incomplètes ${state.unresolved||0}`);panel.append(counts);
  }
  const missing=state.unresolved_available??state.unresolved;
  if(missing){
   const clarify=document.createElement('button');clarify.type='button';clarify.className='primary';clarify.disabled=busy||active;
   clarify.textContent=text(`让 ChatGPT 自动补全并再审（${missing}）`,`Faire compléter et réévaluer par ChatGPT (${missing})`);
   clarify.onclick=async()=>{busy=true;paint();try{state=await requestJson('/api/matches/automation?mode=clarify',{method:'POST'});}catch(error){state={...state,phase:'blocked',error:error.message};}finally{busy=false;paint();}};panel.append(clarify);
   const gaps=document.createElement('button');gaps.type='button';gaps.textContent=text(`查看缺少什么 / 补全信息（${missing}）`,`Voir les informations manquantes (${missing})`);gaps.onclick=()=>ReviewGaps.open();panel.append(gaps);
  }
  if(active){const stop=document.createElement('button');stop.type='button';stop.textContent=text('停止复核','Arrêter la revue');stop.disabled=stopRequested;stop.onclick=async()=>{stopRequested=true;paint();try{await requestJson('/api/matches/automation/stop',{method:'POST'});await refresh();}catch(error){stopRequested=false;note.textContent=error.message;}};panel.append(stop);}
  const queue=document.createElement('button');queue.type='button';queue.textContent=text('查看申请队列 →','Voir la file →');queue.onclick=()=>WorkspaceMenu.navigate('pipeline');panel.append(queue);
 }
 async function refresh(){
  if(!panel||document.hidden||refreshing)return;
  refreshing=true;
  try{state=await requestJson('/api/matches/automation');if(!['starting','running'].includes(state.phase))stopRequested=false;paint();
   const next=JSON.stringify([state.phase,state.completed,state.enqueued,state.unresolved_available,state.error]);
   const changed=recordsSignature!==null&&recordsSignature!==next;recordsSignature=next;
   if(changed)await load();
   await window.ReviewGaps?.refresh();
  }
  catch{state={phase:'blocked',error:text('后台尚未更新：请关闭旧后台，再用 Dashboard 快捷方式启动。','Redémarrez l’ancien serveur avec le raccourci Dashboard pour charger ce flux.')};paint();}
  finally{refreshing=false;}
 }
 function init(actions){
  button=document.createElement('button');button.type='button';button.className='primary';button.id='reviewMatchesBtn';actions.append(button);
  panel=document.createElement('section');panel.id='matchAutomationStatus';panel.className='match-automation';panel.setAttribute('role','status');panel.setAttribute('aria-live','polite');
  document.getElementById('jobsView').querySelector('header').after(panel);
  button.onclick=async()=>{busy=true;paint();try{state=await requestJson('/api/matches/automation',{method:'POST'});await load();}catch(error){state={phase:'blocked',error:error.message};}finally{busy=false;paint();}};
  document.addEventListener('localechange',paint);document.addEventListener('visibilitychange',refresh);setInterval(refresh,4000);refresh();
 }
 return {init,refresh,paint};
})();
