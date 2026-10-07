/* Fictional practice: only its own progress is saved, never application records. */
window.Example=(()=>{
  let step=0,checked=false,following=false;
  try{const s=localStorage.getItem('jaa-example-step-v1');if(/^[0-5]$/.test(s||''))step=Number(s);}catch{}
  const t=k=>(ExampleTexts[Locale.language]||ExampleTexts.fr)[k];
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const targets=[['profile','resumeFile'],['jobs','q'],['pipeline','queueFocus'],['pipeline','queueFocus'],['pipeline','pipelineBoard']];
  function save(){try{localStorage.setItem('jaa-example-step-v1',String(step));}catch{}}
  function context(i){
    const label=k=>esc(Locale.t(k));
    if(i===0)return `<div class="example-preview">CV_Alex_Accueil.pdf → ${label('Ajouter')} → ${label('ACTIF')}</div>`;
    if(i===1)return `<div class="example-preview"><b>Réceptionniste · Hôtel Exemple</b><p>Paris · CDD</p>${label('Ouvrir l’offre ↗')}</div>`;
    if(i===2)return `<div class="example-preview"><dl><dt>${label('Prénom')}</dt><dd>Alex</dd><dt>${label('E-mail')}</dt><dd>alex@example.test</dd><dt>CV</dt><dd>CV_Alex_Accueil.pdf</dd></dl></div>`;
    if(i===3)return `<div class="example-preview">${label('Envoyer')} → ${esc(t('sent'))}</div>`;
    return `<div class="example-preview"><b>Réceptionniste · Hôtel Exemple</b><p>${esc(t('sent'))}</p>${esc(t('record'))}</div>`;
  }
  function instructions(i){return `<h3>${i+1}. ${esc(t(i+'title'))}</h3><p>${esc(t(i+'body'))}</p><h4>${esc(t('label'))}</h4>${context(i)}<h4>${esc(t('expect'))}</h4><p>${esc(t(i+'expect'))}</p>`;}
  function paint(focus=false){
    const root=document.getElementById('workedExample');if(!root)return;
    root.innerHTML=`<h2 id="exampleTitle" tabindex="-1">${esc(t('title'))}</h2><p class="example-note">${esc(t('note'))}</p><p role="status">${esc(t('step'))} ${Math.min(step+1,5)} / 5</p><progress value="${step}" max="5" aria-label="${esc(t('title'))}"></progress>
      ${step<5?instructions(step):`<p class="example-success">${esc(t('done'))}</p>${context(4)}`}
      ${step===2?`<label class="example-check"><input type="checkbox" id="exampleChecked" ${checked?'checked':''}>${esc(t('2action'))}</label>`:''}
      <div class="example-actions">${step<5?`<button type="button" id="exampleAdvance" class="primary" ${step===2&&!checked?'disabled':''}>${esc(t(step+'action'))}</button>${[0,1,4].includes(step)?`<button type="button" id="exampleReal">${esc(t('real'))}</button>`:''}`:`<button type="button" id="exampleStart">${esc(t('start'))}</button>`}${step>0?`<button type="button" id="exampleBack">${esc(t('back'))}</button>`:''}<button type="button" id="exampleReset">${esc(t('reset'))}</button></div>`;
    const advance=document.getElementById('exampleAdvance');
    if(advance)advance.onclick=()=>{if(step===2&&!checked)return;step++;checked=false;save();paint(true);};
    const box=document.getElementById('exampleChecked');if(box)box.onchange=()=>{checked=box.checked;advance.disabled=!checked;};
    const real=document.getElementById('exampleReal');if(real)real.onclick=async()=>{following=true;await Guide.go(...targets[step]);companion();};
    const start=document.getElementById('exampleStart');if(start)start.onclick=()=>{following=false;Guide.go('jobs','q');};
    const back=document.getElementById('exampleBack');if(back)back.onclick=()=>{step=Math.max(0,step-1);checked=false;save();paint(true);};
    document.getElementById('exampleReset').onclick=()=>{step=0;checked=false;following=false;save();paint(true);};
    companion();if(focus)document.getElementById('exampleTitle').focus({preventScroll:true});
  }
  function companion(){
    let node=document.getElementById('exampleCompanion');
    if(!node){node=document.createElement('div');node.id='exampleCompanion';document.getElementById('mainContent').prepend(node);}
    node.hidden=!following||!document.getElementById('guideView').classList.contains('hidden')||step===5;
    node.innerHTML=`<b>${esc(t('step'))} ${Math.min(step+1,5)}/5 · ${esc(t(Math.min(step,4)+'title'))}</b><p>${esc(t(Math.min(step,4)+'body'))}</p><button type="button">${esc(t('return'))}</button>`;
    node.querySelector('button').onclick=()=>Guide.go('guide','exampleTitle');
  }
  return {mount:paint,print:all=>{const root=document.getElementById('workedExample');if(all)root.innerHTML=`<h2>${esc(t('title'))}</h2><p>${esc(t('note'))}</p>`+[0,1,2,3,4].map(instructions).join('');else paint();}};
})();
