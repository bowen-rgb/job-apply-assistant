let allJobs=[];
let current='all';
let pollTimer=null;
let scanTimer=null;
let sourceLabels={};
let sourcesCache=[];
let loadedProfile=null;
let savedAnswers=[];
let searchProfiles=[];
let resumesCache=[];
const cards=document.querySelector('#cards');
const statusEl=document.querySelector('#status');
const profileStatus=document.querySelector('#profileStatus');
const summary=document.querySelector('#summary');
const scanPanel=document.querySelector('#scanPanel');
const scanText=document.querySelector('#scanText');
const scanCounts=document.querySelector('#scanCounts');
const scanCurrent=document.querySelector('#scanCurrent');
const progressBar=document.querySelector('#progressBar');
const qInput=document.querySelector('#q');
const sourceSelect=document.querySelector('#sourceSelect');

const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const lines=s=>String(s||'').split(/\r?\n|,/).map(x=>x.trim()).filter(Boolean);
const toLines=a=>(a||[]).join('\n');
const el=id=>document.getElementById(id);
const tr=key=>Locale.t(key);

function showView(which){
  const jobs=which==='jobs', profile=which==='profile', pipeline=which==='pipeline';
  el('jobsView').classList.toggle('hidden',!jobs);
  el('profileView').classList.toggle('hidden',!profile);
  el('pipelineView').classList.toggle('hidden',!pipeline);
  el('jobSidebar').classList.toggle('hidden',!jobs);
  el('jobsNav').classList.toggle('active',jobs);
  el('profileNav').classList.toggle('active',profile);
  el('pipelineNav').classList.toggle('active',pipeline);
  if(profile) loadProfile();
  if(pipeline) loadPipeline();
}
el('jobsNav').onclick=()=>showView('jobs');
el('profileNav').onclick=()=>showView('profile');
el('pipelineNav').onclick=()=>showView('pipeline');

async function loadSources(){
  try{
    const r=await fetch('/api/sources');
    const xs=await r.json();
    sourcesCache=xs;
    sourceLabels=Object.fromEntries(xs.map(x=>[x.key,x.label]));
    sourceSelect.innerHTML=`<option value="">${esc(tr('Toutes les sources'))}</option>`+xs.filter(x=>x.enabled).map(x=>`<option value="${esc(x.key)}">${esc(x.label)}</option>`).join('');
    renderSourceSettings();
  }catch(e){}
}

async function load(){
  const r=await fetch('/api/jobs');
  allJobs=await r.json();
  render();
  const running=allJobs.some(j=>['QUEUED','RUNNING'].includes(j.review_verdict));
  if(running && !pollTimer) pollTimer=setInterval(load,3500);
  if(!running && pollTimer){clearInterval(pollTimer);pollTimer=null;}
}

function matchFilter(j){
  if(current==='all') return true;
  if(['keep','review'].includes(current)) return j.decision===current;
  if(current==='liked') return j.user_action==='liked';
  if(current==='approved') return j.review_verdict==='APPLY';
  if(current==='human') return j.review_verdict==='HUMAN_REVIEW';
  if(current==='queued') return !!j.queue_status && !['done','error','cancelled'].includes(j.queue_status);
  if(current==='submitted') return ['submitted','submitted_verified'].includes(j.application_status);
  if(current==='expired') return ['expired','reject'].includes(j.decision) || j.availability_status==='expired' || j.review_verdict==='SKIP';
  return true;
}

function reviewBadge(j){
  const v=j.review_verdict||'';
  if(!v) return `<span class="review none">${esc(tr('Pas relu'))}</span>`;
  const cls=v==='APPLY'?'applyok':v==='SKIP'?'skipbad':v==='HUMAN_REVIEW'?'human':v==='ERROR'?'err':'running';
  const conf=j.review_confidence?` · ${j.review_confidence}%`:'';
  return `<span class="review ${cls}">${esc(v)}${conf}</span>`;
}

function fact(label,value){
  if(!value) return '';
  return `<span class="fact"><b>${esc(label)}</b> ${esc(value)}</span>`;
}

