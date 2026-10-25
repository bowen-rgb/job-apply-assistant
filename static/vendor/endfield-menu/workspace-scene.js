// SPDX-License-Identifier: GPL-3.0-or-later
// Local adaptation of ccdr4gon/endfield_menu. See NOTICE.md.
(()=>{
 const EF=window.EF;
 const actions=['overview','guide','accounts','logins','pending','pfe','liked','human','confirmed','submitted','export','sources','resumes','appearance','jobs','pipeline','profile','qr'];
 const scenes=['explore','send','read','photo'];
 EF.workspace={cards:['jobs','pipeline','profile','qr'].map((action,i)=>({action,label:action,art:'local-card-'+i,text:{size:25,anchor:'middle',x:[230],y:[136],width:160}})),
  tiles:actions.map((id,i)=>({id,label:id,art:'local-tile-'+i,text:{size:19,anchor:'middle',x:[53.5],y:[92],width:95}}))};
 const symbol=(id,content,box)=>`<symbol id="${id}" viewBox="${box}">${content}</symbol>`;
 let art=EF.workspace.cards.map((_,i)=>symbol('local-card-'+i,`<image href="/static/artwork/angelina/${scenes[i]}.png" x="185" y="18" width="90" height="90"/>`,'0 0 440 172')).join('');
 const icons=['ic-radar','ic-warn-f','ic-gear-f','ic-mail-f','ic-mail-f','ic-radar','ic-bolt','ic-warn-f','ic-signal','ic-mail-f','ic-mail-f','ic-gear-f','ic-mail-f','ic-gear-f','ic-radar','ic-signal','ic-gear-f','ic-radar'];
 art+=actions.map((_,i)=>symbol('local-tile-'+i,`<svg x="33" y="15" width="42" height="42"><use href="#${icons[i]}"/></svg>`,'0 0 107 104')).join('');
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
