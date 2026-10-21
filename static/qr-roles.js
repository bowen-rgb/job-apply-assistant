/* Employer listings remain discoveries until the user selects an actual role.
   Filters keep missing dates visible by default; no fabricated start dates. */
window.QRRoleBrowser=(()=>{
 const states=new Map(),t=s=>Locale.t(s),e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c])),norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 const names={mechanical:'Mécanique',simulation:'Simulation',control:'Robotique / commande',digital:'Numérique / logiciel',research:'Recherche'};
 const state=id=>{if(!states.has(id))states.set(id,{from:'',to:'',place:'',direction:'',unknown:true,keyword:'',limit:40});return states.get(id);};
 function matches(row,f){
  if(f.keyword&&!f.keyword.split(/[，,;]+/).map(x=>norm(x.trim())).filter(Boolean).some(term=>norm(row.title+' '+(row.body||'')).includes(term)))return false;
  if(f.place&&!(row.location?norm(row.location).includes(norm(f.place)):f.unknown))return false;
  if(f.direction&&!(row.directions?.length?row.directions.includes(f.direction):f.unknown))return false;
  if(f.from||f.to){const month=/^\d{4}-\d{2}/.test(row.start_date||'')?row.start_date.slice(0,7):'';if(!month)return f.unknown;if(f.from&&month<f.from||f.to&&month>f.to)return false;}
  return true;
 }
 function markup(current){
  const f=state(current.id),p=current.preview,c=p.crawl||{},running=current.state==='crawling';
  return `<section id="qrRoleBrowser" class="qr-role-browser"><div class="qr-role-heading"><h4>${e(t('Offres de ce site'))}</h4><button type="button" id="qrCrawl" class="secondary compact" ${current.state!=='draft'?'disabled':''}>${e(t(c.remaining||c.errors?.length?'Continuer la collecte':'Collecter les offres du site'))}</button>${running?`<button type="button" id="qrCrawlStop" class="ghost compact">${e(t('Arrêter la collecte'))}</button>`:''}</div><p class="small" role="status">${e(t(running?'Collecte des offres…':c.status==='complete'?'Collecte terminée':c.status==='empty'?'Aucune offre identifiable trouvée':c.status?'Collecte partielle':'Parcourez le site ici, puis choisissez une offre.'))}${c.status?` · ${c.pages_read||0} ${e(t('pages lues'))} · ${c.discovered||0} ${e(t('offres trouvées'))} · ${c.remaining||0} ${e(t('pages restantes'))}`:''}</p>${p.ai_explanation?`<details class="qr-ai-note"><summary>${e(t('Explication de ChatGPT — à vérifier'))}</summary><p>${e(p.ai_explanation)}</p></details>`:''}${p.ai_error?`<p class="small">${e(t('ChatGPT indisponible. Vérifiez sa connexion dans Chrome.'))}</p>`:''}${c.errors?.length?`<details><summary>${c.errors.length} ${e(t('pages non lues'))}</summary>${c.errors.slice(-8).map(x=>`<p class="small">${e(x.url)} · ${e(x.error)}</p>`).join('')}</details>`:''}${c.capped?`<p class="small">${e(t('Limite de collecte atteinte. La liste peut être incomplète.'))}</p>`:''}
  <div class="qr-role-filters"><label>${e(t('Mots-clés'))}<input id="qrRoleKeyword" value="${e(f.keyword)}" placeholder="robotique, simulation…"></label><label>${e(t('Lieu'))}<input id="qrRolePlace" value="${e(f.place)}" placeholder="Paris, France…"></label><label>${e(t('Domaine'))}<select id="qrRoleDirection"><option value="">${e(t('Tous les domaines'))}</option>${Object.entries(names).map(([key,name])=>`<option value="${key}" ${key===f.direction?'selected':''}>${e(t(name))}</option>`).join('')}</select></label><label>${e(t('Début à partir de'))}<input id="qrRoleFrom" type="month" value="${e(f.from)}"></label><label>${e(t('Début au plus tard'))}<input id="qrRoleTo" type="month" value="${e(f.to)}"></label></div><label class="qr-role-unknown"><input id="qrRoleUnknown" type="checkbox" ${f.unknown?'checked':''}>${e(t('Garder les informations manquantes — à vérifier'))}</label><p class="small">${e(t('La date de publication ne remplace pas la date de début.'))}</p><div id="qrRoleResults"></div></section>`;
 }
 function bind(root,current,onSelect,onCrawl,onStop){
  const outer=root.querySelector('#qrRoleBrowser');if(!outer)return;
  const f=state(current.id),rows=current.preview.opportunities||[];
  const paint=()=>{
   const invalid=f.from&&f.to&&f.from>f.to,filtered=invalid?[]:rows.filter(row=>matches(row,f));
   outer.querySelector('#qrRoleResults').innerHTML=`<p class="small" role="status">${invalid?e(t('La fin doit suivre le début.')):filtered.length+' / '+rows.length+' '+e(t('offres affichées'))}</p><div class="qr-role-cards">${filtered.slice(0,f.limit).map(row=>`<article><h5>${e(row.title)}</h5><p>${e(row.location||t('Lieu à vérifier'))} · ${e(row.start_date||t('Début à vérifier'))}</p><span class="small">${e(t(row.source==='chatgpt_suggestion'?'Lien proposé par ChatGPT — non vérifié':row.verified?'Page de détail lue':'Lien trouvé — détail à lire'))}</span><button type="button" class="secondary compact" data-qr-pick-role="${e(row.url)}" ${current.state!=='draft'?'disabled':''}>${e(t('Choisir cette offre'))}</button><a href="${e(row.url)}" target="_blank" rel="noopener noreferrer">${e(t('Voir le site destinataire'))} ↗</a></article>`).join('')||`<p>${e(t(rows.length?'Aucune offre ne correspond à ces filtres.':'Aucune offre collectée pour le moment.'))}</p>`}</div>${filtered.length>f.limit?`<button type="button" id="qrRoleMore" class="ghost compact">${e(t('Afficher plus'))}</button>`:''}`;
   outer.querySelectorAll('[data-qr-pick-role]').forEach(b=>b.onclick=()=>onSelect(b.dataset.qrPickRole));
   const more=outer.querySelector('#qrRoleMore');if(more)more.onclick=()=>{f.limit+=40;paint();};
  };
  for(const [id,key] of [['qrRoleKeyword','keyword'],['qrRolePlace','place'],['qrRoleDirection','direction'],['qrRoleFrom','from'],['qrRoleTo','to'],['qrRoleUnknown','unknown']]){
   const input=outer.querySelector('#'+id);input.oninput=()=>{f[key]=input.type==='checkbox'?input.checked:input.value;f.limit=40;paint();};
  }
  outer.querySelector('#qrCrawl').onclick=onCrawl;const stop=outer.querySelector('#qrCrawlStop');if(stop)stop.onclick=onStop;paint();
 }
 return {markup,bind,matches};
})();