function reviewDetails(j){
  if(!j.review_summary && !j.review_json) return '';
  let extra='';
  if(j.review_json){
    try{
      const x=JSON.parse(j.review_json);
      const reasons=(x.reasons||[]).map(v=>`<li>${esc(v)}</li>`).join('');
      const manual=(x.manual_questions||[]).map(v=>`<li>${esc(v)}</li>`).join('');
      const risks=(x.risks||[]).map(v=>`<li>${esc(v)}</li>`).join('');
      if(reasons||manual||risks) extra=`<details><summary>${esc(tr('Détails du reviewer'))}</summary>${reasons?`<div class="detail-title">${esc(tr('Raisons'))}</div><ul>${reasons}</ul>`:''}${risks?`<div class="detail-title">${esc(tr('Risques'))}</div><ul>${risks}</ul>`:''}${manual?`<div class="detail-title">${esc(tr('À vérifier'))}</div><ul>${manual}</ul>`:''}</details>`;
    }catch(e){}
  }
  return `<div class="review-summary">${esc(j.review_summary||'')}${extra}</div>`;
}

function render(){
  const q=(qInput.value||'').trim().toLowerCase();
  const src=sourceSelect.value;
  const jobs=allJobs.filter(j=>matchFilter(j)).filter(j=>!src || j.provider_key===src).filter(j=>{
    if(!q) return true;
    return [j.title,j.company,j.location,j.source,j.employment_type].join(' ').toLowerCase().includes(q);
  });
  const liked=allJobs.filter(j=>j.user_action==='liked').length;
  const keep=allJobs.filter(j=>j.decision==='keep').length;
  const approved=allJobs.filter(j=>j.review_verdict==='APPLY').length;
  const human=allJobs.filter(j=>j.review_verdict==='HUMAN_REVIEW').length;
  const submitted=allJobs.filter(j=>['submitted','submitted_verified'].includes(j.application_status)).length;
  summary.textContent=`${jobs.length} / ${allJobs.length} ${tr('offres')}`;
  el('jobMetrics').innerHTML=[[tr('Offres'),allJobs.length,'all'],[tr('Match fort'),keep,'keep'],[tr('Aimées'),liked,'liked'],[tr('À vérifier'),human,'human'],[tr('Envoyées'),submitted,'submitted']].map(([label,count,filter])=>`<button type="button" class="metric metric-button ${current===filter?'selected':''}" data-metric-filter="${filter}"><span>${esc(label)}</span><b>${count}</b></button>`).join('');
  el('jobMetrics').querySelectorAll('[data-metric-filter]').forEach(button=>button.onclick=()=>{current=button.dataset.metricFilter;document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.filter===current));render();});
  if(!jobs.length){cards.innerHTML=`<div class="empty"><strong>${esc(tr('Aucune offre dans cette vue.'))}</strong><span>${esc(tr('Modifiez les filtres ou lancez un scan pour trouver des offres.'))}</span></div>`;return;}
  cards.innerHTML=jobs.map(j=>`<article class="card">
    <div class="top"><div><div class="title">${esc(j.title||tr('Offre sans titre'))}</div><div class="company">${esc(j.company||'')} ${j.location?`<span>· ${esc(j.location)}</span>`:''}</div></div><div class="source">${esc(sourceLabels[j.provider_key]||j.source||'web')}</div></div>
    <div class="meta"><span class="tag">${esc(j.decision)}</span>${j.user_action?`<span class="tag user">${esc(j.user_action)}</span>`:''}${j.application_status?`<span class="tag appstate">${esc(j.application_status)}</span>`:''}${j.queue_status?`<span class="tag queue">file: ${esc(j.queue_status)}</span>`:''}${j.tracker_stage?`<span class="tag stage">${esc(j.tracker_stage)}</span>`:''}<span class="score ${j.score>=65?'good':j.score>=38?'mid':''}">${j.score}</span>${reviewBadge(j)}</div>
    <div class="facts">${fact(tr('Profil'),j.search_profile_label&&j.search_profile_label!=='Default'?j.search_profile_label:'')}${fact('ATS',j.ats&&j.ats!=='generic'?j.ats:'')}${fact(tr('Contrat'),j.employment_type)}${fact(tr('Début'),j.start_date)}${fact(tr('Fin'),j.end_date)}${fact(tr('Salaire'),j.salary)}${fact(tr('Publié'),j.date_posted)}</div>
    <div class="snippet">${esc(j.snippet||j.body?.slice(0,430)||'')}</div>
    <div class="reason">${esc(j.reason||'')}</div>
    ${reviewDetails(j)}
    <div class="linkrow"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(tr('Ouvrir l’offre ↗'))}</a></div>
    <div class="actions five">
      <button class="skip" onclick="decide(${j.id},'skipped')">${esc(tr('Passer'))}</button>
      <button class="like" onclick="decide(${j.id},'liked')">${esc(tr('Garder'))}</button>
      <button class="reviewbtn" onclick="reviewJob(${j.id})">${esc(tr('ChatGPT终审'))}</button>
      <button class="apply" onclick="applyJob(${j.id},'${esc(j.review_verdict||'')}')">${esc(tr('Pré-remplir'))}</button>
      <button class="ghost" onclick="queueJob(${j.id})">${esc(tr('+ File'))}</button>
    </div>
    <div class="status-actions">${['submitted','submitted_verified'].includes(j.application_status)?`<span class="submitted-pill">${esc(tr('Envoyée'))}${j.application_status==='submitted_verified'?` · ${esc(tr('vérifiée'))}`:''}</span>`:`<button class="ghost compact" onclick="markApplication(${j.id},'submitted')">${esc(tr('Marquer envoyée'))}</button>`}${j.apply_adapter?`<span class="small">${esc(tr('Adapter:'))} ${esc(j.apply_adapter)}</span>`:''}${j.agent_status?`<span class="small">${esc(tr('Agent:'))} ${esc(j.agent_status)}${j.agent_steps?` · ${j.agent_steps} ${esc(tr('étapes'))}`:''}</span>`:''}${j.fill_audit_path?`<a class="audit-link" href="/api/jobs/${j.id}/audit" target="_blank" rel="noopener">${esc(tr('Audit ↗'))}</a>`:''}${j.agent_trace_path?`<a class="audit-link" href="/api/jobs/${j.id}/agent-trace" target="_blank" rel="noopener">${esc(tr('Agent trace ↗'))}</a>`:''}</div>
  </article>`).join('');
}

