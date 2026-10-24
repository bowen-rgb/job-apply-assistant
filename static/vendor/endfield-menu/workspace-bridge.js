// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded navigation-only bridge; see NOTICE.md.
(()=>{
 const token=new URLSearchParams(location.hash.slice(1)).get('token');
 const tell=(type,extra={})=>parent.postMessage({type,token,...extra},'*');
 document.addEventListener('ef-action',event=>tell('jaa-menu:navigate',{action:event.detail.action}));
 document.addEventListener('click',event=>{if(event.target.closest('[data-action="close"]'))tell('jaa-menu:back');});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();tell('jaa-menu:back');}},true);
 window.addEventListener('message',event=>{
  const data=event.data;
  if(event.source!==parent||!data||data.token!==token||data.type!=='jaa-menu:state')return;
  document.documentElement.lang=data.language;
  document.body.classList.toggle('jaa-quiet',!!data.quiet);
  if(data.active)EF.menu.setClosed(false);else EF.menu.setClosed(true);
  if(data.quiet)EF.scene.pause();
  document.getElementById('sceneOwner').textContent=data.owner||'';
  document.getElementById('sceneOwnerHint').textContent=data.profileLabel;
  document.getElementById('sceneHint').textContent=data.hint;
  document.getElementById('sceneSync').textContent=data.sync;
  const stats=document.getElementById('sceneStats');stats.replaceChildren();
  for(const metric of data.metrics||[]){const cell=document.createElement('div'),value=document.createElement('b'),label=document.createElement('span');value.textContent=metric.value;label.textContent=metric.label;cell.append(value,label);stats.append(cell);}
  for(const item of data.entries||[]){
   for(const button of document.querySelectorAll('[data-action],[data-label-route]')){
    if((button.dataset.action||button.dataset.labelRoute)!==item.id)continue;
    button.setAttribute('aria-label',item.label);button.title=item.label;
    for(const text of button.querySelectorAll('text[data-menu-label]')){
     text.textContent=item.short;
     const units=[...item.short].reduce((n,char)=>n+(char.charCodeAt(0)>255?1:.56),0);
     text.setAttribute('font-size',Math.min(+text.dataset.labelSize,+text.dataset.labelWidth/Math.max(units,1)));
    }
   }
  }
 });
 tell('jaa-menu:ready');
})();
