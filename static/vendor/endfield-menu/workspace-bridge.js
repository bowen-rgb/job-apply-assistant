// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded navigation-only bridge; see NOTICE.md.
(()=>{
 const token=new URLSearchParams(location.hash.slice(1)).get('token');
 const tell=(type,extra={})=>parent.postMessage({type,token,...extra},'*');
 let active=null,quiet=null;
 document.addEventListener('ef-action',event=>tell('jaa-menu:navigate',{action:event.detail.action}));
 document.addEventListener('click',event=>{if(event.target.id==='efMenu'||event.target.closest('[data-action="close"]'))tell('jaa-menu:back');});
 document.addEventListener('keydown',event=>{if((event.key==='Escape'||event.key==='Tab'&&!event.shiftKey&&!event.ctrlKey&&!event.altKey&&!event.metaKey)&&!event.repeat&&!event.target.closest('input,textarea,select,audio,[contenteditable=true]')){event.preventDefault();event.stopImmediatePropagation();tell('jaa-menu:back');}},true);
 document.addEventListener('jaa-widget:locate',()=>tell('jaa-menu:locate'));
 window.addEventListener('message',event=>{
  const data=event.data;
  if(event.source!==parent||!data||data.token!==token)return;
  if(data.type==='jaa-menu:location'){EF.widgets.location(data);return;}
  if(data.type!=='jaa-menu:state')return;
  document.documentElement.lang=data.language;
  document.body.classList.toggle('jaa-quiet',!!data.quiet);
  if(active!==data.active){if(data.active)EF.menu.setClosed(false);else EF.menu.setClosed(true);}
  if(quiet!==data.quiet||active!==data.active){if(data.quiet||!data.active)EF.scene.pause();else EF.scene.resume();}
  active=data.active;quiet=data.quiet;EF.widgets.update(data);
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