async function decide(id,d){
  await fetch(`/api/jobs/${id}/decision`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({decision:d})});
  await load();
}
async function reviewJob(id){
  statusEl.textContent='ChatGPT Web 终审排队中…';
  const r=await fetch(`/api/jobs/${id}/review`,{method:'POST'}); const x=await r.json();
  statusEl.textContent=x.message||'Reviewer queued'; await load();
}
async function applyJob(id, verdict){
  if(!verdict){if(!confirm(tr('Cette offre n’a pas encore été relue par ChatGPT. Ouvrir quand même ?'))) return;}
  else if(verdict==='SKIP'){if(!confirm(tr('Le reviewer recommande SKIP. Ouvrir quand même ?'))) return;}
  else if(verdict==='HUMAN_REVIEW'){if(!confirm(tr('Le reviewer demande une vérification humaine. Ouvrir le formulaire ?'))) return;}
  statusEl.textContent='Ouverture du formulaire…';
  const r=await fetch(`/api/jobs/${id}/apply`,{method:'POST'}); const x=await r.json();
  statusEl.textContent=x.message||'Ouvert'; setTimeout(load,1500);
}
async function markApplication(id,status){
  await fetch(`/api/jobs/${id}/application-status`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({status})});
  statusEl.textContent=status==='submitted'?'Candidature marquée comme envoyée.':'Statut mis à jour.';
  await load();
}
async function queueJob(id){
  await fetch('/api/queue',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({job_ids:[id],priority:100})});
  statusEl.textContent='Ajoutée à la file de pré-remplissage.'; await load();
}
window.decide=decide; window.reviewJob=reviewJob; window.applyJob=applyJob; window.markApplication=markApplication; window.queueJob=queueJob;

async function pollScan(){
  try{
    const r=await fetch('/api/search/status'); const s=await r.json();
    if(s.running || s.scan_id){
      scanPanel.classList.remove('hidden'); scanText.textContent=tr(s.running?'Scan en cours':'Dernier scan terminé');
      scanCounts.textContent=`${s.found} ${tr('vus')} · ${s.fetched} ${tr('lus')} · ${s.inserted} ${tr('nouveaux')} · ${s.updated} ${tr('mis à jour')} · ${s.errors} ${tr('erreurs')}`;
      scanCurrent.textContent=s.running?`${s.current_campaign?`[${s.current_campaign}] `:''}${s.current_source||''} ${s.current_title||''}`:(s.message||'');
      const denom=Math.max(1,s.found); progressBar.style.width=`${Math.min(100,Math.round((s.fetched/denom)*100))}%`;
    }
    if(s.running){if(!scanTimer) scanTimer=setInterval(pollScan,1500); await load();}
    else if(scanTimer){clearInterval(scanTimer);scanTimer=null;await load();}
  }catch(e){}
}

