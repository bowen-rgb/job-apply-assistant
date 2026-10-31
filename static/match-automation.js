/* One native workflow: strong matches -> ChatGPT -> approved preparation queue. */
window.MatchAutomation=(()=>{
 let button,panel,state={},busy=false,stopRequested=false,refreshing=false,recordsSignature=null,recordsRefreshing=false,recordsPending=false;
 const text=(zh,fr)=>Locale.language==='zh'?zh:fr;
 const groupLabels=()=>({pending:text('待初审','À évaluer'),reviewing:text('审核中','En revue'),needs_information:text('待补全','À compléter'),approved:text('已通过待入队','Validées à mettre en file'),queued:text('申请队列','En file'),submitted:text('已投递','Envoyées'),not_suitable:text('复核不适合','Écartées'),errors:text('审核异常','Erreurs'),inactive:text('已退出流程','Hors processus')});
 function paint(){
  if(!panel)return;
  const active=['starting','running'].includes(state.phase);
  button.disabled=busy||active;
  const strong=state.inventory?.total??allJobs.filter(job=>job.decision==='keep').length;
  const available=state.review_available??strong;
  const scope=({clarify:text('旧缺项补全','Clarifications'),research:text('公开信息查证与复核','Recherche et revue'),rereview:text('补充后重新审核','Réévaluation après complément')})[state.mode]||text('待审核岗位','Offres à évaluer');
  button.textContent=active?`${scope} ${state.completed||0}/${state.total||available}`:state.actions?text(`初审 / 重试可处理岗位（${available}）`,`Évaluer / réessayer les offres prêtes (${available})`):['blocked','stopped','interrupted'].includes(state.phase)?text('继续 / 重试批量处理','Reprendre le traitement en lot'):text(`批量处理全部高度匹配岗位（${strong}）`,`Traiter tous les bons résultats (${strong})`);
  panel.replaceChildren();
  const title=document.createElement('strong');
  title.textContent=text('高度匹配 → ChatGPT 再审 → 通过后加入申请队列','Bons résultats → revue ChatGPT → file après validation');
  const note=document.createElement('p');
  const phases={idle:text('扫描完成后自动继续，也可以处理已有岗位。','La revue suit le scan. Vous pouvez aussi traiter les offres déjà enregistrées.'),starting:text('正在启动…','Démarrage…'),running:text('正在复核','Revue en cours'),done:text('本轮已完成','Lot terminé'),blocked:text('流程暂停，需要处理连接或资料问题','En pause : connexion ou informations à vérifier'),stopped:text('已停止','Arrêté'),interrupted:text('上次处理已中断，可继续','Le lot précédent a été interrompu. Vous pouvez reprendre.')};
  const failure=/No ChatGPT response|ChatGPT could not load this response/.test(state.error||'')?text('ChatGPT 没有返回有效回复。已进行一次自动重试，进度已保留；请检查专用 Chrome 中的回复、登录和网络，再重试对应任务。','ChatGPT n’a pas répondu après une nouvelle tentative. La progression est conservée ; vérifiez Chrome dédié puis relancez l’action.'):state.error;
  note.textContent=stopRequested?text('停止请求已收到，当前复核结束后会停止。','Arrêt demandé : la revue en cours va se terminer.'):failure||phases[state.phase]||phases.idle;
  panel.append(title,note);
  if(state.inventory){
   const total=document.createElement('p');total.textContent=text(`规则初筛高度匹配共 ${strong} 条，以下阶段互不重复，合计等于总数。`,`Présélection : ${strong} offres. Les étapes ci-dessous sont exclusives et leur somme égale le total.`);panel.append(total);
   const groups=document.createElement('div');groups.className='review-inventory';
   for(const [key,label] of Object.entries(groupLabels())){const metric=document.createElement('button');metric.type='button';metric.dataset.reviewGroup=key;metric.textContent=`${label} ${state.inventory.counts[key]||0}`;metric.onclick=()=>selectApplicationView('workflow:'+key);groups.append(metric);}panel.append(groups);
   const cumulative=state.inventory.cumulative;
   if(cumulative){
    const totals=document.createElement('p');totals.dataset.reviewCumulative='';
    const reviewed=document.createElement('button');reviewed.type='button';reviewed.dataset.reviewGroup='reviewed';reviewed.textContent=text(`累计已复核 ${cumulative.reviewed} 条（岗位去重）`,`Offres déjà évaluées : ${cumulative.reviewed} (uniques)`);reviewed.onclick=()=>selectApplicationView('workflow:reviewed');totals.append(reviewed);
    totals.append(document.createTextNode(text(` · 高度匹配已入队 ${cumulative.queued} · 不适合 ${cumulative.not_suitable} · 待补全 ${cumulative.needs_information}`,` · Présélection en file ${cumulative.queued} · Écartées ${cumulative.not_suitable} · À compléter ${cumulative.needs_information}`)));
    const allQueue=document.createElement('button');allQueue.type='button';allQueue.textContent=text(`全申请队列（${state.inventory.queue_total}）`,`Toute la file (${state.inventory.queue_total})`);allQueue.onclick=()=>WorkspaceMenu.navigate('pipeline');totals.append(allQueue);panel.append(totals);
   }
  }
  const scopeNote=document.createElement('p');scopeNote.className='small';scopeNote.textContent=['research','rereview'].includes(state.mode)?text(`当前批次：${scope} ${state.total||0} 条；只处理本批目标。`,`Lot actuel : ${scope}, ${state.total||0} offres ; seules ces cibles seront traitées.`):state.mode==='clarify'?text(`当前子批次：旧缺项补全 ${state.total||0} 条；其余 ${state.inventory?.counts?.pending??'—'} 条待初审会随后自动继续。`,`Lot actuel : ${state.total||0} clarifications ; ${state.inventory?.counts?.pending??'—'} offres encore non évaluées suivront automatiquement.`):state.continued_from_clarify?text('旧缺项补全阶段已结束，正在继续其余岗位初审。','Clarifications terminées, poursuite des autres évaluations.'):text('初审会跳过尚未补齐个人事实或需要专门查证的岗位。','La revue initiale exclut les offres en attente de faits personnels ou de recherche dédiée.');panel.append(scopeNote);
  if(state.current_title){const current=document.createElement('p');current.textContent=`${state.company||''} · ${state.current_title}`;panel.append(current);}
  if(Number.isFinite(state.total)){
   const progress=document.createElement('progress');progress.max=Math.max(1,state.total);progress.value=state.completed||0;progress.setAttribute('aria-label',text('复核进度','Avancement de la revue'));panel.append(progress);
   const counts=document.createElement('p');counts.dataset.reviewBatch='';counts.textContent=state.inventory?.cumulative?text(`本批已处理 ${state.completed||0}/${state.total} · 本批入队 ${state.enqueued||0} · 本批不适合 ${state.skipped||0} · 本批待补全 ${state.unresolved||0}`,`Ce lot : ${state.completed||0}/${state.total} · Mises en file ${state.enqueued||0} · Écartées ${state.skipped||0} · À compléter ${state.unresolved||0}`):text(`已复核 ${state.completed||0}/${state.total} · 已入队 ${state.enqueued||0} · 不适合 ${state.skipped||0} · 信息不足 ${state.unresolved||0}`,`Revues ${state.completed||0}/${state.total} · En file ${state.enqueued||0} · Écartées ${state.skipped||0} · Incomplètes ${state.unresolved||0}`);panel.append(counts);
   if(state.inventory?.cumulative){const remaining=document.createElement('p');remaining.className='small';remaining.textContent=text(`本批剩余 ${Math.max(0,state.total-(state.completed||0))} 条（包含正在复核的岗位）。累计覆盖当前档案全部岗位，按岗位去重；重审不会重复增加。`,`Reste dans ce lot : ${Math.max(0,state.total-(state.completed||0))}, revue en cours incluse. Le cumul couvre toutes les offres du profil, sans doublons lors des réévaluations.`);panel.append(remaining);}
  }
  const missing=state.unresolved_available??state.unresolved;
  if(state.actions){
   const personal=state.actions.personal_input?.count||0,research=state.actions.public_research?.count||0,ready=state.actions.rereview?.count||0;
   const action=(label,mode,count)=>{const item=document.createElement('button');item.type='button';item.textContent=label;item.disabled=busy||active||!count;item.onclick=()=>startAction(mode);panel.append(item);};
   action(text(`查证公开岗位信息并复核（${research}）`,`Rechercher les informations publiques et réévaluer (${research})`),'research',research);
   const facts=document.createElement('button');facts.type='button';facts.textContent=text(`需要你补充个人信息（${personal}）`,`Faits personnels à compléter (${personal})`);facts.disabled=!personal;facts.onclick=()=>ReviewGaps.open('personal');panel.append(facts);
   action(text(`重新审核已补充 / 待重审岗位（${ready}）`,`Réévaluer les offres complétées / prêtes (${ready})`),'rereview',ready);
   const explanation=document.createElement('p');explanation.className='small';explanation.textContent=text('按钮统计当前仍有缺项的岗位，不是本批剩余数；同一岗位可能同时缺个人事实和公开信息。个人事实由你确认，系统不会代填。','Les boutons comptent les offres encore incomplètes, pas le reste du lot. Une offre peut nécessiter les deux actions. Vous seul confirmez vos faits personnels.');panel.append(explanation);
   if(missing){const all=document.createElement('button');all.type='button';all.textContent=text('查看全部复核缺项','Voir toutes les questions de revue');all.onclick=()=>ReviewGaps.open();panel.append(all);}
  }else if(missing){
   const clarify=document.createElement('button');clarify.type='button';clarify.className='primary';clarify.disabled=busy||active;
   clarify.textContent=text(`让 ChatGPT 自动补全并再审（${missing}）`,`Faire compléter et réévaluer par ChatGPT (${missing})`);
   clarify.onclick=async()=>{busy=true;paint();try{state=await requestJson('/api/matches/automation?mode=clarify',{method:'POST'});}catch(error){state={...state,phase:'blocked',error:error.message};}finally{busy=false;paint();}};panel.append(clarify);
   const gaps=document.createElement('button');gaps.type='button';gaps.textContent=text(`查看缺少什么 / 补全信息（${missing}）`,`Voir les informations manquantes (${missing})`);gaps.onclick=()=>ReviewGaps.open();panel.append(gaps);
  }
  if(active){const stop=document.createElement('button');stop.type='button';stop.textContent=text('停止复核','Arrêter la revue');stop.disabled=stopRequested;stop.onclick=async()=>{stopRequested=true;paint();try{await requestJson('/api/matches/automation/stop',{method:'POST'});await refresh();}catch(error){stopRequested=false;note.textContent=error.message;}};panel.append(stop);}
  const queue=document.createElement('button');queue.type='button';queue.textContent=text('查看申请队列 →','Voir la file →');queue.onclick=()=>WorkspaceMenu.navigate('pipeline');panel.append(queue);
 }
 async function startAction(mode){busy=true;paint();try{state=await requestJson(`/api/matches/automation?mode=${mode}`,{method:'POST'});}catch(error){state={...state,phase:'blocked',error:error.message};}finally{busy=false;paint();}}
 async function refreshRecords(){
  recordsPending=true;if(recordsRefreshing)return;
  recordsRefreshing=true;
  try{while(recordsPending){recordsPending=false;await load();if(!document.getElementById('pipelineView').classList.contains('hidden'))await loadPipeline();}}
  catch(error){const note=document.createElement('p');note.textContent=text('岗位详情同步失败，将自动重试：','Synchronisation des détails interrompue : ')+error.message;panel.append(note);recordsPending=true;}
  finally{recordsRefreshing=false;}
 }
 async function refresh(){
  if(!panel||document.hidden||refreshing)return;
  refreshing=true;
  try{state=await requestJson('/api/matches/automation');if(!['starting','running'].includes(state.phase))stopRequested=false;paint();
   const next=JSON.stringify([state.snapshot_id,state.phase,state.completed,state.enqueued,state.unresolved_available,state.actions,state.error]);
   const changed=recordsSignature!==null&&recordsSignature!==next;recordsSignature=next;
   await window.ReviewGaps?.refresh(state.gaps);
   if(changed||recordsPending)void refreshRecords();
  }
  catch{state={phase:'blocked',error:text('后台尚未更新：请关闭旧后台，再用 Dashboard 快捷方式启动。','Redémarrez l’ancien serveur avec le raccourci Dashboard pour charger ce flux.')};paint();}
  finally{refreshing=false;}
 }
 function init(actions){
  button=document.createElement('button');button.type='button';button.className='primary';button.id='reviewMatchesBtn';actions.append(button);
  panel=document.createElement('section');panel.id='matchAutomationStatus';panel.className='match-automation';panel.setAttribute('role','status');panel.setAttribute('aria-live','polite');
  document.getElementById('jobsView').querySelector('header').after(panel);
  button.onclick=async()=>{busy=true;paint();try{state=await requestJson('/api/matches/automation',{method:'POST'});await load();}catch(error){state={phase:'blocked',error:error.message};}finally{busy=false;paint();}};
  document.addEventListener('localechange',paint);document.addEventListener('visibilitychange',refresh);setInterval(refresh,2000);refresh();
 }
 return {init,refresh,paint,hasLiveSnapshot:()=>!!state.gaps,matches:(id,group)=>(group==='reviewed'?state.inventory?.cumulative?.reviewed_job_ids:state.inventory?.job_ids?.[group])?.includes(id)===true,label:group=>group==='reviewed'?text('累计已复核','Offres déjà évaluées'):groupLabels()[group]||group};
})();
