// SPDX-License-Identifier: GPL-3.0-or-later
// Bounded navigation-only bridge; see NOTICE.md.
(()=>{
 const token=new URLSearchParams(location.hash.slice(1)).get('token');
 const tell=(type,extra={})=>parent.postMessage({type,token,...extra},'*');
 let active=null,quiet=null;
 document.addEventListener('ef-action',event=>tell('jaa-menu:navigate',{action:event.detail.action}));
 document.addEventListener('click',event=>{if(event.target.id==='efMenu'||event.target.closest('[data-action="close"]'))tell('jaa-menu:back');});
 document.addEventListener('keydown',event=>{if((event.key==='Escape'||event.key==='Tab'&&!event.shiftKey&&!event.ctrlKey&&!event.altKey&&!event.metaKey)&&!event.repeat&&!event.target.closest('input,textarea,select,audio,[contenteditable=true]')){event.preventDefault();event.stopImmediatePropagation();tell('jaa-menu:back');}},true);
 window.addEventListener('message',event=>{
  const data=event.data;
  if(event.source!==parent||!data||data.token!==token)return;
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
     text.removeAttribute('transform');text.textContent=item.short;
     // Fit the rendered glyphs, not an estimated character count; French and
     // Chinese labels must both stay inside their own card.
     text.setAttribute('font-size',text.dataset.labelSize);
     const measured=text.getComputedTextLength(),limit=+text.dataset.labelWidth;
     if(measured>limit&&text.closest('.ef-rtile')&&(/\s/.test(item.short)||/[\u3400-\u9fff]/.test(item.short))){
      const label=item.short;let split=1,best=Infinity;
      const spaces=[...label].map((char,i)=>char===' '?i:-1).filter(i=>i>0);
      const candidates=spaces.length?spaces:Array.from({length:label.length-1},(_,i)=>i+1);
      for(const i of candidates){const width=Math.max(text.getSubStringLength(0,i),text.getSubStringLength(i,label.length-i));if(width<best){best=width;split=i;}}
      text.textContent='';text.setAttribute('font-size',Math.min(+text.dataset.labelSize,+text.dataset.labelSize*limit/best));
      for(const [i,line] of [label.slice(0,split).trim(),label.slice(split).trim()].entries()){
       const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');span.setAttribute('x',text.getAttribute('x'));span.setAttribute('y',+text.getAttribute('y')+(i?7:-13));span.textContent=line;text.append(span);
      }
     }else if(measured>limit)text.setAttribute('font-size',+text.dataset.labelSize*(limit/measured));
     // Ink bounds may extend beyond advance width for bold CJK glyphs.
     const ink=text.getBBox().width;
     if(ink>limit)text.setAttribute('font-size',+text.getAttribute('font-size')*(limit/ink)*.99);
     if(text.closest('.ef-disclabels')){const box=text.getBBox();text.setAttribute('transform',`translate(${Number(text.getAttribute('x'))-box.x-box.width/2} ${904-box.y-box.height/2})`);}
     if(text.closest('.ef-rtile')){const box=text.getBBox();text.setAttribute('transform',`translate(${53.5-box.x-box.width/2} ${78-box.y-box.height/2})`);}
    }
   }
  }
 });
 tell('jaa-menu:ready');
})();