for(const b of document.querySelectorAll('.filter')) b.onclick=()=>{document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));b.classList.add('active');current=b.dataset.filter;render();};
qInput.oninput=render; sourceSelect.onchange=render;
el('searchBtn').onclick=async()=>{statusEl.textContent='Démarrage du scan…';const r=await fetch('/api/search',{method:'POST'});const x=await r.json();statusEl.textContent=x.running?'Scan lancé':'Scan déjà actif';await pollScan();};
el('batchBtn').onclick=async()=>{if(!confirm(tr('Lancer le reviewer ChatGPT sur les offres aimées + match fort non encore relues ?')))return;const r=await fetch('/api/review/batch?mode=strong',{method:'POST'});const x=await r.json();statusEl.textContent=x.message||tr('Batch review lancé');setTimeout(load,1000);};
el('healthBtn').onclick=async()=>{statusEl.textContent='Vérification locale…';try{const r=await fetch('/api/health');const h=await r.json();const ls=h.learning_stats||{};const bits=[`CV:${h.resume_ok?'OK':'MANQUANT'}`,`CDP:${h.cdp_ok?'OK':'OFF'}`,`Playwright:${h.playwright_ok?'OK':'MANQUANT'}`,`Scrapling:${h.scrapling_ok?'OK':'MANQUANT'}`,`Agent:${h.agent_fallback_enabled?'ON':'OFF'}`,`Learn:${ls.rules??0}/${ls.successes??0}`];statusEl.textContent=bits.join(' · ')+(h.cdp_browser?` · ${h.cdp_browser}`:'');}catch(e){statusEl.textContent='Diagnostic impossible: '+e;}};
el('clearBtn').onclick=async()=>{if(!confirm(tr('Supprimer toutes les offres locales ?')))return;await fetch('/api/jobs',{method:'DELETE'});await load();};

function setValue(id,v){const x=el(id);if(x)x.value=v??'';}
function setChecked(id,v){const x=el(id);if(x)x.checked=!!v;}
function answerRow(item={}){
  const div=document.createElement('div'); div.className='answer-row';
  div.innerHTML=`<input class="ans-match" placeholder="Libellé / regex, ex. motivation|why us" value="${esc(item.match||'')}"><textarea class="ans-value" rows="2" placeholder="Réponse">${esc(item.value||'')}</textarea><label class="check"><input class="ans-auto" type="checkbox" ${item.autofill===false?'':'checked'}> auto</label><button type="button" title="Supprimer">×</button>`;
  div.querySelector('button').onclick=()=>div.remove();
  el('answersList').appendChild(div);
}
el('addAnswerBtn').onclick=()=>answerRow({});

function renderSourceSettings(){
  const enabled=new Set(loadedProfile?.automation?.enabled_sources||sourcesCache.filter(x=>x.enabled).map(x=>x.key));
  el('sourcesGrid').innerHTML=sourcesCache.filter(s=>!s.filter_only).map(s=>`<label class="source-check"><input type="checkbox" data-source="${esc(s.key)}" ${enabled.has(s.key)?'checked':''}> ${esc(s.label)}</label>`).join('');
}

