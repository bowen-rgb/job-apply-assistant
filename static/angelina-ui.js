/* Constraint brief: task/state first, guidance second, artwork last (§2.1).
   Navigation only: no scan, preparation, approval or send mutations.
   Shared 8/12/16/24/32/48 spacing and existing semantic colors (§3.6/§5.7).
   Decorative scenes get their own column; no text over illustrations (§7.2). */
window.AngelinaUI=(()=>{
 const base='/static/artwork/angelina/',reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const pages={
  overviewView:['ride','Votre prochaine action et vos données réelles, réunies ici.'],
  jobsView:['explore','Choisissez un poste, lisez ses conditions, puis confirmez s’il vous convient.'],
  profileView:['read','Vérifiez le profil sélectionné, vos coordonnées et le CV à utiliser.'],
  pipelineView:['send','Repérez la candidature en cours. Si elle demande votre aide, ouvrez son action de reprise.'],
  guideView:['sit','Commencez par vos documents, puis essayez un poste avec le guide.'],
  pfeView:['dive','Indiquez votre projet de stage et examinez les preuves des opportunités trouvées.'],
  accountsDialog:['shop','Chaque profil garde ses CV et ses comptes. Vérifiez le nom avant de modifier.'],
  pendingTasksDialog:['deliver','Ouvrez une opportunité, vérifiez les informations et choisissez la suite.']
 };
 let mode='static',scheduled=false,overrides={};
 const t=key=>Locale.t(key);
 function text(node,value){if(node.textContent!==value)node.textContent=value;}
 function motion(){return mode==='animated'&&!reduced.matches;}
 function picture(node,scene,running=false){
  const file=scene+(running&&motion()&&['sit','photo','explore','beach','dive','read','send','shop','deliver','ride'].includes(scene)?'.gif':'.png');
  if(node.dataset.file!==file){node.src=base+file;node.dataset.file=file;}
  node.alt='';node.setAttribute('aria-hidden','true');node.draggable=false;
 }
 function stage(id){return ['profileView','accountsDialog'].includes(id)?'profile':['jobsView','pfeView'].includes(id)?'jobs':['pipelineView','qrApplicationDialog','pendingTasksDialog'].includes(id)?'pipeline':'';}
 function decorate(){
  document.documentElement.dataset.angelinaMode=mode;
  const select=document.getElementById('angelinaMode');
  const galleryButton=document.getElementById('angelinaGalleryOpen');if(galleryButton)text(galleryButton,t('Scènes et autocollants')+' · 48');
  if(select){select.value=mode;text(document.querySelector('[for=angelinaMode]'),t('Présentation'));for(const option of select.options)text(option,t({static:'Illustrations',animated:'Animations pendant le travail',quiet:'Mode sobre'}[option.value]));}
  for(const [id,[scene,description]] of Object.entries(pages)){
   const root=document.getElementById(id);if(!root)continue;
   const header=root.querySelector(':scope > header');if(!header)continue;
   root.classList.add('aa-surface');header.classList.add('aa-heading');
   let art=header.querySelector('.aa-scene');
   if(!art){art=header.querySelector('.wb-art')||document.createElement('img');art.classList.add('aa-scene');header.append(art);}
   const visible=root.getClientRects().length>0&&!document.hidden;
   const running=visible&&((id==='pipelineView'&&!!root.querySelector('#queueFocus button[onclick^="stopApplication"]'))||(id==='jobsView'&&root.querySelector('#scanPanel')?.dataset.running==='true'));
   art.loading='lazy';art.width=144;art.height=144;
   picture(art,overrides[id]?.scene||scene,running);
   let ornament=header.querySelector('.aa-ornament');if(!ornament){ornament=document.createElement('img');ornament.className='aa-ornament';ornament.alt='';ornament.setAttribute('aria-hidden','true');ornament.loading='lazy';header.append(ornament);}
   const sticker=overrides[id]?.sticker||({overviewView:'ui-20.png',jobsView:'ui-21.png',profileView:'ui-14.png',pipelineView:'ui-19.png',guideView:'stars.png',pfeView:'ui-15.png',accountsDialog:'ui-12.png',pendingTasksDialog:'ui-13.png'})[id];if(sticker&&ornament.dataset.file!==sticker){ornament.src=base+sticker;ornament.dataset.file=sticker;}
   let help=root.querySelector(':scope > .aa-help');
   if(!help){help=document.createElement('div');help.className='aa-help';const p=document.createElement('p');help.append(p);header.after(help);}
   text(help.querySelector('p'),t(description));
   if(!root.matches('dialog')&&!help.querySelector('nav')){
    const nav=document.createElement('nav');nav.className='aa-route';nav.setAttribute('aria-label',t('Parcours de candidature'));
    ['profile','jobs','pipeline'].forEach((view,i)=>{const button=document.createElement('button');button.type='button';button.dataset.aaView=view;const num=document.createElement('span');num.textContent=String(i+1);num.setAttribute('aria-hidden','true');const label=document.createElement('span');label.className='aa-route-label';button.append(num,label);button.onclick=()=>document.getElementById(view+'Nav')?.click();nav.append(button);});help.append(nav);
   }
   help.querySelectorAll('[data-aa-view]').forEach(button=>{
    const view=button.dataset.aaView;button.setAttribute('aria-current',stage(id)===view?'step':'false');
    text(button.querySelector('.aa-route-label'),t({profile:'Préparer mes documents',jobs:'Choisir un poste',pipeline:'Suivre mes candidatures'}[view]));
   });
   root.querySelectorAll('.empty').forEach(empty=>{if(!empty.querySelector('.aa-empty-art')){const image=document.createElement('img');image.className='aa-empty-art';image.loading='lazy';picture(image,['jobsView','pfeView'].includes(id)?'beach':scene);empty.prepend(image);}});
  }
  // Nested editors and confirmation dialogs share controls and spacing; keep
  // their original task headings, error messages, focus behavior and actions.
  for(const dialog of document.querySelectorAll('dialog'))dialog.classList.add('aa-dialog');
 }
 function schedule(){if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;decorate();});}
 function init(){
  const key=Accounts.key('jaa-appearance');const saved=localStorage.getItem(key);try{overrides=JSON.parse(localStorage.getItem(Accounts.key('jaa-art-layout'))||'{}');}catch{overrides={};}mode=['static','animated','quiet'].includes(saved)?saved:'static';
  const box=document.createElement('div');box.className='angelina-preferences';
  const label=document.createElement('label');label.htmlFor='angelinaMode';const select=document.createElement('select');select.id='angelinaMode';
  for(const value of ['static','animated','quiet']){const option=document.createElement('option');option.value=value;select.append(option);}
  select.onchange=()=>{mode=select.value;localStorage.setItem(key,mode);decorate();};
  const gallery=document.createElement('button');gallery.type='button';gallery.id='angelinaGalleryOpen';gallery.className='ghost';gallery.onclick=()=>AngelinaGallery.open();box.append(label,select,gallery);document.querySelector('aside')?.append(box);
  new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
  reduced.addEventListener('change',decorate);document.addEventListener('localechange',decorate);document.addEventListener('visibilitychange',decorate);document.addEventListener('jaa:scan-state',decorate);document.querySelector('.primary-nav')?.addEventListener('click',schedule);decorate();
 }
 return {init,refresh:decorate,customize:(id,value)=>{if(!pages[id])return;if(value)overrides[id]={...overrides[id],...value};else delete overrides[id];localStorage.setItem(Accounts.key('jaa-art-layout'),JSON.stringify(overrides));decorate();}};
})();
