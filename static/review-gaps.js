/* Clarify once, retain candidate facts, then resume the existing native workflow. */
window.ReviewGaps=(()=>{
 const t=(zh,fr)=>Locale.language==='zh'?zh:fr;
 let dialog;
 async function open(){
  if(!dialog){dialog=document.createElement('dialog');dialog.className='review-gaps-dialog';document.body.append(dialog);dialog.addEventListener('close',()=>dialog.replaceChildren());}
  if(!dialog.open)dialog.showModal();
  dialog.replaceChildren();
  const heading=document.createElement('h2');heading.textContent=t('补全复核所需信息','Compléter les informations de revue');
  const close=document.createElement('button');close.textContent=t('关闭','Fermer');close.onclick=()=>dialog.close();
  const note=document.createElement('p');note.textContent=t('先让 ChatGPT 自动查证下面的问题。只有系统仍无法确认、且你本人知道的事实，才需要手动补充。','Laissez d’abord ChatGPT rechercher les réponses. Complétez uniquement les faits personnels qui restent inconnus.');
  dialog.append(heading,close,note);
  const auto=document.createElement('button');auto.className='primary';auto.textContent=t('让 ChatGPT 自动补全并再审','Faire compléter et réévaluer par ChatGPT');
  auto.onclick=async()=>{auto.disabled=true;try{await requestJson('/api/matches/automation?mode=clarify',{method:'POST'});dialog.close();await MatchAutomation.refresh();}catch(error){note.textContent=error.message;auto.disabled=false;}};dialog.append(auto);
  try{
   const data=await requestJson('/api/matches/gaps');
   const status=document.createElement('p');status.setAttribute('role','status');dialog.append(status);
   if(!data.items.length){status.textContent=t('当前没有待补全的复核结果。连接或回复异常请使用批量处理的重试按钮。','Aucune clarification en attente. Pour une erreur de connexion ou de réponse, reprenez le lot.');return;}
   const kinds={candidate:t('你可以补充的个人信息','Information personnelle'),posting:t('需从岗位原页或招聘方确认','À vérifier auprès de l’employeur'),form:t('仅限本次表单的问题','Question propre au formulaire'),evaluation:t('评分回复不完整，需系统重审','Évaluation incomplète : relancer la revue'),unknown:t('旧结果：请先判断由谁确认','Ancien résultat : identifier qui peut répondre')};
   for(const job of data.items){
    const section=document.createElement('section');section.className='review-gap-job';
    const title=document.createElement('h3');title.textContent=`${job.company} · ${job.title}`;
    const summary=document.createElement('p');summary.textContent=job.review_summary;
    const link=document.createElement('a');link.textContent=t('查看原始岗位 ↗','Voir l’offre originale ↗');
    if(/^https?:\/\//i.test(job.url)){link.href=job.url;link.target='_blank';link.rel='noopener noreferrer';}
    section.append(title,summary,link);
    for(const finding of job.research_findings||[]){
     const p=document.createElement('p');p.textContent=`${t('系统查证','Recherche')} · ${finding.answer||''}`;
     if(/^https?:\/\//i.test(finding.source_url||'')){const a=document.createElement('a');a.href=finding.source_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=t(' 查看来源 ↗',' Source ↗');p.append(a);}
     section.append(p);
    }
    if(!job.questions.length){const p=document.createElement('p');p.textContent=t('旧回复没有提供具体问题，请重试批量处理以获取明确缺项。','L’ancienne réponse ne précise pas les questions. Relancez la revue.');section.append(p);}
    for(const gap of job.questions){
     const field=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=kinds[gap.kind]||kinds.unknown;field.append(legend);
     const question=document.createElement('p');question.textContent=gap.question;field.append(question);
     for(const value of [gap.reason,gap.evidence])if(value){const p=document.createElement('p');p.className='small';p.textContent=value;field.append(p);}
     if(gap.kind!=='evaluation'){
      const previous=data.answers.find(a=>a.question===gap.question&&(a.job_id===job.id||a.reusable));
      const input=document.createElement('textarea');input.rows=3;input.maxLength=4000;input.value=previous?.answer||'';input.setAttribute('aria-label',gap.question);field.append(input);
      const label=document.createElement('label'),reuse=document.createElement('input');reuse.type='checkbox';reuse.checked=previous?.reusable===true;reuse.disabled=!['candidate','unknown'].includes(gap.kind);label.append(reuse,document.createTextNode(t('这是我的个人事实，保存到当前档案，今后同类审核可复用（不代表同意网站条款）','Fait personnel à conserver et réutiliser dans les revues (hors consentements)')));field.append(label);
      const save=document.createElement('button');save.textContent=t('保存这条信息','Enregistrer cette réponse');save.onclick=async()=>{save.disabled=true;try{await requestJson('/api/matches/gaps/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidate_id:data.candidate_id,job_id:job.id,question:gap.question,answer:input.value,reusable:reuse.checked})});loadedProfile=null;status.textContent=t('已保存到当前个人档案。补完后点击底部“继续批量复核”。','Enregistré dans le profil actuel. Reprenez la revue une fois les réponses complétées.');}catch(error){status.textContent=error.message;}finally{save.disabled=false;}};field.append(save);
     }
     section.append(field);
    }
    dialog.append(section);
   }
   const resume=document.createElement('button');resume.className='primary';resume.textContent=t('继续批量复核','Reprendre la revue en lot');resume.onclick=async()=>{resume.disabled=true;try{await requestJson('/api/matches/automation',{method:'POST'});dialog.close();await MatchAutomation.refresh();}catch(error){status.textContent=error.message;resume.disabled=false;}};dialog.append(resume);
  }catch(error){note.textContent=error.message;}
 }
 return {open};
})();
