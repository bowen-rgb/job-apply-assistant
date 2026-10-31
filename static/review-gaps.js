/* Clarify once, retain candidate facts, then resume the existing native workflow. */
window.ReviewGaps=(()=>{
 const t=(zh,fr)=>Locale.language==='zh'?zh:fr;
 let dialog,timer,owner,signature='',epoch=0,inFlight=false,saving=0;
 const drafts=new Map();
 async function open(){
  if(!dialog){dialog=document.createElement('dialog');dialog.className='review-gaps-dialog';document.body.append(dialog);dialog.addEventListener('close',()=>{clearInterval(timer);timer=null;epoch++;owner=null;signature='';drafts.clear();dialog.replaceChildren();});}
  if(!dialog.open){epoch++;dialog.showModal();const loading=document.createElement('p');loading.textContent=t('正在读取最新复核结果…','Chargement des dernières revues…');dialog.append(loading);}
  await refresh();
  if(dialog.open&&!timer)timer=setInterval(refresh,3000);
 }
 async function refresh(){
  if(!dialog?.open||document.hidden||inFlight||saving)return;
  inFlight=true;const requestEpoch=epoch;
  try{
   const data=await requestJson('/api/matches/gaps');
   if(!dialog.open||requestEpoch!==epoch)return;
   if(owner&&owner!==data.candidate_id){dialog.close();return;}
   owner=data.candidate_id;
   dialog.querySelector('[data-sync-error]')?.remove();
   const next=JSON.stringify(data);if(next===signature)return;
   const scroll=dialog.scrollTop,active=document.activeElement;
   let focused;
   for(const field of dialog.querySelectorAll('fieldset[data-question]')){
    const input=field.querySelector('textarea');if(!input)continue;
    const key=JSON.stringify([field.closest('[data-job-id]').dataset.jobId,field.dataset.question]);
    if(field.dataset.dirty==='true')drafts.set(key,{value:input.value,reusable:field.querySelector('input[type=checkbox]').checked});
    if(input===active)focused={key,start:input.selectionStart,end:input.selectionEnd};
   }
   render(data);signature=next;
   for(const field of dialog.querySelectorAll('fieldset[data-question]')){
    const key=JSON.stringify([field.closest('[data-job-id]').dataset.jobId,field.dataset.question]),draft=drafts.get(key),input=field.querySelector('textarea');
    if(!input)continue;
    if(draft){input.value=draft.value;field.querySelector('input[type=checkbox]').checked=draft.reusable;field.dataset.dirty='true';}
    if(focused?.key===key){input.focus({preventScroll:true});input.setSelectionRange(focused.start,focused.end);}
   }
   dialog.scrollTop=scroll;
  }catch(error){if(dialog.open&&requestEpoch===epoch){let note=dialog.querySelector('[data-sync-error]');if(!note){note=document.createElement('p');note.dataset.syncError='';note.setAttribute('role','status');dialog.prepend(note);}note.textContent=t('同步失败，保留上次结果，正在自动重试：','Synchronisation interrompue, nouvelle tentative : ')+error.message;}}
  finally{inFlight=false;}
 }
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
 function render(data){
  dialog.replaceChildren();
  const heading=document.createElement('h2');heading.textContent=t('补全复核所需信息','Compléter les informations de revue');
  const close=document.createElement('button');close.textContent=t('关闭','Fermer');close.onclick=()=>dialog.close();
  const note=document.createElement('p');note.textContent=t('这里是 AI 审核提出的疑问，不代表招聘网站必填题或 HR 来信。系统先自动查证；可选疑问只作提醒。只有明确缺少的个人事实才需要你填写。','Ces questions proviennent de la revue IA, pas nécessairement du formulaire employeur ou des RH. Les points facultatifs restent des conseils ; seuls les faits personnels manquants demandent votre réponse.');
  dialog.append(heading,close,note);
  const auto=document.createElement('button');auto.className='primary';auto.textContent=t('让 ChatGPT 自动补全并再审','Faire compléter et réévaluer par ChatGPT');
  auto.onclick=async()=>{auto.disabled=true;try{await requestJson('/api/matches/automation?mode=clarify',{method:'POST'});dialog.close();await MatchAutomation.refresh();}catch(error){note.textContent=error.message;auto.disabled=false;}};dialog.append(auto);
  try{
   const status=document.createElement('p');status.setAttribute('role','status');dialog.append(status);
   if(!data.items.length){status.textContent=t('当前没有待补全的复核结果。连接或回复异常请使用批量处理的重试按钮。','Aucune clarification en attente. Pour une erreur de connexion ou de réponse, reprenez le lot.');return;}
   const kinds={candidate:t('AI 复核：缺少个人事实','Revue IA : fait personnel manquant'),posting:t('AI 复核疑问：系统查证，无需在这里填写','Question IA : recherche automatique'),form:t('实际申请表单中需处理的问题','Question du formulaire réel'),evaluation:t('评分回复不完整，需系统重审','Évaluation incomplète : relancer la revue'),unknown:t('旧 AI 审核疑问（非网站必填，等待自动重审）','Ancienne question IA : réévaluation automatique')};
   for(const job of data.items){
    const section=document.createElement('section');section.className='review-gap-job';section.dataset.jobId=String(job.id);
    const title=document.createElement('h3');title.textContent=`${job.company} · ${job.title}`;
    const summary=document.createElement('p');summary.textContent=job.review_summary;
    const link=document.createElement('a');link.textContent=t('查看原始岗位 ↗','Voir l’offre originale ↗');
    if(/^https?:\/\//i.test(job.url)){link.href=job.url;link.target='_blank';link.rel='noopener noreferrer';}
    section.append(title,summary,link);
    const updated=document.createElement('p');updated.className='small';updated.textContent=[
     job.processing?t('正在重新查证；以下为上次结果，完成后自动替换。','Nouvelle revue en cours ; le résultat précédent sera remplacé automatiquement.'):
     job.review_verdict==='ERROR'?t('重审未完成，以下为上次结果；请重试自动处理。','Revue interrompue ; résultat précédent conservé. Relancez le traitement.'):
     job.legacy?t('历史审核结果，等待按新规则重审。','Ancienne revue en attente de réévaluation.'):
     t('最新审核结果','Dernière revue'),
     job.reviewed_at?`${t('审核时间','Revue du')} ${job.reviewed_at} UTC`:''
    ].filter(Boolean).join(' · ');section.append(updated);
    for(const finding of job.research_findings||[]){
     const p=document.createElement('p');p.textContent=`${t('系统查证','Recherche')} · ${finding.answer||''}`;
     if(/^https?:\/\//i.test(finding.source_url||'')){const a=document.createElement('a');a.href=finding.source_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=t(' 查看来源 ↗',' Source ↗');p.append(a);}
     section.append(p);
    }
    if(!job.questions.length){const p=document.createElement('p');p.textContent=t('旧回复没有提供具体问题，请重试批量处理以获取明确缺项。','L’ancienne réponse ne précise pas les questions. Relancez la revue.');section.append(p);}
    for(const gap of job.questions){
     const field=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=kinds[gap.kind]||kinds.unknown;field.append(legend);field.dataset.question=gap.question;
     const question=document.createElement('p');question.textContent=gap.question;field.append(question);
     for(const value of [gap.reason,gap.evidence])if(value){const p=document.createElement('p');p.className='small';p.textContent=value;field.append(p);}
     if(gap.kind==='candidate'&&!job.processing){
      field.addEventListener('input',()=>{field.dataset.dirty='true';});field.addEventListener('change',()=>{field.dataset.dirty='true';});
      const previous=data.answers.find(a=>a.question===gap.question&&(a.job_id===job.id||a.reusable));
      const input=document.createElement('textarea');input.rows=3;input.maxLength=4000;input.value=previous?.answer||'';input.setAttribute('aria-label',gap.question);field.append(input);
      const label=document.createElement('label'),reuse=document.createElement('input');reuse.type='checkbox';reuse.checked=previous?.reusable===true;reuse.disabled=!['candidate','unknown'].includes(gap.kind);label.append(reuse,document.createTextNode(t('这是我的个人事实，保存到当前档案，今后同类审核可复用（不代表同意网站条款）','Fait personnel à conserver et réutiliser dans les revues (hors consentements)')));field.append(label);
      const save=document.createElement('button');save.textContent=t('保存这条信息','Enregistrer cette réponse');save.onclick=async()=>{save.disabled=true;saving++;try{await requestJson('/api/matches/gaps/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidate_id:data.candidate_id,job_id:job.id,question:gap.question,answer:input.value,reusable:reuse.checked})});field.dataset.dirty='false';drafts.delete(JSON.stringify([String(job.id),gap.question]));loadedProfile=null;status.textContent=t('已保存到当前个人档案。补完后点击底部“继续批量复核”。','Enregistré dans le profil actuel. Reprenez la revue une fois les réponses complétées.');}catch(error){status.textContent=error.message;}finally{save.disabled=false;saving--;}};field.append(save);
     }
     section.append(field);
    }
    dialog.append(section);
   }
   const resume=document.createElement('button');resume.className='primary';resume.textContent=t('继续批量复核','Reprendre la revue en lot');resume.onclick=async()=>{resume.disabled=true;try{await requestJson('/api/matches/automation',{method:'POST'});dialog.close();await MatchAutomation.refresh();}catch(error){status.textContent=error.message;resume.disabled=false;}};dialog.append(resume);
  }catch(error){note.textContent=error.message;}
 }
 return {open,refresh};
})();
