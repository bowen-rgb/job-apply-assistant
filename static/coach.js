/* Real manual-application journey. Submission stays on the recruiter's website. */
window.Coach=(()=>{
  let simple=true,state={step:0,id:null,index:0,opened:false},health=null,jobs=[],loaded=false,busy=false,signature='',message='',checked=false,autoResume=true,searching=false,searchRequested=false;
  const drafts={role:'',place:''};
  let automate=false,autoSubmit=false,autoStart=false;
  try{simple=localStorage.getItem('jaa-ui-mode')!=='full';}catch{}
  const $=id=>document.getElementById(id);
  const text=k=>(CoachTexts[Locale.language]||CoachTexts.fr)[k];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function save(){try{localStorage.setItem(Accounts.key('jaa-manual-flow'),JSON.stringify(state));}catch{}}
  function url(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}}
  const submitted=j=>['submitted','submitted_verified'].includes(j.application_status)||['submitted','screening','interview','offer'].includes(j.tracker_stage);
  const candidates=()=>jobs.filter(j=>url(j.url)&&!submitted(j)&&j.user_action!=='skipped'&&!['reject','expired'].includes(j.decision)&&!['SKIP','QUEUED','RUNNING'].includes(j.review_verdict)&&!['rejected','withdrawn'].includes(j.tracker_stage)&&!['opening','preparing','preparing_letter','withdrawn'].includes(j.application_status)&&j.queue_status!=='running'&&!matchFilter(j,'expired')).sort((a,b)=>(b.score||0)-(a.score||0));
  function move(step){state.step=step;if(step===0)autoResume=false;message='';checked=false;signature='';save();paint();$('coachTitle')?.focus();}
  function setMessage(value){message=value;if($('coachStatus'))$('coachStatus').textContent=value;}
  async function action(fn){if(busy)return;busy=true;document.querySelectorAll('#beginnerGuide button').forEach(b=>b.disabled=true);setMessage(text('wait'));try{await fn();}catch{setMessage(text('error'));}finally{busy=false;document.querySelectorAll('#beginnerGuide button').forEach(b=>b.disabled=false);if($('coachRecord'))$('coachRecord').disabled=!checked;if($('coachReturn'))$('coachReturn').disabled=!state.opened;if($('coachSearch'))$('coachSearch').disabled=searching;paint();}}
  function paint(){
    const root=$('beginnerGuide');if(!root||busy)return;
    if(autoResume&&health?.resume_ok===true&&state.step===0){state.step=1;autoResume=false;save();}
    let selected=jobs.find(j=>j.id===state.id);
    if(loaded&&state.step>=2&&state.id&&!selected){state={step:1,id:null,index:0,opened:false};checked=false;save();}
    if(selected&&submitted(selected)){state.step=4;save();}
    const options=candidates(),job=state.step===1?options[state.index%Math.max(options.length,1)]:selected;
    const key=JSON.stringify([Locale.language,state.step,state.id,state.index,state.opened,job,options.length]);
    if(key===signature){if($('coachStatus'))$('coachStatus').textContent=message;return;}signature=key;
    const headings=['cv',options.length?'choose':'empty','site','confirm','done'];
    let body='';
    if(state.step===0)body=`<p>${esc(text('cvHint'))}</p><label for="coachFile">${esc(text('cv'))}</label><div class="coach-file-box"><span id="coachFileName" aria-hidden="true">${esc(text('fileBox'))}</span><input id="coachFile" type="file" aria-label="${esc(text('fileBox'))}" accept=".pdf,.doc,.docx"></div><button id="coachUpload" class="primary" type="button">${esc(text('upload'))}</button>`;
    if(state.step===1){
      body=job?`<p>${esc(text('chooseHint'))}</p><article class="coach-job"><h3>${esc(job.display_title||job.title)}</h3><p>${esc(job.company)} · ${esc(job.location)}</p><p>${esc(job.employment_type||'')}</p><details><summary>${esc(text('details'))}</summary><p>${esc(job.description||job.snippet||'')}</p></details></article><button type="button" id="coachPick" class="primary">${esc(text('pick'))}</button><button type="button" id="coachOther">${esc(text('other'))}</button>`:
        `<label for="coachRole">${esc(text('role'))}</label><input id="coachRole" value="${esc(drafts.role)}"><label for="coachPlace">${esc(text('place'))}</label><input id="coachPlace" value="${esc(drafts.place)}"><button id="coachSearch" class="primary" type="button">${esc(text('search'))}</button><p>${esc(text('noResults'))}</p>`;
    }
    if(state.step===1&&job&&automate){body=body.replace(/<button[^>]*id="coachPick"[^>]*>.*?<\/button>/,'');const pending=['APPLY','HUMAN_REVIEW'].includes(job.review_verdict)&&job.human_review_status!=='approved';body+=`<button type="button" id="coachAutomate" class="primary">${esc(Accounts.actionLabel(pending?2:autoSubmit?0:1))}</button>`;}
    if(state.step===2&&job)body=`<h3>${esc(job.display_title||job.title)}</h3><p>${esc(job.company)} · ${esc(job.location)}</p><ol class="coach-site-steps">${text('siteHint').split(/(?=[①②③④]|[1-4]\. )/).filter(Boolean).map(s=>`<li>${esc(s.replace(/^[①②③④]|^[1-4]\. /,''))}</li>`).join('')}</ol><a id="coachOpen" class="primary coach-link" href="${esc(url(job.url))}" target="_blank" rel="noopener noreferrer">${esc(text('open'))}</a><div id="coachResume"></div><button id="coachReturn" type="button" ${state.opened?'':'disabled'}>${esc(text('returned'))}</button><details><summary>${esc(text('help'))}</summary><p>${esc(text('helpHint'))}</p><button type="button" id="coachAlready">${esc(text('already'))}</button></details>`;
    if(state.step===3&&job)body=`<h3>${esc(job.display_title||job.title)}</h3><p>${esc(job.company)} · ${esc(job.location)}</p><label class="coach-check"><input id="coachConfirmed" type="checkbox">${esc(text('check'))}</label><button id="coachRecord" class="primary" type="button" disabled>${esc(text('record'))}</button>`;
    if(state.step===4)body=`<p class="example-success">${esc(text('done'))}</p><h3>${esc(job?.display_title||job?.title||'')}</h3><button id="coachNext" class="primary" type="button">${esc(text('next'))}</button>`;
    const previousFile=root.querySelector('#coachFile');
    root.innerHTML=`<p>${esc(ExampleTexts[Locale.language].step)} ${state.step+1} / 5</p><h2 id="coachTitle" tabindex="-1">${esc(text(headings[state.step]))}</h2>${body}<p id="coachStatus" role="status" aria-live="polite">${esc(message)}</p>${state.step>0&&state.step<4?`<button id="coachBack" type="button">${esc(text('back'))}</button>`:''}<details class="coach-help"><summary>${esc(text('help'))}</summary><p>${esc(text('helpHint'))}</p></details>`;
    if(previousFile&&$('coachFile'))$('coachFile').replaceWith(previousFile);
    if($('coachFile')){const file=$('coachFile');file.setAttribute('aria-label',text('fileBox'));const name=()=>{$('coachFileName').textContent=file.files[0]?.name||text('fileBox');};file.onchange=name;name();}
    if($('coachConfirmed')){$('coachConfirmed').checked=checked;$('coachRecord').disabled=!checked;}
    if($('coachUpload'))$('coachUpload').onclick=()=>{const file=$('coachFile').files[0];if(!file){setMessage(text('missing'));$('coachFile').focus();return;}action(async()=>{const fd=new FormData();fd.append('file',file);const result=await requestJson('/api/resumes/upload',{method:'POST',body:fd});if(!result.resume?.id)throw new Error('Missing resume');await requestJson(`/api/resumes/${encodeURIComponent(result.resume.id)}/activate`,{method:'POST'});move(1);await refreshAutomationStatus();});};
    if($('coachPick'))$('coachPick').onclick=()=>{state.id=job.id;state.opened=false;move(2);loadResumeLink();};
    if($('coachOther'))$('coachOther').onclick=()=>{state.index++;save();signature='';paint();};
    if($('coachRole')){for(const [id,k] of [['coachRole','role'],['coachPlace','place']])$(id).oninput=()=>drafts[k]=$(id).value;}
    if($('coachSearch')){$('coachSearch').disabled=searching;$('coachSearch').onclick=()=>{if(!drafts.role.trim()||!drafts.place.trim()){setMessage(text('need'));return;}action(async()=>{await requestJson('/api/profile',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({preferences:{roles:[drafts.role.trim()],locations:[drafts.place.trim()]}})});await requestJson('/api/search',{method:'POST'});searchRequested=true;await pollScan();await load();});};}
    if($('coachOpen'))$('coachOpen').onclick=()=>{state.opened=true;save();$('coachReturn').disabled=false;};
    if($('coachReturn'))$('coachReturn').onclick=()=>move(3);
    if($('coachAlready'))$('coachAlready').onclick=()=>move(3);
    if($('coachConfirmed'))$('coachConfirmed').onchange=()=>{checked=$('coachConfirmed').checked;$('coachRecord').disabled=!checked;};
    if($('coachRecord'))$('coachRecord').onclick=()=>{if(!checked)return;action(async()=>{await requestJson(`/api/jobs/${state.id}/application-status`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({status:'submitted'})});move(4);await load();});};
    if($('coachAutomate'))$('coachAutomate').onclick=()=>action(async()=>{if(['APPLY','HUMAN_REVIEW'].includes(job.review_verdict)&&job.human_review_status!=='approved'){current='human';qInput.value=job.title||'';await load();showView('jobs');return;}await requestJson('/api/queue',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({job_ids:[job.id]})});if(!autoStart)await requestJson('/api/queue/start?mode=batch',{method:'POST'});showView('pipeline');});
    if($('coachNext'))$('coachNext').onclick=()=>{state.id=null;state.index=0;state.opened=false;move(1);};
    if($('coachBack'))$('coachBack').onclick=()=>move(state.step===1?0:state.step-1);
    if(state.step===2)loadResumeLink();
  }
  async function loadResumeLink(){try{const rows=await requestJson('/api/resumes');const active=rows.find(r=>r.active);if(active&&$('coachResume'))$('coachResume').innerHTML=`<a href="/api/resumes/${encodeURIComponent(active.id)}/download" download>${esc(Guide.text('download'))}</a>`;}catch{}}
  function mount(root,h,js){health=h;jobs=js;paint();document.body.classList.toggle('simple-mode',simple);if($('simpleModeToggle'))$('simpleModeToggle').textContent=text(simple?'full':'mode');if(simple){$('guideNav').textContent=text('nav');$('guideTitle').textContent=text('nav');$('guideTitle').nextElementSibling.textContent=text('intro');}}
  function init(){try{const saved=JSON.parse(localStorage.getItem(Accounts.key('jaa-manual-flow'))||'null');if(saved&&Number.isInteger(saved.step)&&saved.step>=0&&saved.step<=4&&Number.isInteger(saved.index)&&saved.index>=0&&saved.index<100000&&(!saved.id||Number.isInteger(saved.id)))state={step:saved.step,id:saved.id,index:saved.index,opened:saved.opened===true};}catch{}const toggle=document.createElement('button');toggle.id='simpleModeToggle';toggle.type='button';document.querySelector('.language-control').after(toggle);toggle.onclick=()=>{simple=!simple;try{localStorage.setItem('jaa-ui-mode',simple?'simple':'full');}catch{}signature='';Guide.render();if(simple)showView('guide');};if(simple)showView('guide');else Guide.render();requestJson('/api/profile').then(p=>{automate=p.automation?.auto_submit===true||p.automation?.auto_start_queue===true;autoSubmit=p.automation?.auto_submit===true;autoStart=p.automation?.auto_start_queue===true;drafts.role||=p.preferences?.roles?.[0]||'';drafts.place||=p.preferences?.locations?.[0]||'';signature='';paint();}).catch(()=>{});}
  function scan(s){searching=s?.running===true;if(state.step===1&&(searching||searchRequested)){message=!s?text('error'):searching?text('wait'):candidates().length?'':text('noResults');if(!searching)searchRequested=false;setMessage(message);}if($('coachSearch'))$('coachSearch').disabled=searching||busy;}
  function configure(p){automate=p.automation?.auto_submit===true||p.automation?.auto_start_queue===true;autoSubmit=p.automation?.auto_submit===true;autoStart=p.automation?.auto_start_queue===true;signature='';paint();}
  return {configure,init,mount,jobsLoaded:()=>{loaded=true;},isSimple:()=>simple,text,scan};
})();