async function loadResumes(){
  const r=await fetch('/api/resumes'); const xs=await r.json(); resumesCache=xs;
  document.querySelectorAll('.search-profile-row .sp-resume').forEach(sel=>{const cur=sel.value;sel.innerHTML=`<option value="">${esc(tr('CV actif / routage auto'))}</option>`+xs.map(x=>`<option value="${esc(x.id)}">${esc(x.label||x.original_name)}</option>`).join('');sel.value=cur;});
  const box=el('resumeList');
  if(!xs.length){box.innerHTML=`<div class="small">${esc(tr('Aucun CV dans la bibliothèque locale.'))}</div>`;return;}
  box.innerHTML=xs.map(x=>`<div class="resume-item resume-edit"><div class="resume-fields"><input id="resume-label-${esc(x.id)}" value="${esc(x.label||x.original_name)}" aria-label="Nom du CV"><input id="resume-tags-${esc(x.id)}" value="${esc((x.tags||[]).join(', '))}" placeholder="tags: accueil, logistique…" aria-label="Tags du CV"><div class="resume-meta">${esc(x.original_name)} · ${(x.size/1024).toFixed(0)} KB</div></div><div class="resume-actions">${x.active?'<span class="active-pill">ACTIF</span>':`<button type="button" onclick="activateResume('${esc(x.id)}')">Activer</button>`}<button type="button" onclick="saveResumeMeta('${esc(x.id)}')">Enregistrer</button><button type="button" onclick="deleteResume('${esc(x.id)}')">Supprimer</button></div></div>`).join('');
}
async function activateResume(id){await fetch(`/api/resumes/${id}/activate`,{method:'POST'});await loadResumes();profileStatus.textContent='CV actif modifié.';}
async function saveResumeMeta(id){
  const label=el(`resume-label-${id}`)?.value?.trim()||'';
  const tags=lines(el(`resume-tags-${id}`)?.value||'');
  const r=await fetch(`/api/resumes/${id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({label,tags})});
  profileStatus.textContent=r.ok?'Métadonnées CV enregistrées.':'Erreur lors de la mise à jour du CV.';
  if(r.ok) await loadResumes();
}
async function deleteResume(id){if(!confirm(tr('Supprimer ce CV de la bibliothèque locale ?')))return;await fetch(`/api/resumes/${id}`,{method:'DELETE'});await loadResumes();}
window.activateResume=activateResume;window.saveResumeMeta=saveResumeMeta;window.deleteResume=deleteResume;
el('uploadResumeBtn').onclick=async()=>{
  const file=el('resumeFile').files[0]; if(!file){profileStatus.textContent='Choisis un fichier CV.';return;}
  const fd=new FormData(); fd.append('file',file); fd.append('label',el('resumeLabel').value||'');
  profileStatus.textContent='Ajout du CV…'; const r=await fetch('/api/resumes/upload',{method:'POST',body:fd});
  if(!r.ok){profileStatus.textContent=(await r.json()).detail||'Erreur upload';return;}
  el('resumeFile').value='';el('resumeLabel').value='';await loadResumes();profileStatus.textContent='CV ajouté.';
};


function searchProfileRow(item={}){
  const box=el('searchProfilesList'); if(!box)return;
  const d=document.createElement('div'); d.className='search-profile-row';
  const id=item.id||`profile-${Date.now()}-${Math.floor(Math.random()*999)}`;
  d.dataset.id=id;
  d.innerHTML=`<div class="sp-head"><label class="check"><input class="sp-enabled" type="checkbox" ${item.enabled===false?'':'checked'}> Actif</label><input class="sp-label" value="${esc(item.label||'Profil de recherche')}" placeholder="Nom du profil"><button type="button" class="danger ghost compact sp-delete">Supprimer</button></div>
  <div class="form-grid cols3">
    <label>Rôles<textarea class="sp-roles" rows="3">${esc(toLines(item.roles||[]))}</textarea></label>
    <label>Lieux<textarea class="sp-locations" rows="3">${esc(toLines(item.locations||[]))}</textarea></label>
    <label>Contrats<textarea class="sp-contracts" rows="3">${esc(toLines(item.contracts||[]))}</textarea></label>
    <label>Sources internes<textarea class="sp-sources" rows="2" placeholder="indeed\nhellowork">${esc(toLines(item.sources||[]))}</textarea></label>
    <label>Sites JobSpy<input class="sp-jobspy" value="${esc((item.jobspy_sites||[]).join(', '))}" placeholder="indeed, google"></label>
    <label>Pays Indeed<input class="sp-country" value="${esc(item.country_indeed||'')}" placeholder="France"></label>
    <label>Résultats<input class="sp-results" type="number" min="1" max="200" value="${esc(item.results_wanted??20)}"></label>
    <label>Ancienneté h<input class="sp-hours" type="number" min="0" value="${esc(item.hours_old??168)}"></label>
    <label>CV dédié (optionnel)<select class="sp-resume"><option value="">CV actif / routage auto</option>${resumesCache.map(x=>`<option value="${esc(x.id)}" ${x.id===(item.resume_id||'')?'selected':''}>${esc(x.label||x.original_name)}</option>`).join('')}</select></label>
  </div>`;
  d.querySelector('.sp-delete').onclick=()=>d.remove(); box.appendChild(d);
}
function readSearchProfiles(){
  return [...document.querySelectorAll('.search-profile-row')].map((r,i)=>({
    id:r.dataset.id||`profile-${i+1}`,label:r.querySelector('.sp-label').value.trim()||`Profil ${i+1}`,
    enabled:r.querySelector('.sp-enabled').checked,roles:lines(r.querySelector('.sp-roles').value),locations:lines(r.querySelector('.sp-locations').value),contracts:lines(r.querySelector('.sp-contracts').value),
    sources:lines(r.querySelector('.sp-sources').value),jobspy_sites:lines(r.querySelector('.sp-jobspy').value),country_indeed:r.querySelector('.sp-country').value.trim(),
    results_wanted:Number(r.querySelector('.sp-results').value||20),hours_old:Number(r.querySelector('.sp-hours').value||168),resume_id:r.querySelector('.sp-resume').value.trim()
  }));
}
el('addSearchProfileBtn').onclick=()=>searchProfileRow({});

async function loadProfile(){
  try{
    const r=await fetch('/api/profile'); loadedProfile=await r.json();
    const i=loadedProfile.identity||{}, b=loadedProfile.background||{}, a=loadedProfile.availability||{}, p=loadedProfile.preferences||{}, au=loadedProfile.automation||{};
    ['first_name','last_name','email','phone','address_line1','city','postal_code','country','linkedin','portfolio'].forEach(k=>setValue(k,i[k]));
    ['current_title','current_company','years_experience','school','degree','field_of_study','graduation_year'].forEach(k=>setValue(k,b[k]));
    setValue('availability_start_date',a.start_date);setValue('availability_end_date',a.end_date);setValue('availability_text',a.text);setValue('weekends',a.weekends||'flexible');setValue('night_shifts',a.night_shifts||'flexible');setValue('holiday_work',a.holiday_work||'flexible');setValue('hours_min',a.hours_per_week_min);setValue('hours_max',a.hours_per_week_max);
    setValue('roles',toLines(p.roles));setValue('locations',toLines(p.locations));setValue('contracts',toLines(p.contracts));setValue('industries',toLines(p.industries));setValue('include_terms',toLines(p.include_terms));setValue('exclude_terms',toLines(p.exclude_terms));setValue('max_commute_minutes',p.max_commute_minutes);setValue('min_salary',p.min_salary);setValue('salary_period',p.salary_period||'hour');setValue('languages',toLines(p.languages));
    setValue('search_queries_per_run',au.search_queries_per_run||18);setValue('search_market',au.search_market||'');setValue('custom_sources',(au.custom_sources||[]).map(x=>typeof x==='string'?x:`${x.label||x.domain} | ${x.domain}`).join('\n'));setValue('max_results_per_query',au.max_results_per_query||10);setValue('direct_source_pages',au.direct_source_pages||3);setValue('browser_mode',au.browser_mode||'cdp');setValue('chrome_cdp_endpoint',au.chrome_cdp_endpoint||'http://127.0.0.1:9222');setChecked('dynamic_fetch_fallback',au.dynamic_fetch_fallback!==false);setChecked('reviewer_enabled',au.chatgpt_web_reviewer?.enabled!==false);
    setChecked('jobspy_enabled',au.jobspy_enabled!==false);setValue('jobspy_sites',(au.jobspy_sites||['indeed','google']).join(', '));setValue('jobspy_results_wanted',au.jobspy_results_wanted??20);setValue('jobspy_hours_old',au.jobspy_hours_old??168);setValue('jobspy_country_indeed',au.jobspy_country_indeed||'');setValue('dedupe_scope',au.dedupe_scope||'title_company_location');setValue('auto_scan_interval_minutes',au.auto_scan_interval_minutes??0);setChecked('jobspy_linkedin_fetch_description',au.jobspy_linkedin_fetch_description===true);
    searchProfiles=au.search_profiles||[];
    const ag=au.agent_fallback||{};setChecked('agent_enabled',ag.enabled!==false);setValue('agent_max_steps',ag.max_steps??8);setValue('agent_min_confidence',ag.min_action_confidence??82);setChecked('agent_allow_next',ag.allow_next_clicks!==false);setChecked('agent_for_assisted',ag.run_for_agent_assisted_ats!==false);setChecked('agent_for_required',ag.run_when_required_unanswered!==false);setChecked('agent_screenshots',ag.screenshot_each_step===true);setValue('company_boards',toLines(au.company_boards||[]));
    setChecked('auto_resume_routing',loadedProfile.application?.auto_resume_routing===true);
    savedAnswers=(loadedProfile.application?.saved_answers||[]);el('answersList').innerHTML='';savedAnswers.forEach(answerRow);if(!savedAnswers.length)answerRow({});
    renderSourceSettings(); await loadResumes(); el('searchProfilesList').innerHTML=''; searchProfiles.forEach(searchProfileRow); profileStatus.textContent='Profil chargé.';
  }catch(e){profileStatus.textContent='Impossible de charger le profil: '+e;}
}

function readAnswers(){
  return [...document.querySelectorAll('.answer-row')].map(r=>({match:r.querySelector('.ans-match').value.trim(),value:r.querySelector('.ans-value').value.trim(),autofill:r.querySelector('.ans-auto').checked})).filter(x=>x.match&&x.value);
}

el('saveProfileBtn').onclick=async()=>{
  if(!loadedProfile) await loadProfile();
  const profile=structuredClone(loadedProfile||{});
  profile.schema_version=8;
  profile.identity={...(profile.identity||{}),first_name:el('first_name').value.trim(),last_name:el('last_name').value.trim(),email:el('email').value.trim(),phone:el('phone').value.trim(),address_line1:el('address_line1').value.trim(),city:el('city').value.trim(),postal_code:el('postal_code').value.trim(),country:el('country').value.trim(),linkedin:el('linkedin').value.trim(),portfolio:el('portfolio').value.trim()};
  profile.background={...(profile.background||{}),current_title:el('current_title').value.trim(),current_company:el('current_company').value.trim(),years_experience:el('years_experience').value,school:el('school').value.trim(),degree:el('degree').value.trim(),field_of_study:el('field_of_study').value.trim(),graduation_year:el('graduation_year').value.trim()};
  profile.availability={...(profile.availability||{}),start_date:el('availability_start_date').value,end_date:el('availability_end_date').value,text:el('availability_text').value.trim(),weekends:el('weekends').value,night_shifts:el('night_shifts').value,holiday_work:el('holiday_work').value,hours_per_week_min:el('hours_min').value,hours_per_week_max:el('hours_max').value};
  profile.preferences={...(profile.preferences||{}),roles:lines(el('roles').value),locations:lines(el('locations').value),contracts:lines(el('contracts').value),industries:lines(el('industries').value),include_terms:lines(el('include_terms').value),exclude_terms:lines(el('exclude_terms').value),max_commute_minutes:el('max_commute_minutes').value,min_salary:el('min_salary').value,salary_period:el('salary_period').value,languages:lines(el('languages').value)};
  profile.application={...(profile.application||{}),saved_answers:readAnswers(),auto_resume_routing:el('auto_resume_routing').checked};
  profile.automation={...(profile.automation||{}),enabled_sources:[...document.querySelectorAll('[data-source]:checked')].map(x=>x.dataset.source),search_queries_per_run:Number(el('search_queries_per_run').value||18),search_market:el('search_market').value.trim(),custom_sources:lines(el('custom_sources').value).map(line=>{const p=line.split('|').map(x=>x.trim());return {label:(p.length>1?p[0]:p[0]),domain:(p.length>1?p[1]:p[0])};}).filter(x=>x.domain),max_results_per_query:Number(el('max_results_per_query').value||10),direct_source_pages:Number(el('direct_source_pages').value||3),browser_mode:el('browser_mode').value,chrome_cdp_endpoint:el('chrome_cdp_endpoint').value.trim(),dynamic_fetch_fallback:el('dynamic_fetch_fallback').checked,company_boards:lines(el('company_boards').value),jobspy_enabled:el('jobspy_enabled').checked,jobspy_sites:lines(el('jobspy_sites').value),jobspy_results_wanted:Number(el('jobspy_results_wanted').value||20),jobspy_hours_old:Number(el('jobspy_hours_old').value||168),jobspy_country_indeed:el('jobspy_country_indeed').value.trim(),jobspy_linkedin_fetch_description:el('jobspy_linkedin_fetch_description').checked,dedupe_scope:el('dedupe_scope').value,auto_scan_interval_minutes:Number(el('auto_scan_interval_minutes').value||0),search_profiles:readSearchProfiles(),chatgpt_web_reviewer:{...(profile.automation?.chatgpt_web_reviewer||{}),enabled:el('reviewer_enabled').checked,cdp_endpoint:el('chrome_cdp_endpoint').value.trim()},agent_fallback:{...(profile.automation?.agent_fallback||{}),enabled:el('agent_enabled').checked,max_steps:Number(el('agent_max_steps').value||8),min_action_confidence:Number(el('agent_min_confidence').value||82),allow_next_clicks:el('agent_allow_next').checked,run_for_agent_assisted_ats:el('agent_for_assisted').checked,run_when_required_unanswered:el('agent_for_required').checked,screenshot_each_step:el('agent_screenshots').checked}};
  profileStatus.textContent='Enregistrement…';
  const r=await fetch('/api/profile',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(profile)});
  const x=await r.json(); if(!r.ok){profileStatus.textContent=x.detail||'Erreur';return;}
  loadedProfile=x.profile;profileStatus.textContent='Profil enregistré.';await loadSources();
};

el('exportProfileBtn').onclick=()=>{window.location.href='/api/profile/export';};
el('importProfileBtn').onclick=()=>el('profileImportFile').click();
el('profileImportFile').onchange=async()=>{
  const file=el('profileImportFile').files[0]; if(!file)return;
  if(!confirm('Importer ce profil et remplacer les paramètres actuels ? Les CV locaux ne seront pas supprimés.'))return;
  const fd=new FormData();fd.append('file',file);profileStatus.textContent='Import du profil…';
  const r=await fetch('/api/profile/import',{method:'POST',body:fd});const x=await r.json();
  if(!r.ok){profileStatus.textContent=x.detail||'Import impossible';return;}
  loadedProfile=x.profile;profileStatus.textContent='Profil importé.';await loadProfile();await loadSources();
};


const stageLabels={saved:'Sauvegardée',queued:'En file',prepared:'Préparée',submitted:'Envoyée',screening:'Screening',interview:'Entretien',offer:'Offre',rejected:'Refus',withdrawn:'Retirée'};
async function setStage(id,stage){
  const note=prompt(tr('Note (optionnelle) :'),''); if(note===null)return;
  await fetch(`/api/jobs/${id}/track`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({stage,note,followup_at:''})});
  await loadPipeline(); await load();
}
async function removeQueue(id){await fetch(`/api/queue/${id}`,{method:'DELETE'});await loadPipeline();await load();}
window.setStage=setStage;window.removeQueue=removeQueue;
async function loadPipeline(){
  const [pr,qr,ar]=await Promise.all([fetch('/api/pipeline'),fetch('/api/queue'),fetch('/api/analytics')]);
  const jobs=await pr.json(), q=await qr.json(), a=await ar.json();
  el('pipelineSummary').textContent=`${jobs.length} ${tr('dossiers suivis')} · ${tr('file:')} ${Object.values(q.counts||{}).reduce((x,y)=>x+y,0)} · worker ${tr(q.running?'actif':'inactif')}`;
  const t=a.totals||{}; el('analyticsCards').innerHTML=[['Offres',t.total||0],['Aimées',t.liked||0],['Reviewer APPLY',t.reviewer_apply||0],['Envoyées',t.submitted||0]].map(x=>`<div class="metric"><span>${esc(tr(x[0]))}</span><b>${x[1]}</b></div>`).join('');
  el('queueList').innerHTML=(q.items||[]).length?(q.items||[]).map(x=>`<div class="queue-item"><b>${esc(x.title||'')}</b> · ${esc(x.company||'')} <span class="tag queue">${esc(x.status)}</span><div class="small">${esc(tr('Tentatives'))} ${x.attempts||0}${x.note?` · ${esc(x.note)}`:''}</div><button class="ghost compact" onclick="removeQueue(${x.job_id})">${esc(tr('Retirer'))}</button></div>`).join(''):`<div class="empty">${esc(tr('File vide.'))}</div>`;
  const stages=['saved','queued','prepared','submitted','screening','interview','offer','rejected','withdrawn'];
  el('pipelineBoard').innerHTML=stages.map(st=>{const xs=jobs.filter(j=>(j.tracker_stage||((j.user_action==='liked')?'saved':''))===st);return `<div class="pipeline-col"><h3>${esc(tr(stageLabels[st]))} <span class="stage-count">${xs.length}</span></h3>${xs.map(j=>`<div class="pipeline-card"><b>${esc(j.title||'')}</b><div>${esc(j.company||'')}</div><div class="small">${esc(j.location||'')} ${j.next_followup_at?`· ${esc(tr('suivi'))} ${esc(j.next_followup_at)}`:''}</div><select onchange="setStage(${j.id},this.value)">${stages.map(x=>`<option value="${x}" ${x===st?'selected':''}>${esc(tr(stageLabels[x]))}</option>`).join('')}</select></div>`).join('')}</div>`}).join('');
}
el('queueRunBtn').onclick=async()=>{await fetch('/api/queue/start',{method:'POST'});el('pipelineStatus').textContent='Worker démarré.';setTimeout(loadPipeline,700);};
el('queueClearBtn').onclick=async()=>{await fetch('/api/queue/clear-finished',{method:'POST'});await loadPipeline();};
el('startQueueBtn').onclick=async()=>{await fetch('/api/queue/start',{method:'POST'});statusEl.textContent='File de pré-remplissage démarrée.';};

document.addEventListener('localechange',()=>{render();loadSources();if(!el('pipelineView').classList.contains('hidden'))loadPipeline();Locale.apply();});
async function init(){await Locale.ready;await loadSources();await load();await pollScan();}
init();
