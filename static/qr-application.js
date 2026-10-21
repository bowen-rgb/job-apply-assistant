/* Import desk: permanent add control, independent import tickets, saved applications.
   Ant Upload controlled lists + Refactoring UI §§2.1,2.8,3.6,8.4; native JS only.
   Import/preview/navigation NEVER authorize sending. The existing start endpoint does. */
window.QRApplication=(()=>{
 let dialog,current=null,items=[],tickets=[],pumping=false,actionBusy=false,message='',timer=null,filter='all',ticketSequence=0,historyExpanded=null;
 const images=new Map(),pendingSelections=new Map(),t=s=>Locale.t(s);
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
 const host=url=>{try{return new URL(url).hostname;}catch{return '';}};
 const errors={qr_image_size:'Choisissez une image de moins de 8 Mo.',qr_image_pixels:'L’image est trop grande. Recadrez le QR code.',qr_image_format:'Utilisez une image PNG, JPG, WebP ou BMP.',qr_no_code:'Aucun QR code lisible. Recadrez le code ou utilisez une image plus nette.',qr_mobile_only:'Ce code nécessite une application mobile. Ouvrez-le sur votre téléphone et importez le lien web de candidature.',qr_not_web_form:'Ce lien ne mène pas à une page web de candidature.',qr_expired:'Ce QR code a expiré. Demandez un nouveau code au recruteur.',qr_no_resume:'Ajoutez un CV dans le profil avant de postuler.',qr_company_required:'Indiquez le nom de l’entreprise.',qr_busy:'Une tâche est déjà en cours. Terminez-la ou arrêtez-la avant cette candidature.',qr_already_started:'Cette candidature a déjà été lancée. Vérifiez son état avant de réessayer.',qr_existing_application:'Ce poste existe déjà ou attend une vérification. Consultez sa candidature dans la file.',qr_materials_changed:'Les documents ou le profil ont changé. Importez à nouveau le QR code.',qr_letter_not_checked:'La lettre doit être régénérée et vérifiée avant l’envoi.',qr_not_found:'Cette demande appartient à un autre profil ou n’existe plus.',qr_context_incomplete:'Identifiez l’entreprise, le poste et les missions avant de postuler.',qr_page_unavailable:'Page inaccessible. Vérifiez le lien ou demandez un nouveau code au recruteur.'};
 const kind={vacancy:'Poste identifié',general:'Dépôt de CV général',entry:'Portail à préciser'};
 const sectors={research:'Recherche',mechanical:'Mécanique / industrie',control:'Robotique / commande',digital:'Numérique / logiciel',unknown:'Type non identifié'};
 const stages={connecting:'Connexion à Chrome',letter:'Rédaction et relecture de la lettre',opening_form:'Ouverture du formulaire',finding_form:'Recherche du formulaire',filling:'Remplissage et pièces jointes',checking:'Vérification du formulaire',assisted:'Navigation assistée',submitting:'Envoi en cours',completed:'Envoi confirmé par le site',submission_check:'Vérifiez le résultat sur le site avant tout nouvel envoi.',privacy:'Le site demande votre décision sur la confidentialité.',login:'Connectez-vous dans Chrome, puis reprenez la candidature.',handoff:'Une action de votre part est nécessaire.',materials_review:'Les documents doivent être vérifiés.'};
 async function api(url,options){let response,data;try{response=await fetch(url,options);data=await response.json();}catch{throw Error('Connexion à la plateforme impossible.');}if(!response.ok)throw Error(errors[data.detail]||data.detail||'Connexion à la plateforme impossible.');return data;}
 const post=(url,data)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const canSend=p=>!!p&&(p.readiness?.ready===true||(p.kind==='general'&&p.company&&p.company_quote))&&!!p.resume_id;
 const active=row=>row&&!['draft','analyzing'].includes(row.state);
 const done=row=>['submitted','submitted_verified'].includes(row?.progress?.status);
 function status(row){if(done(row))return 'Envoi confirmé par le site';if(row.state==='analyzing')return 'Lecture du site dans Chrome…';if(row.progress?.worker_running)return 'Candidature en cours';if(active(row))return 'La candidature nécessite votre aide';if(row.preview.kind==='entry')return 'Choisir un poste';return canSend(row.preview)?'Prête à vérifier':'À compléter';}
 function remember(row=current){if(!row)return;const index=items.findIndex(item=>item.id===row.id);if(index<0)items.push(row);else items[index]=row;}
 function stopPoll(){clearTimeout(timer);timer=null;}
 function bind(id,event,handler){const node=dialog.querySelector('#'+id);if(node)node['on'+event]=handler;}
 function notice(error){message=error.message||String(error);paint();}
 function detailMarkup(){
  if(!current)return `<div class="qr-welcome"><img src="/static/artwork/angelina/photo.png" alt="" aria-hidden="true"><h3>${escape(t('Ajoutez votre premier QR code'))}</h3><p>${escape(t('Une photo ou plusieurs : ajoutez-les ici, puis vérifiez chaque candidature dans la liste.'))}</p><p class="small">${escape(t('Le nom de l’entreprise, le lien et le CV proposé apparaîtront ici. Rien n’est envoyé à l’importation.'))}</p><button type="button" class="secondary" data-qr-add>${escape(t('Ajouter des images'))}</button></div>`;
  const p=current.preview,progress=current.progress,started=active(current),analyzing=current.state==='analyzing';
  return `<section class="qr-result" aria-labelledby="qrResultTitle">
   <div class="qr-item-title">${images.has(current.id)?`<img src="${images.get(current.id)}" alt="${escape(t('QR code importé'))}">`:'<span class="qr-item-symbol" aria-hidden="true">↗</span>'}<div><p class="qr-kicker">${escape(p.source_name||host(p.original_qr_url||p.url))}</p><h3 id="qrResultTitle">${escape(p.company||t('Entreprise à identifier'))}</h3><p>${escape(t(status(current)))}</p></div></div>
   ${started?`<section class="qr-progress" role="status"><h3>${escape(t(done(current)?'Envoi confirmé par le site':progress?.worker_running?'Candidature en cours':'La candidature nécessite votre aide'))}</h3><p>${escape(t(stages[progress?.step]||'Vérifiez le résultat sur le site avant tout nouvel envoi.'))}</p>${progress?.detail?.note?`<details><summary>${escape(t('Détail'))}</summary><p>${escape(progress.detail.note)}</p></details>`:''}<div class="qr-handoff">${!done(current)?`<button class="primary compact" id="qrTakeover" ${progress?.worker_running?'disabled':''}>${escape(t('Ouvrir la candidature dans Chrome'))}</button>${!progress?.worker_running?`<button class="ghost compact" id="qrResumeRun">${escape(t('Reprendre cette candidature'))}</button>`:''}<button class="ghost compact" id="qrStop">${escape(t('Arrêter'))}</button>`:''}<button class="ghost compact" id="qrViewQueue">${escape(t('Voir le suivi'))}</button></div></section>`:''}
   <div class="qr-check-block"><div class="qr-block-title"><span aria-hidden="true">01</span><h4>${escape(t('Entreprise et poste'))}</h4></div>
    <details class="qr-company-edit" ${p.company?'':'open'}><summary>${escape(t('Modifier le nom de l’entreprise'))}</summary><label>${escape(t('Entreprise'))}<input id="qrCompany" value="${escape(p.company)}" placeholder="${escape(t('Indiquez le nom de l’entreprise.'))}" ${started||analyzing||actionBusy?'disabled':''}></label></details>
    ${p.kind==='entry'?`<p class="qr-missing">${escape(t('Ce code ouvre un portail, pas encore un poste. Choisissez l’offre qui vous intéresse.'))}</p>${p.opportunities?.length?`<label>${escape(t('Choisir le poste à analyser'))}<select id="qrRole" ${analyzing||actionBusy?'disabled':''}><option value="">${escape(t('Choisir un poste'))}</option>${p.opportunities.map(role=>`<option value="${escape(role.url)}">${escape(role.title)}</option>`).join('')}</select></label>`:''}<form id="qrTargetForm"><label>${escape(t('Ou collez le lien du poste'))}<input id="qrTargetURL" type="url" placeholder="https://…" required ${analyzing?'disabled':''}></label><button type="submit" class="secondary compact" ${actionBusy||analyzing?'disabled':''}>${escape(t('Utiliser ce poste'))}</button></form>`:`<p class="qr-job">${escape(p.role_title||p.title||t('Dépôt de CV général'))}</p>`}
    <a class="qr-target" href="${escape(p.final_url)}" target="_blank" rel="noopener noreferrer">${escape(t('Voir le site destinataire'))} : ${escape(host(p.final_url))} ↗</a>
    ${!started?`<button type="button" class="${canSend(p)?'ghost':'primary'} compact" id="qrAnalyze" ${actionBusy||analyzing?'disabled':''}>${escape(t(analyzing?'Lecture du site dans Chrome…':'Lire le site dans Chrome et compléter les informations'))}</button>`:''}
    ${p.inspection_error?`<p class="qr-missing">${escape(t('Lecture incomplète. Vérifiez Chrome et réessayez.'))}</p><details><summary>${escape(t('Détail'))}</summary><p>${escape(p.inspection_error)}</p></details>`:''}
    ${p.tasks?.length?`<details class="qr-evidence"><summary>${escape(t('Missions lues sur la page'))} · ${p.tasks.length}</summary><ul>${p.tasks.map(task=>`<li>${escape(task)}</li>`).join('')}</ul></details>`:''}
   </div>
   <div class="qr-check-block"><div class="qr-block-title"><span aria-hidden="true">02</span><h4>${escape(t('CV qui sera utilisé'))}</h4></div>
    <label class="qr-resume-label">${escape(t('Vérifiez la version choisie'))}<select id="qrResume" ${started||analyzing||actionBusy?'disabled':''}><option value="">${escape(t('Choisissez la version qui correspond à cette candidature.'))}</option>${(current.resumes||[]).map(r=>`<option value="${escape(r.id)}" ${r.id===p.resume_id?'selected':''}>${escape(r.label)}</option>`).join('')}</select></label>
    <p id="qrResumeHint">${escape(t(p.resume_reason==='qr_resume_manual'?'Vous avez choisi ce CV pour cette candidature.':p.kind==='entry'?'Choisissez un poste avant de confirmer le CV.':'Sélection selon le poste. Vous pouvez choisir une autre version.'))}</p>
    <details class="qr-evidence"><summary>${escape(t('Pourquoi cette sélection ?'))}</summary>${(p.resume_ranking||[]).map(row=>`<article><strong>${escape(row.label)}</strong><p>${escape(row.reason==='role_tasks_vs_cv'?t('Comparaison des missions avec le contenu du CV'):row.reason)}</p>${row.evidence?.[0]?`<p>${escape(t('Extrait du CV'))} : ${escape(row.evidence[0])}</p>`:''}${row.task_evidence?`<p>${escape(t('Mission correspondante'))} : ${escape(row.task_evidence)}</p>`:''}</article>`).join('')}<p>${escape(t('Entreprise identifiée sur la page'))} : ${escape(p.company_quote||t('À confirmer'))}</p><p class="small">${escape(t(sectors[p.sector]||sectors.unknown))} · ${escape(t('Type estimé'))}</p></details>
   </div>
  </section>`;
 }
 function listMarkup(){
  const rows=items.filter(row=>filter==='all'||(filter==='review'&&!active(row))||(filter==='active'&&active(row)&&!done(row))||(filter==='done'&&done(row)));
  return `<div class="qr-import-heading"><h3>${escape(t('Mes candidatures'))} <span>${items.length}</span></h3><button type="button" class="ghost compact" id="qrClear" ${actionBusy?'disabled':''}>${escape(t('Retirer les brouillons'))}</button></div><label class="qr-filter-label" ${items.length<2?'hidden':''}>${escape(t('Afficher'))}<select id="qrFilter"><option value="all">${escape(t('Tout'))}</option><option value="review">${escape(t('À vérifier'))}</option><option value="active">${escape(t('Candidature en cours'))}</option><option value="done">${escape(t('Terminée'))}</option></select></label><p class="qr-mobile-list-hint">${escape(t('Faites défiler pour choisir une candidature.'))}</p><ul>${rows.map(row=>`<li class="${current?.id===row.id?'selected':''}" data-qr-row="${escape(row.id)}"><button type="button" class="qr-select" data-qr-select="${escape(row.id)}" aria-pressed="${current?.id===row.id}">${images.has(row.id)?`<img src="${images.get(row.id)}" alt="">`:'<span class="qr-list-symbol" aria-hidden="true">↗</span>'}<span><strong>${escape(row.preview.company||row.preview.source_name||host(row.preview.final_url))}</strong><span class="qr-list-subtitle">${escape(row.preview.role_title||row.preview.source_name||host(row.preview.final_url))}</span><span class="qr-list-status">${escape(t(status(row)))}</span></span></button>${!active(row)?`<button type="button" class="ghost compact" data-qr-remove="${escape(row.id)}" aria-label="${escape(t('Retirer'))} ${escape(row.preview.company||row.preview.source_name)}">×</button>`:''}</li>`).join('')||`<li class="qr-list-empty">${escape(t(items.length?'Aucune candidature dans cet état.':'Vos QR codes apparaîtront ici.'))}</li>`}</ul>`;
 }
 function ticketsMarkup(){
  const waiting=tickets.filter(x=>['queued','reading'].includes(x.status)).length,errorsCount=tickets.filter(x=>x.status==='error').length;
  const label={queued:'En attente',reading:'Lecture du QR code…',done:'Code ajouté',duplicate:'Déjà dans la liste',error:'À réessayer'};
  return tickets.length?`<details id="qrImportHistory" ${(historyExpanded??(waiting||errorsCount))?'open':''}><summary>${escape(t(waiting?'Importation en cours':'Dernier import'))} · ${tickets.filter(x=>x.status==='done').length} ${escape(t('Codes ajoutés'))} · ${waiting} ${escape(t('En attente'))} · ${errorsCount} ${escape(t('À réessayer'))}</summary><ul>${tickets.map(x=>`<li><div><strong>${escape(x.name)}</strong><span>${escape(t(label[x.status]))}</span>${x.error?`<p>${escape(t(x.error))}</p>`:''}</div>${x.status==='error'?`<button type="button" class="secondary compact" data-qr-retry="${x.key}">${escape(t('Réessayer'))}</button>`:''}<button type="button" class="ghost compact" data-qr-ticket-remove="${x.key}" ${x.status==='reading'?'disabled':''} aria-label="${escape(t('Retirer'))} ${escape(x.name)}">×</button></li>`).join('')}</ul></details>`:'';
 }
 function footerMarkup(){
  if(!current)return `<p>${escape(t('Vous pouvez ajouter d’autres images à tout moment.'))}</p>`;
  if(active(current))return `<p>${escape(t(done(current)?'Envoi confirmé par le site':'Chaque candidature garde son propre suivi.'))}</p><button class="ghost" id="qrNext">${escape(t('Vérifier la suivante'))} →</button>`;
  const analyzing=current.state==='analyzing';return `<div><p>${escape(t(canSend(current.preview)?'Vérifiez le poste et le CV, puis autorisez cette candidature.':'Entreprise, poste ou CV à compléter. Rien ne sera envoyé pour le moment.'))}</p>${canSend(current.preview)?`<small>${escape(t(current.generate_letter===false?'Ce clic autorise l’envoi du CV choisi uniquement. La génération de lettre est désactivée dans ce profil.':'Ce clic autorise l’envoi à ce destinataire du CV choisi et de la lettre générée puis relue par ChatGPT. Les questions manquantes et les accords du site peuvent nécessiter votre intervention.'))}</small>`:''}</div><div class="qr-footer-actions">${items.length>1?`<button type="button" class="ghost" id="qrNext">${escape(t('Vérifier la suivante'))} →</button>`:''}<button class="primary" id="qrSend" ${actionBusy||analyzing||!canSend(current.preview)?'disabled':''}>${escape(t(analyzing?'Lecture du site dans Chrome…':'Postuler en un clic'))}</button></div>`;
 }
 function paint(){
  if(!dialog)return;
  const main=dialog.querySelector('#qrDetail'),list=dialog.querySelector('#qrList'),mainScroll=main.scrollTop,listScroll=list.scrollTop,ticketScroll=dialog.querySelector('#qrTickets').scrollTop;
  const focused=dialog.contains(document.activeElement)?document.activeElement:null,focus=focused?.id||'',selection=focused&&'selectionStart' in focused?[focused.selectionStart,focused.selectionEnd]:null,old=main.dataset.item,targetDraft=main.querySelector('#qrTargetURL')?.value;
  // During background imports do not reconstruct the selected application's form.
  if(!pumping||old!==(current?.id||'')||!main.innerHTML){main.innerHTML=detailMarkup();main.dataset.item=current?.id||'';main.scrollTop=old===main.dataset.item?mainScroll:0;if(old===main.dataset.item&&targetDraft&&main.querySelector('#qrTargetURL'))main.querySelector('#qrTargetURL').value=targetDraft;}
  list.innerHTML=listMarkup();list.scrollTop=listScroll;dialog.querySelector('#qrFilter').value=filter;
  dialog.querySelector('#qrTickets').innerHTML=ticketsMarkup();const history=dialog.querySelector('#qrImportHistory');if(history)history.querySelector('summary').onclick=()=>{historyExpanded=!history.open;};dialog.querySelector('#qrTickets').scrollTop=ticketScroll;dialog.querySelector('#qrFooter').innerHTML=footerMarkup();
  dialog.querySelector('.qr-feedback').textContent=t(message);const browserHelp=dialog.querySelector('#qrOpenChrome');if(browserHelp)browserHelp.hidden=!/chrome|browser|navigateur|浏览器/i.test(message||current?.preview.inspection_error||'');
  dialog.querySelector('#qrAdd').textContent=t(items.length?'Ajouter d’autres QR codes':'Ajouter des images');dialog.querySelector('#qrAdd').className=items.length?'secondary':'primary';
  const feedback=dialog.querySelector('.qr-feedback');feedback.hidden=!message;
  window.AngelinaUI?.refresh();
  if(focus&&dialog.querySelector('#'+focus)!==document.activeElement){const node=dialog.querySelector('#'+focus);node?.focus({preventScroll:true});if(selection&&selection[0]!==null&&node?.setSelectionRange)node.setSelectionRange(...selection);}
  dialog.querySelectorAll('[data-qr-select]').forEach(button=>button.onclick=()=>selectItem(button.dataset.qrSelect));
  dialog.querySelectorAll('[data-qr-remove]').forEach(button=>button.onclick=()=>removeItem(button.dataset.qrRemove));
  dialog.querySelectorAll('[data-qr-add]').forEach(button=>button.onclick=()=>dialog.querySelector('#qrFile').click());
  dialog.querySelectorAll('[data-qr-retry]').forEach(button=>button.onclick=()=>{const ticket=tickets.find(x=>x.key===button.dataset.qrRetry);ticket.status='queued';ticket.error='';paint();pump();});
  dialog.querySelectorAll('[data-qr-ticket-remove]').forEach(button=>button.onclick=()=>{tickets=tickets.filter(x=>x.key!==button.dataset.qrTicketRemove);paint();});
  dialog.querySelector('#qrClear').onclick=clearDrafts;dialog.querySelector('#qrFilter').onchange=e=>{filter=e.target.value;paint();};
  bind('qrAnalyze','click',analyze);
  bind('qrTargetForm','submit',event=>{event.preventDefault();setTarget(dialog.querySelector('#qrTargetURL').value);});
  bind('qrRole','change',e=>{if(e.target.value)setTarget(e.target.value);});
  bind('qrResume','change',e=>{current.preview.resume_id=e.target.value;saveSelection(true);});
  bind('qrCompany','input',e=>{current.preview.company=e.target.value;});
  bind('qrCompany','change',()=>saveSelection(false));
  bind('qrSend','click',send);
  bind('qrNext','click',nextItem);
  bind('qrTakeover','click',()=>post(`/api/jobs/${current.job_id}/take-over`,{}).catch(notice));
  bind('qrResumeRun','click',async()=>{try{await post(`/api/qr/${current.id}/resume`,{});await refresh();}catch(e){notice(e);}});
  bind('qrStop','click',async()=>{try{await post(`/api/jobs/${current.job_id}/stop`,{});await refresh();}catch(e){notice(e);}});
  bind('qrViewQueue','click',()=>{dialog.close();showView('pipeline');});
 }
 async function selectItem(id){if(actionBusy)return;await pendingSelections.get(id);stopPoll();message='';current=await api(`/api/qr/${id}`).catch(error=>{notice(error);return null;});if(current){remember();localStorage.setItem(Accounts.key('qr-request'),current.id);}paint();if(current?.state!=='draft')refresh();if(matchMedia('(max-width:760px)').matches)dialog.querySelector('#qrDetail').scrollIntoView({block:'start',behavior:'instant'});}
 async function removeItem(id){if(actionBusy)return;try{await pendingSelections.get(id);await api(`/api/qr/${id}`,{method:'DELETE'});items=items.filter(x=>x.id!==id);if(images.has(id)){URL.revokeObjectURL(images.get(id));images.delete(id);}if(current?.id===id){stopPoll();current=null;localStorage.removeItem(Accounts.key('qr-request'));if(items.length)await selectItem(items[0].id);}message='Code retiré. Aucun envoi effectué.';paint();}catch(e){notice(e);}}
 async function clearDrafts(){for(const row of [...items])if(!active(row))await removeItem(row.id);}
 function urls(text){return [...new Set((text.match(/https?:\/\/[^\s<>"']+/gi)||[]).map(url=>url.replace(/[),;]+$/,'')))];}
 function enqueue(entries){for(const entry of entries)tickets.push({...entry,key:String(++ticketSequence),name:entry.file?.name||host(entry.url),status:'queued',error:''});message='';paint();pump();}
 async function pump(){
  if(pumping)return;pumping=true;let autoReadId='';
  try{while(tickets.some(x=>x.status==='queued')){
   const ticket=tickets.find(x=>x.status==='queued');ticket.status='reading';paint();
   try{
    let codes=[ticket.url];if(ticket.file){if(ticket.file.size>8*1024*1024)throw Error(errors.qr_image_size);const form=new FormData();form.append('image',ticket.file);codes=(await api('/api/qr/decode',{method:'POST',body:form})).codes;}
    let added=0;
    for(const url of codes){
     if(items.some(x=>[x.preview.url,x.preview.final_url,x.preview.original_qr_url].includes(url)))continue;
     const row=await post('/api/qr/inspect',{url,source_name:ticket.file?.name||''});
     if(items.some(x=>x.preview.final_url===row.preview.final_url)){
      if(!items.some(x=>x.id===row.id)&&row.state==='draft')await api(`/api/qr/${row.id}`,{method:'DELETE'});continue;
     }
     remember(row);added++;if(ticket.file)images.set(row.id,URL.createObjectURL(ticket.file));
     if(!current){current=row;autoReadId=row.preview.needs_enrichment?row.id:'';localStorage.setItem(Accounts.key('qr-request'),row.id);}
    }
    ticket.status=added?'done':'duplicate';
   }catch(e){ticket.status='error';ticket.error=e.message;}
   paint();
  }}finally{pumping=false;paint();if(autoReadId&&current?.id===autoReadId&&!actionBusy)analyze();}
 }
 async function action(callback,label='Préparation de la candidature…'){if(actionBusy||!current)return;actionBusy=true;message=label;paint();const id=current.id;try{await pendingSelections.get(id);await callback(id);if(message===label)message='';}catch(e){message=e.message;}finally{actionBusy=false;paint();}}
 async function analyze(){await action(async id=>{const row=await post(`/api/qr/${id}/analyze`,{});remember(row);if(current?.id===id)current=row;await refresh();},'Lecture du site dans Chrome…');}
 async function setTarget(url){await action(async id=>{const row=await post(`/api/qr/${id}/target`,{url});remember(row);if(current?.id===id)current=row;message='Poste mis à jour. Vérifiez le CV proposé.';},'Lecture du site dans Chrome…');}
 function saveSelection(resume_explicit=true){
  if(!current||current.state!=='draft'||!current.preview.resume_id)return;
  const id=current.id,selection={resume_id:current.preview.resume_id,company:current.preview.company,resume_explicit};
  const promise=(pendingSelections.get(id)||Promise.resolve()).then(()=>post(`/api/qr/${id}/selection`,selection)).then(row=>{
   remember(row);if(current?.id===id&&current.preview.resume_id===selection.resume_id&&current.preview.company===selection.company){Object.assign(current.preview,row.preview);dialog.querySelector('#qrResumeHint').textContent=t('Vous avez choisi ce CV pour cette candidature.');dialog.querySelector('#qrFooter').innerHTML=footerMarkup();bind('qrSend','click',send);}
  }).catch(error=>{message=error.message;dialog.querySelector('.qr-feedback').hidden=false;dialog.querySelector('.qr-feedback').textContent=t(message);const browserHelp=dialog.querySelector('#qrOpenChrome');if(browserHelp)browserHelp.hidden=!/chrome|browser|navigateur|浏览器/i.test(message||current?.preview.inspection_error||'');});pendingSelections.set(id,promise);return promise;
 }
 async function send(){if(!current||!canSend(current.preview)||current.state!=='draft')return;await action(async id=>{const row=await post(`/api/qr/${id}/start`,{resume_id:current.preview.resume_id,company:current.preview.company});remember(row);if(current?.id===id)current=row;await refresh();});}
 function nextItem(){const next=items.find(row=>row.id!==current?.id&&!active(row));if(next)selectItem(next.id);else{message='Vous pouvez ajouter d’autres images à tout moment.';paint();dialog.querySelector('#qrAdd').focus();}}
 async function refresh(){stopPoll();if(!current)return;const id=current.id;try{const row=await api(`/api/qr/${id}`);remember(row);if(current?.id!==id)return;current=row;if(items.some(x=>active(x)||x.state==='analyzing')){const rows=await api('/api/qr');if(Array.isArray(rows))items=rows;remember(current);}if(row.state==='analyzing'&&row.inspection_running===false){current.state='draft';message='Lecture interrompue. Relancez la lecture du site.';}paint();if(dialog.open&&(current.state==='analyzing'||items.some(x=>x.state==='analyzing'||x.progress?.worker_running)))timer=setTimeout(refresh,1500);}catch(e){notice(e);}}
 async function open(){message='';dialog.showModal();try{const rows=await api('/api/qr');if(Array.isArray(rows))items=rows;const saved=localStorage.getItem(Accounts.key('qr-request'));const row=items.find(x=>x.id===(current?.id||saved))||items[0];current=row?await api(`/api/qr/${row.id}`):null;}catch(e){message=e.message;}paint();if(current&&(current.state!=='draft'||items.some(x=>x.progress?.worker_running||x.state==='analyzing')))refresh();}
 function init(){
  dialog=document.createElement('dialog');dialog.id='qrApplicationDialog';dialog.className='qr-desk';dialog.setAttribute('aria-labelledby','qrTitle');
  dialog.innerHTML=`<header class="qr-desk-heading"><div><p class="qr-kicker">QR / APPLICATION DESK</p><h2 id="qrTitle">${escape(t('Postuler avec un QR code'))}</h2><p>${escape(t('Ajoutez vos codes ici. Nous gardons une fiche pour chaque candidature.'))}</p></div><button id="qrClose" type="button" class="ghost">${escape(t('Fermer'))}</button></header>
   <div class="qr-addbar"><button id="qrAdd" type="button" class="primary">${escape(t('Ajouter des images'))}</button><button id="qrLinkToggle" type="button" class="secondary" aria-expanded="false" aria-controls="qrLinkForm">${escape(t('Coller des liens'))}</button><span>${escape(t('Glisser des images ou Ctrl + V'))}</span><input id="qrFile" type="file" multiple accept="image/png,image/jpeg,image/webp,image/bmp" class="qr-native-input" aria-label="${escape(t('Ajouter des images'))}"></div>
   <form id="qrLinkForm" hidden><label>${escape(t('Un lien par ligne'))}<textarea id="qrLink" rows="3" placeholder="https://…" required></textarea></label><button type="submit" class="secondary compact">${escape(t('Importer les liens'))}</button></form>
   <div id="qrTickets"></div><div class="qr-notice-area"><p class="qr-feedback" role="status" aria-live="polite" hidden></p><button type="button" id="qrOpenChrome" class="secondary compact" hidden>${escape(t('Ouvrir Chrome dédié'))}</button></div>
   <div class="qr-desk-body"><section id="qrList" class="qr-imports" aria-label="${escape(t('Mes candidatures'))}"></section><div id="qrDetail" class="qr-detail"></div></div>
   <footer id="qrFooter" class="qr-desk-footer"></footer>`;
  document.body.append(dialog);document.getElementById('qrNav').onclick=open;dialog.querySelector('#qrClose').onclick=()=>dialog.close();dialog.addEventListener('close',stopPoll);
  dialog.querySelector('#qrOpenChrome').onclick=async()=>{try{const state=await post('/api/browser/start',{});message=state.message||'Chrome';paint();}catch(error){notice(error);}};
  dialog.querySelector('#qrAdd').onclick=()=>dialog.querySelector('#qrFile').click();dialog.querySelector('#qrFile').onchange=e=>{const files=[...e.target.files];e.target.value='';if(files.length)enqueue(files.map(file=>({file})));};
  dialog.querySelector('#qrLinkToggle').onclick=()=>{const form=dialog.querySelector('#qrLinkForm');form.hidden=!form.hidden;dialog.querySelector('#qrLinkToggle').setAttribute('aria-expanded',String(!form.hidden));if(!form.hidden)dialog.querySelector('#qrLink').focus();};
  dialog.querySelector('#qrLinkForm').onsubmit=e=>{e.preventDefault();const links=urls(dialog.querySelector('#qrLink').value);if(links.length){enqueue(links.map(url=>({url})));dialog.querySelector('#qrLink').value='';dialog.querySelector('#qrLinkForm').hidden=true;dialog.querySelector('#qrLinkToggle').setAttribute('aria-expanded','false');}else notice(Error('Ajoutez au moins un lien de candidature.'));};
  dialog.addEventListener('paste',e=>{const files=Array.from(e.clipboardData?.items||[]).filter(x=>x.kind==='file'&&x.type.startsWith('image/')).map(x=>x.getAsFile()).filter(Boolean);if(files.length){e.preventDefault();enqueue(files.map(file=>({file})));}else if(!['INPUT','TEXTAREA'].includes(e.target.tagName)){const links=urls(e.clipboardData?.getData('text/plain')||'');if(links.length){e.preventDefault();enqueue(links.map(url=>({url})));}}});
  dialog.addEventListener('dragover',e=>{e.preventDefault();dialog.classList.add('qr-dragging');});dialog.addEventListener('dragleave',e=>{if(!dialog.contains(e.relatedTarget))dialog.classList.remove('qr-dragging');});dialog.addEventListener('drop',e=>{e.preventDefault();dialog.classList.remove('qr-dragging');const files=[...e.dataTransfer.files];if(files.length)enqueue(files.map(file=>({file})));});
  document.addEventListener('localechange',()=>{dialog.querySelector('#qrTitle').textContent=t('Postuler avec un QR code');document.getElementById('qrNav').textContent=t('Postuler avec un QR code');paint();});paint();
 }
 return {init,open};
})();
