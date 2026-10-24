/* Navigation registry: the scene and compact menu share these routes.
   Every entry opens an existing page/editor; no application or scan is started. */
window.WorkspaceMenu=(()=>{
 const routes=[
  ['jobs','jobsNav'],['pipeline','pipelineNav'],['profile','profileNav'],['qr','qrNav'],
  ['overview','overviewNav'],['guide','guideNav'],['accounts','accountsNav'],['logins','platformLoginNav'],
  ['pending','pendingTasksNav'],['pfe','pfeNav'],['liked','liked'],['human','human'],['confirmed','confirmed'],['submitted','submitted'],
  ['export','jobExportShortcut'],['sources','jobSourcesShortcut'],['resumes','resumeFile'],['appearance','appearanceSettings']
 ];
 const $=id=>document.getElementById(id),t=key=>Locale.t('menu.'+key);
 let view='menu',previous='jobs',frame,ready=false,token='',summary=null,loading=false,serial=0,frameDeadline;
 const entries=()=>routes.map(([id,target])=>({id,target,label:t(id),short:t(id)}));
 const shown=()=>view==='menu';
 function state(){
  const owner=$('candidateSelect')?.selectedOptions[0]?.textContent||'';
  return {type:'jaa-menu:state',token,active:shown()&&!document.hidden,language:Locale.language,
   quiet:document.documentElement.dataset.angelinaMode==='quiet',owner,profileLabel:t('profile'),hint:t('hint'),
   widget:Object.fromEntries(['music','map','chooseMusic','noTrack','localMusic','locate','locating','locationHint','locationError','openMap','clearLocation','rotate','clock','audioError'].map(key=>[key,t(key)])),
   sync:loading?t('loading'):summary?.error?t('unavailable'):summary?t('updated'):'',entries:entries(),
   metrics:['jobs','pipeline','human','submitted'].map(id=>({label:t(id),value:summary?.counts?.[id]??'—'}))};
 }
 function notify(){if(ready)frame.contentWindow.postMessage(state(),'*');}
 function render(){
  $('workspaceMenuButton').textContent=t('back')+' · Tab';$('mainMenuTitle').textContent=t('title');
  $('mainMenuHint').textContent=t('hint');$('menuSearch').placeholder=t('search');$('menuSearch').setAttribute('aria-label',t('search'));
  $('workspaceTitle').textContent=view==='menu'?t('title'):(t(view));
  const query=$('menuSearch').value.trim().toLocaleLowerCase();
  $('mainMenuView').classList.toggle('menu-searching',!!query);
  $('menuPageGrid').replaceChildren();
  for(const item of entries().filter(item=>!query||item.label.toLocaleLowerCase().includes(query)||item.id.includes(query))){
   const button=document.createElement('button');button.type='button';button.dataset.menuPage=item.id;
   const icon=document.createElement('span');icon.className='menu-page-icon';icon.setAttribute('aria-hidden','true');
   icon.textContent=({jobs:'⌕',pipeline:'⇢',profile:'▤',qr:'▦',overview:'◴',guide:'?',accounts:'◎',logins:'⌘',pending:'✓',pfe:'◇',liked:'♡',human:'◌',confirmed:'✓',submitted:'↗',export:'↓',sources:'⌕',resumes:'▤',appearance:'✧'})[item.id];
   const label=document.createElement('strong');label.textContent=item.label;
   const arrow=document.createElement('span');arrow.textContent='↗';arrow.className='menu-page-arrow';arrow.setAttribute('aria-hidden','true');
   button.append(icon,label,arrow);button.onclick=()=>navigate(item.id);$('menuPageGrid').append(button);
  }
  $('menuEmpty').hidden=!!$('menuPageGrid').children.length;$('menuEmpty').textContent=t('empty');
  $('menuDataStatus').textContent=loading?t('loading'):summary?.error?t('unavailable'):summary?t('updated'):'';
  $('menuRetry').textContent=t('retry');$('menuRetry').hidden=!summary?.error;
  frame.title=t('title');notify();
 }
 async function refresh(){
  if(loading)return;
  loading=true;const request=++serial;render();
  try{
   const [jobs,queue]=await Promise.all([requestJson('/api/jobs'),requestJson('/api/queue')]);
   if(!Array.isArray(jobs)||!Array.isArray(queue.items))throw Error('Menu data unavailable');
   if(request!==serial)return;
   summary={counts:{jobs:jobs.filter(j=>matchFilter(j,'all')).length,pipeline:queue.items.filter(j=>!['done','cancelled'].includes(j.status)).length,
    human:jobs.filter(j=>matchFilter(j,'human')).length,submitted:jobs.filter(j=>matchFilter(j,'submitted')).length}};
  }catch{if(request===serial)summary={error:true};}
  finally{if(request===serial){loading=false;render();}}
 }
 async function navigate(id){
  const route=routes.find(row=>row[0]===id);if(!route)return;
  $('menuSearch').value='';
  if(['liked','human','confirmed','submitted'].includes(id)){
   showView('jobs');qInput.value='';sourceSelect.value='';document.querySelector(`#jobSidebar [data-filter="${id}"]`).click();
  }else if(['export','sources'].includes(id)){
   if(id==='export')showView('jobs');else await showView('profile');
   $(route[1]).click();
  }else if(['resumes','appearance'].includes(id)){
   await showView('profile');const target=$(route[1]);target.scrollIntoView({block:'center',behavior:'smooth'});target.focus({preventScroll:true});
  }else {
   // Dialog pages return to the exact underlying page, including unsaved inputs.
   if(['qr','accounts','logins','pending'].includes(id)&&shown())showView(previous,{resume:true});
   $(route[1])?.click();
  }
 }
 function activate(next){
  if(view!=='menu')previous=view;view=next;document.body.dataset.workspaceView=next;
  render();
  if(shown()){
   if(!frame.src){token=[...crypto.getRandomValues(new Uint8Array(16))].map(byte=>byte.toString(16).padStart(2,'0')).join('');frame.src='/static/vendor/endfield-menu/index.html#token='+encodeURIComponent(token);frameDeadline=setTimeout(()=>{if(!ready)$('mainMenuView').classList.add('menu-fallback');},5000);}
   refresh();
  }
 }
 function init(){
  const header=document.createElement('header');header.id='workspaceHeader';header.className='workspace-header';
  const brand=document.querySelector('aside .brand');const menu=document.createElement('button');menu.type='button';menu.id='workspaceMenuButton';menu.onclick=()=>showView('menu');
  const title=document.createElement('span');title.id='workspaceTitle';title.setAttribute('aria-live','polite');
  const controls=document.createElement('div');controls.className='workspace-controls';
  controls.append(document.querySelector('.profile-switcher'),document.querySelector('.language-control'));
  header.append(brand,menu,title,controls);document.querySelector('.shell').before(header);
  document.querySelector('aside').hidden=true;
  const actionBar=document.createElement('div');actionBar.className='workspace-page-actions';
  actionBar.append($('searchBtn'),$('batchBtn'));$('jobsView').querySelector('header').after(actionBar);
  const options=document.createElement('details');options.id='workspaceOptions';
  const optionsLabel=document.createElement('summary');optionsLabel.textContent='⋯';optionsLabel.setAttribute('aria-label',t('appearance'));
  options.append(optionsLabel,$('simpleModeToggle'));header.insertBefore(options,title);
  options.addEventListener('click',event=>{if(event.target.closest('button'))options.open=false;});
  const appearance=document.createElement('section');appearance.id='appearanceSettings';appearance.className='settings-card';appearance.tabIndex=-1;
  const heading=document.createElement('h2');heading.textContent=t('appearance');appearance.append(heading,document.querySelector('.angelina-preferences'));
  $('profileForm').insertBefore(appearance,$('profileForm').lastElementChild);
  const data=document.createElement('details');data.className='workspace-data-tools';const caption=document.createElement('summary');caption.textContent=t('data');data.append(caption,$('clearBtn'));$('profileView').append(data);
  // Retain existing command/filter bindings without retaining a sidebar UI.
  const commands=document.createElement('div');commands.id='workspaceCommands';commands.hidden=true;
  const oldAside=document.querySelector('aside');while(oldAside.firstChild)commands.append(oldAside.firstChild);oldAside.replaceWith(commands);
  $('mainMenuView').innerHTML='<div class="main-menu-heading"><div><h1 id="mainMenuTitle"></h1><p id="mainMenuHint"></p></div><input id="menuSearch" type="search" autocomplete="off"></div><div class="main-menu-stage"><iframe id="menuScene" sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe><nav id="menuPageGrid"></nav><p id="menuEmpty" hidden></p></div><footer class="main-menu-footer"><span id="menuDataStatus" role="status"></span><button id="menuRetry" type="button" hidden></button><a href="/static/vendor/endfield-menu/NOTICE.md" target="_blank" rel="noopener">Endfield menu · source & credits ↗</a></footer>';
  frame=$('menuScene');$('menuSearch').oninput=render;$('menuRetry').onclick=refresh;
  window.addEventListener('message',event=>{
   if(event.source!==frame.contentWindow||!event.data||event.data.token!==token)return;
   if(event.data.type==='jaa-menu:ready'){ready=true;clearTimeout(frameDeadline);$('mainMenuView').classList.remove('menu-fallback');notify();}
   if(event.data.type==='jaa-menu:navigate')navigate(event.data.action);
   if(event.data.type==='jaa-menu:back')showView(previous,{resume:true});
   if(event.data.type==='jaa-menu:locate'&&shown()){
    const reply=value=>frame.contentWindow.postMessage({type:'jaa-menu:location',token,...value},'*');
    if(!navigator.geolocation){reply({error:true});return;}
    navigator.geolocation.getCurrentPosition(position=>reply({latitude:position.coords.latitude,longitude:position.coords.longitude}),()=>reply({error:true}),{timeout:12000,maximumAge:60000,enableHighAccuracy:false});
   }
  });
  document.addEventListener('localechange',()=>{heading.textContent=t('appearance');caption.textContent=t('data');render();});
  document.addEventListener('visibilitychange',()=>{notify();if(shown()&&!document.hidden)refresh();});
  document.addEventListener('jaa:view-change',event=>activate(event.detail.view));
  document.addEventListener('keydown',event=>{if((event.key==='Escape'||event.key==='Tab'&&!event.shiftKey&&!event.ctrlKey&&!event.altKey&&!event.metaKey)&&!event.repeat&&!document.querySelector('dialog[open]')&&!event.target.closest('input,textarea,select,audio,[contenteditable=true]')){event.preventDefault();showView(shown()?previous:'menu',{resume:true});}});
  setInterval(()=>{if(shown()&&!document.hidden)refresh();},10000);
  showView('menu');
 }
 return {init,navigate,refresh,entries};
})();
