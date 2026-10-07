/* Navigation-only guidance: never starts a scan, fills a form or sends an application. */
window.Guide=(()=>{
  let health=null,jobs=[],view='jobs';
  const $=id=>document.getElementById(id);
  const text=key=>(window.GuideTexts[Locale.language]||window.GuideTexts.fr)[key];
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const t=key=>escape(text(key));
  function stored(key){try{return localStorage.getItem(key);}catch{return null;}}
  async function go(target,id,filter){
    if($(`${target}View`).classList.contains('hidden'))await showView(target);
    if(filter){current=filter;document.querySelectorAll('.filter').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));render();}
    const node=$(id)||$(`${target}View`).querySelector('h1');
    if(node){if(!node.matches('input,textarea,select,button,a'))node.tabIndex=-1;node.scrollIntoView({block:'center'});node.focus({preventScroll:true});}
  }
  function button(key,target,id='',filter=''){
    return `<button type="button" data-guide-target="${target}" data-guide-id="${id}" data-guide-filter="${filter}">${t(key)}</button>`;
  }
  function bind(root){
    root.querySelectorAll('[data-guide-target]').forEach(b=>b.onclick=()=>go(b.dataset.guideTarget,b.dataset.guideId,b.dataset.guideFilter));
  }
  function render(){
    const troubleOpen=$('guideView').querySelector('details')?.open;
    const focused=document.activeElement?.id;
    $('guideNav').textContent=text('nav');
    const pending=jobs.filter(j=>['APPLY','HUMAN_REVIEW'].includes(j.review_verdict)&&j.human_review_status!=='approved'&&j.human_review_status!=='declined'&&!['submitted','submitted_verified','withdrawn'].includes(j.application_status));
    const resume=health?.resume_ok===true?'ready':health?.resume_ok===false?'cv':'unknown';
    const connection=health?.cdp_ok===true?'browser':health?.cdp_ok===false?'notConnected':'unknown';
    $('guideView').innerHTML=`<header><div><h1 id="guideTitle">${t('nav')}</h1><p>${t('intro')}</p></div></header>
      <div class="guide-readiness" role="status"><p>${t(resume)}</p><p>${t(connection)}</p>${button('cv','profile','resumeFile')}<button type="button" id="guideRetry">${t('retry')}</button></div>
      <div class="guide-paths">${[['manual','manualHelp','jobs','q'],['assisted','assistedHelp','profile','resumeFile'],['sent','sentHelp','pipeline','pipelineBoard']].map(([key,help,target,id])=>`<article><h2>${t(key)}</h2><p>${t(help)}</p>${button(key,target,id)}</article>`).join('')}</div>
      <ol class="guide-tasks">${[['profile','profileHelp','profile','first_name'],['cv','cvHelp','profile','resumeFile'],['jobs','jobsHelp','jobs','q'],['pipeline','pipelineHelp','pipeline','queueFocus']].map(([key,help,target,id])=>`<li><h2>${t(key)}</h2><p>${t(help)}</p>${button(key,target,id)}</li>`).join('')}</ol>
      ${pending.length?`<p>${button('pending','jobs','cards','human')} <strong>${pending.length}</strong></p>`:''}
      <details class="guide-trouble"><summary>${t('help')}</summary><p>${t('offline')}</p><p>${t('privacy')}</p></details>
      <button type="button" id="guidePrint">${t('print')}</button>`;
    const practice=document.createElement('section');practice.id='workedExample';practice.className='worked-example';
    $('guideView').querySelector('header').after(practice);Example.mount();
    if(troubleOpen)$('guideView').querySelector('details').open=true;
    if(focused&&$(focused))$(focused).focus({preventScroll:true});
    bind($('guideView'));$('guideRetry').onclick=refreshAutomationStatus;
    $('guidePrint').onclick=()=>{
      const details=$('guideView').querySelector('details'),wasOpen=details.open;
      details.open=true;
      Example.print(true);
      try{window.print();}finally{Example.print(false);details.open=wasOpen;}
    };
    $('welcomeGuide').hidden=view!=='jobs'||stored('jaa-guide-dismissed')==='1';
    $('welcomeGuide').innerHTML=`<p>${t('welcome')}</p>${button('nav','guide')}<button type="button" id="guideDismiss">${t('dismiss')}</button>`;
    bind($('welcomeGuide'));$('guideDismiss').onclick=()=>{try{localStorage.setItem('jaa-guide-dismissed','1');}catch{}$('welcomeGuide').hidden=true;};
    for(const [name,key] of [['jobs','jobs'],['profile','profile'],['pipeline','pipeline']]){
      let help=$(`${name}Help`);
      if(!help){help=document.createElement('details');help.id=`${name}Help`;help.className='guide-page-help';$(`${name}View`).querySelector('header').after(help);}
      help.innerHTML=`<summary>${t(key)}</summary><p>${t(key+'Help')}</p>${name==='profile'?button('cv','profile','resumeFile')+button('profile','profile','saveProfileBtn'):''}${button('nav','guide')}`;
      bind(help);
    }
    document.querySelectorAll('#resumeList a[download]').forEach(a=>a.textContent=text('download'));
    Locale.apply();
  }
  return {text,go,init:render,render,view:which=>{view=which;render();},health:value=>{health=value;render();},jobs:value=>{jobs=value;render();}};
})();
