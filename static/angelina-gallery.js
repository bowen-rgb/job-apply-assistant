/* Native, local-only material catalog. Selecting art changes a page's illustration,
   never an applicant profile or workflow state. All 48 source files are available. */
window.AngelinaGallery=(()=>{
 let dialog,assets=[],tab='character',target='',preview=null;
 const t=s=>Locale.t(s),labelFor=(id,label)=>document.getElementById(id.endsWith('View')?id.replace('View','Nav'):id==='accountsDialog'?'accountsNav':'pendingTasksNav')?.textContent||t(label),escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
 const labels={overviewView:'Tableau de bord',jobsView:'Offres',profileView:'Profil & préférences',pipelineView:'Pipeline & file',guideView:'Premiers pas',pfeView:'PFE / Recherche',accountsDialog:'Profils et comptes',pendingTasksDialog:'Tâches à traiter'};
 function paint(){
  const rows=assets.filter(x=>x.kind===tab);
  dialog.innerHTML=`<header><div><p class="qr-kicker">ANGELINA / MATERIAL LIBRARY · 48</p><h2 id="angelinaGalleryTitle">${escape(t('Scènes et autocollants'))}</h2><p>${escape(t('Choisissez une illustration pour cette page. Les informations et les actions restent prioritaires.'))}</p></div><button type="button" id="aaGalleryClose" class="ghost">${escape(t('Fermer'))}</button></header>
   <div class="aa-gallery-controls"><label>${escape(t('Page à personnaliser'))}<select id="aaGalleryTarget">${Object.entries(labels).map(([id,label])=>`<option value="${id}" ${id===target?'selected':''}>${escape(labelFor(id,label))}</option>`).join('')}</select></label><button type="button" class="ghost" id="aaGalleryReset">${escape(t('Rétablir les choix automatiques'))}</button></div>
   <nav class="aa-gallery-tabs">${[['character','Personnages · 10'],['animation','Animations · 10'],['sticker','Autocollants · 28']].map(([kind,label])=>`<button type="button" data-aa-tab="${kind}" aria-pressed="${tab===kind}">${escape(t(label))}</button>`).join('')}</nav>
   <p class="small">${escape(t(tab==='animation'?'Aperçu du dessin uniquement. Les animations de la page respectent votre préférence de mouvement.':'Les petits autocollants décorent les marges, sans recouvrir le texte.'))}</p>
   <div class="aa-gallery-grid">${rows.map(asset=>`<article><div class="aa-gallery-image"><img src="/static/artwork/angelina/${escape(preview===asset.id?asset.file:asset.preview)}" alt="${escape(t(asset.label))}" loading="lazy"></div><p>${escape(t(asset.label))}</p><div>${tab==='animation'?`<button type="button" class="ghost" data-aa-preview="${asset.id}">${escape(t(preview===asset.id?'Arrêter':'Aperçu'))}</button>`:''}<button type="button" class="secondary" data-aa-choose="${asset.id}">${escape(t('Utiliser sur cette page'))}</button></div></article>`).join('')}</div><p id="aaGalleryFeedback" role="status"></p>`;
  dialog.querySelector('#aaGalleryClose').onclick=()=>dialog.close();dialog.querySelector('#aaGalleryTarget').onchange=e=>target=e.target.value;
  dialog.querySelectorAll('[data-aa-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.aaTab;preview=null;paint();});
  dialog.querySelectorAll('[data-aa-preview]').forEach(b=>b.onclick=()=>{preview=preview===b.dataset.aaPreview?null:b.dataset.aaPreview;paint();});
  dialog.querySelectorAll('[data-aa-choose]').forEach(b=>b.onclick=()=>{const asset=assets.find(x=>x.id===b.dataset.aaChoose);if(asset.kind==='sticker')AngelinaUI.customize(target,{sticker:asset.file});else AngelinaUI.customize(target,{scene:asset.scene});dialog.querySelector('#aaGalleryFeedback').textContent=t('Illustration enregistrée pour cette page.');});
  dialog.querySelector('#aaGalleryReset').onclick=()=>{AngelinaUI.customize(target,null);dialog.querySelector('#aaGalleryFeedback').textContent=t('Choix automatiques rétablis.');};
 }
 async function open(){
  target=[...document.querySelectorAll('dialog[open].aa-surface,main>.aa-surface:not(.hidden)')].find(node=>labels[node.id])?.id||'jobsView';
  if(!dialog){dialog=document.createElement('dialog');dialog.id='angelinaGallery';dialog.setAttribute('aria-labelledby','angelinaGalleryTitle');document.body.append(dialog);dialog.addEventListener('close',()=>{preview=null;dialog.querySelectorAll('img').forEach(img=>{if(img.src.endsWith('.gif'))img.src=img.src.replace('.gif','.png');});});}
  try{if(!assets.length){const response=await fetch('/static/artwork/angelina/catalog.json');if(!response.ok)throw Error('Material catalog unavailable');assets=await response.json();}paint();dialog.showModal();}catch(error){dialog.textContent=error.message;dialog.showModal();}
 }
 return {open};
})();
