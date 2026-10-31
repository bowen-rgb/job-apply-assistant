// SPDX-License-Identifier: GPL-3.0-or-later
// Local adaptation of ccdr4gon/endfield_menu. See NOTICE.md.
(()=>{
 const EF=window.EF;
 const actions=['waiting','responses','followups','decide','rejected','activity','overview','tracking','liked','pending','sources','tools','accounts','logins','pfe','export','resumes','appearance','jobs','pipeline','profile','qr','guide','submitted'];
 const scenes=['explore','send','read','photo'];
 EF.workspace={cards:['jobs','pipeline','profile','qr'].map((action,i)=>({action,label:action,art:'local-card-'+i,text:{size:25,anchor:'middle',x:[230],y:[136],width:160}})),
  tiles:actions.map((id,i)=>({id,label:id,art:'local-tile-'+i,text:{size:19,anchor:'middle',x:[53.5],y:[92],width:95}}))};
 const symbol=(id,content,box)=>`<symbol id="${id}" viewBox="${box}">${content}</symbol>`;
 let art=EF.workspace.cards.map((_,i)=>symbol('local-card-'+i,`<image href="/static/artwork/angelina/${scenes[i]}.png" x="185" y="18" width="90" height="90"/>`,'0 0 440 172')).join('');
 const icons={waiting:'ic-mail-f',responses:'ic-signal',followups:'ic-radar',decide:'ic-warn-f',rejected:'ic-warn-f',activity:'ic-signal',overview:'ic-radar',tracking:'ic-mail-f',liked:'ic-radar',pending:'ic-bolt',sources:'ic-radar',tools:'ic-gear-f',accounts:'ic-mail-f',logins:'ic-signal',pfe:'ic-warn-f',export:'ic-mail-f',resumes:'ic-mail-f',appearance:'ic-gear-f',jobs:'ic-radar',pipeline:'ic-mail-f',profile:'ic-mail-f',qr:'ic-radar',guide:'ic-warn-f',submitted:'ic-mail-f'};
 art+=actions.map((id,i)=>symbol('local-tile-'+i,`<svg x="33" y="15" width="42" height="42"><use href="#${icons[id]}"/></svg>`,'0 0 107 104')).join('');
 // Existing upstream-owned geometry/sprite; excluded game art is not loaded.
 document.body.insertAdjacentHTML('beforeend',`<svg width="0" height="0" aria-hidden="true"><defs>${art}</defs></svg>`);
 EF.labelSVG=(label,t)=>{
  const x=t.anchor?t.x[0]:t.x.reduce((a,b)=>a+b,0)/t.x.length+t.size/2;
  const y=t.y.reduce((a,b)=>a+b,0)/t.y.length;
  return `<text text-anchor="middle" x="${x}" y="${y}" font-size="${t.size}" data-menu-label data-label-width="${t.width||220}" data-label-size="${t.size}">${label}</text>`;
 };
 EF.backdrop={mount:()=>{}};
 EF.badge={mount:layer=>{layer.insertAdjacentHTML('beforeend',`<section class="jaa-scene-badge"><img src="/static/favicon.svg" alt=""><div><strong id="sceneOwner"></strong><p id="sceneOwnerHint"></p></div></section>`);}};
 EF.topBar={mount:layer=>{layer.insertAdjacentHTML('beforeend',`<div class="jaa-scene-stats" id="sceneStats"></div>`);}};
 EF.news={mount:layer=>{layer.insertAdjacentHTML('beforeend',`<div class="jaa-scene-note"><span>JOB APPLY ASSISTANT</span><p id="sceneHint"></p><small id="sceneSync"></small></div>`);},pause:()=>{},resume:()=>{}};
 EF.levelPill={mount:()=>{}};EF.energy={mount:()=>{}};
 EF.hud={mount:hosts=>{hosts.stage.insertAdjacentHTML('beforeend','<button class="jaa-scene-back" data-action="close" aria-label="Back">×</button>');}};
})();
