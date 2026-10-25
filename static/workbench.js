/* Real owner-scoped snapshots. Charts never infer recruiter outcomes or generate sample data. */
window.Workbench=(()=>{
  const copy={zh:['工作台','先看下一步，再看进度。','刷新数据','每 6 秒更新','连接中断 · 保留上次数据','尚未读取数据','可见岗位','待你确认','队列中','已记录投递','下一步','查看待处理','打开申请队列','上传我的简历','已有简历，可以开始检查岗位。','当前档案还没有简历，先上传再准备申请。','岗位发现趋势','最近 7 天','最近 30 天','每日首次保存的岗位数；这不是投递数量。','岗位来源','点击来源，查看对应岗位。零结果请查看扫描诊断。','申请队列状态','排队','处理中','等你接管','准备失败','已完成','已取消','查看数据表','日期','数量','没有数据','处理中 / 下一份','暂无正在处理的申请','查看岗位','数据已更新','本地记录，投递状态以确认记录为准。','准备失败不代表招聘方拒绝。','当前档案','查看新手指引','已保存岗位总数','其他状态'],
fr:['Tableau de bord','Votre prochaine action, puis votre progression.','Actualiser','Actualisation toutes les 6 secondes','Déconnecté · dernières données conservées','Données non chargées','Offres visibles','À confirmer par vous','Dans la file','Envois enregistrés','Prochaine étape','Ouvrir les tâches','Ouvrir la file','Ajouter mon CV','Votre CV est prêt. Vous pouvez examiner les offres.','Ce profil n’a pas de CV. Ajoutez-en un avant de préparer une candidature.','Découverte des offres','7 derniers jours','30 derniers jours','Offres enregistrées pour la première fois par jour ; ce ne sont pas des envois.','Sources des offres','Cliquez sur une source pour voir ses offres. Sans résultat, consultez le diagnostic du scan.','File de candidatures','En attente','En cours','À reprendre par vous','Préparation échouée','Terminées','Annulées','Voir le tableau','Date','Nombre','Aucune donnée','En cours / prochaine offre','Aucune candidature en cours','Voir les offres','Actualisé','Suivi local ; les envois reposent sur les confirmations enregistrées.','Un échec de préparation n’est pas un refus du recruteur.','Profil actuel','Ouvrir le guide débutant','Total des offres enregistrées','Autres états']};
  const t=i=>(copy[Locale.language]||copy.fr)[i],e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let snapshot=null,busy=false,period=7,last=null,signature='',timer=null,failed=false;
  const root=()=>document.getElementById('overviewView');
  const active=()=>root()&&!root().classList.contains('hidden');
  function day(value){if(!value)return null;const s=String(value);const d=new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(s)?s:s.replace(' ','T')+'Z');return Number.isNaN(d.getTime())?null:[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
  function daily(jobs,days,now=new Date()){
    const rows=[];for(let i=days-1;i>=0;i--){const date=new Date(now);date.setDate(date.getDate()-i);rows.push({date:day(date.toISOString()),n:0});}
    const counts=new Map(rows.map(r=>[r.date,r]));for(const job of jobs){const row=counts.get(day(job.first_seen_at||job.discovered_at));if(row)row.n++;}return rows;
  }
  function table(rows,first){return `<details class="wb-data"><summary>${e(t(29))}</summary><table><thead><tr><th scope="col">${e(first)}</th><th scope="col">${e(t(31))}</th></tr></thead><tbody>${rows.map(r=>`<tr><th scope="row">${e(r.label||r.date)}</th><td>${r.n}</td></tr>`).join('')}</tbody></table></details>`;}
  function bars(rows,kind){const max=Math.max(1,...rows.map(r=>r.n));return rows.map(r=>`<button type="button" class="wb-bar" data-wb-${kind}="${e(r.key)}"><span>${e(r.label)}</span><strong>${r.n}</strong><i aria-hidden="true" style="--bar:${100*r.n/max}%"></i></button>`).join('');}
  function clock(){const node=document.getElementById('wbConnection');if(node){node.classList.toggle('wb-offline',failed);node.textContent=failed?t(4):last?`${t(36)} ${last.toLocaleTimeString(Locale.language)} · ${t(3)}`:t(5);}}
  async function refresh(){
    if(busy||!root())return;busy=true;document.getElementById('wbRefresh')?.setAttribute('disabled','');
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
    try{
      const values=await Promise.all(['/api/jobs','/api/queue','/api/pending-tasks','/api/candidates','/api/resumes'].map(async url=>{const r=await fetch(url,{signal:controller.signal});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}));
      if(!Array.isArray(values[0])||!Array.isArray(values[4]))throw new Error('Invalid snapshot');
      snapshot={jobs:values[0],queue:values[1],tasks:values[2].items||[],owner:values[3].items?.find(x=>x.id===values[3].active_id)?.name||'',resumes:values[4]};
      failed=false;last=new Date();const key=JSON.stringify([snapshot,period,Locale.language,day(last.toISOString())]);if(key!==signature){signature=key;paint();}clock();
    }catch{failed=true;if(!snapshot)paint();clock();}finally{clearTimeout(timeout);busy=false;document.getElementById('wbRefresh')?.removeAttribute('disabled');}
  }
  function paint(){
    const readingScroll=window.scrollY;
    const tablePositions=[...root().querySelectorAll('.wb-data')].map(node=>node.scrollTop);
    const focused=root().contains(document.activeElement)?document.activeElement:null;
    const focusId=focused?.id;
    const focusAction=focused?.getAttributeNames().find(name=>name.startsWith('data-wb-')||name==='data-aa-view');
    const focusValue=focusAction?focused.getAttribute(focusAction):null;
    const focusTable=focused?.matches('summary')?focused.closest('details')?.dataset.table:null;
    document.getElementById('overviewNav').textContent=t(0);
    const s=snapshot,jobs=s?.jobs||[],queue=s?.queue||{},tasks=s?.tasks||[];
    const counts=[['all',6],['human',7],['queued',8],['submitted',9]].map(([key,label])=>({key,label:t(label),n:jobs.filter(j=>matchFilter(j,key)).length}));
    const sourceMap=new Map();for(const job of jobs.filter(j=>matchFilter(j,'all'))){const key=job.provider_key||'';const item=sourceMap.get(key)||{key,label:sourceLabels[key]||job.source||t(32),n:0};item.n++;sourceMap.set(key,item);}
    const sources=[...sourceMap.values()].sort((a,b)=>b.n-a.n);
    const states=['queued','running','waiting_user','error','done','cancelled'];
    const stateRows=states.map((key,i)=>({key,label:t(23+i),n:Number(queue.counts?.[key]||0)}));
    const others=Object.entries(queue.counts||{}).filter(([key])=>!states.includes(key)).reduce((a,[,n])=>a+Number(n),0);if(others)stateRows.push({key:'other',label:t(42),n:others});
    const dailyRows=daily(jobs,period),max=Math.max(1,...dailyRows.map(x=>x.n)),width=660,height=170,step=600/period;
    const focus=queue.items?.find(x=>x.status==='running')||queue.items?.find(x=>['waiting_user','error'].includes(x.status))||queue.items?.find(x=>x.status==='queued');
    const pending=tasks.filter(x=>x.status==='pending').length,cv=s?.resumes.some(x=>x.active);
    const openTables=[...root().querySelectorAll('details[open]')].map(x=>x.dataset.table);
    root().innerHTML=`<header class="wb-heading"><div class="wb-identity"><span class="wb-wordmark" aria-hidden="true">APPLY<span>FORWARD.</span></span><p class="wb-eyebrow">JOB APPLY / WORKSPACE</p><h1 id="overviewTitle">${e(t(0))}</h1><p>${e(t(1))}</p></div><img class="wb-art" src="/static/artwork/application-orbit.svg" alt="" aria-hidden="true"><div class="wb-sync"><span id="wbConnection" role="status"></span><button id="wbRefresh" type="button">↻ ${e(t(2))}</button></div></header>
      <div class="wb-owner">${e(t(39))} <strong>${e(s?.owner||'—')}</strong><span>${e(t(41))}: ${s?jobs.length:'—'}</span></div>
      <section class="wb-metrics" aria-label="${e(t(0))}">${counts.map((x,i)=>`<button type="button" data-wb-filter="${x.key}"><span class="wb-index" aria-hidden="true">0${i+1}</span><span>${e(x.label)}</span><b>${s?x.n:'—'}</b><span class="wb-arrow" aria-hidden="true">↗</span></button>`).join('')}</section>
      <section class="wb-next"><div><p class="wb-eyebrow">${e(t(10))}</p><h2>${e(cv?t(14):t(15))}</h2><p>${e(t(37))}</p></div><div class="wb-actions">${!cv?`<button type="button" data-wb-view="profile" class="primary">${e(t(13))}</button>`:''}<button type="button" id="wbTasks">${e(t(11))} · ${s?pending:'—'}</button><button type="button" data-wb-view="pipeline">${e(t(12))}</button><button type="button" data-wb-view="guide">${e(t(40))}</button></div></section>
      <div class="wb-grid"><section class="wb-panel wb-trend"><div class="wb-panel-head"><h2>${e(t(16))}</h2><select id="wbPeriod" aria-label="${e(t(16))}"><option value="7" ${period===7?'selected':''}>${e(t(17))}</option><option value="30" ${period===30?'selected':''}>${e(t(18))}</option></select></div><p>${e(t(19))}</p>${s?`<svg viewBox="0 0 ${width} ${height}" aria-hidden="true" class="wb-chart"><line x1="40" y1="140" x2="650" y2="140"/><line class="wb-gridline" x1="40" y1="30" x2="650" y2="30"/><text x="4" y="144">0</text><text x="4" y="34">${max}</text>${dailyRows.map((row,i)=>`<rect x="${42+i*step}" y="${140-110*row.n/max}" width="${Math.max(3,step-5)}" height="${110*row.n/max}"><title>${e(row.date)}: ${row.n}</title></rect>`).join('')}<text x="40" y="166">${dailyRows[0].date.slice(5)}</text><text x="598" y="166">${dailyRows.at(-1).date.slice(5)}</text></svg>${table(dailyRows,t(30))}`:`<p class="wb-empty">${e(t(5))}</p>`}</section>
      <section class="wb-panel"><div class="wb-panel-head"><h2>${e(t(33))}</h2><span aria-hidden="true">↗</span></div><p class="wb-focus-title">${e(focus?.title||t(34))}</p>${focus?`<p>${e(statusLabel(focus.status))} · #${Number(focus.job_id)}</p>`:''}<p>${e(t(38))}</p><button type="button" class="primary" data-wb-view="pipeline">${e(t(12))}</button></section>
      <section class="wb-panel"><div class="wb-panel-head"><h2>${e(t(20))}</h2><span aria-hidden="true">02</span></div><p>${e(t(21))}</p><div class="wb-bars">${sources.length?bars(sources,'source'):`<p class="wb-empty">${e(s?t(32):t(5))}</p>`}</div>${sources.length?table(sources,t(20)):''}</section>
      <section class="wb-panel"><div class="wb-panel-head"><h2>${e(t(22))}</h2><span aria-hidden="true">03</span></div><p>${e(t(38))}</p><div class="wb-bars">${s?bars(stateRows,'queue'):`<p class="wb-empty">${e(t(5))}</p>`}</div>${s?table(stateRows,t(22)):''}</section></div>`;
    window.AngelinaUI?.refresh();
    root().querySelectorAll('details').forEach((d,i)=>{d.dataset.table=String(i);d.open=openTables.includes(String(i));});
    document.getElementById('wbRefresh').onclick=refresh;
    document.getElementById('wbPeriod').onchange=event=>{period=Number(event.target.value);signature='';paint();document.getElementById('wbPeriod').focus({preventScroll:true});};
    document.getElementById('wbTasks').onclick=()=>document.getElementById('pendingTasksNav').click();
    root().querySelectorAll('[data-wb-view],[data-wb-queue]').forEach(b=>b.onclick=()=>showView(b.dataset.wbView||'pipeline'));
    root().querySelectorAll('[data-wb-filter]').forEach(b=>b.onclick=()=>openJobs(b.dataset.wbFilter));
    root().querySelectorAll('[data-wb-source]').forEach(b=>b.onclick=()=>openJobs('all',b.dataset.wbSource));clock();
    root().querySelectorAll('.wb-data').forEach((node,index)=>{node.scrollTop=tablePositions[index]||0;});
    window.scrollTo({top:readingScroll,behavior:'instant'});
    if(focusId)document.getElementById(focusId)?.focus({preventScroll:true});
    else if(focusAction)[...root().querySelectorAll(`[${focusAction}]`)].find(b=>b.getAttribute(focusAction)===focusValue)?.focus({preventScroll:true});
    else if(focusTable!=null)root().querySelector(`details[data-table="${focusTable}"] summary`)?.focus({preventScroll:true});
  }
  async function openJobs(filter,source=null){
    source=source===null?'':source===''?'__unassigned__':source;
    current=filter;qInput.value='';
    if(![...sourceSelect.options].some(x=>x.value===source)){const option=new Option(sourceMapLabel(source),source);sourceSelect.add(option);}
    sourceSelect.value=source;document.querySelectorAll('.filter').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter));
    await load();render();showView('jobs');document.getElementById('q').focus();
  }
  function sourceMapLabel(key){return sourceLabels[key]||snapshot?.jobs.find(j=>key==='__unassigned__'?!j.provider_key:j.provider_key===key)?.source||key;}
  function init(){paint();document.addEventListener('localechange',()=>{signature='';paint();});timer=setInterval(()=>{if(active()&&!document.hidden)refresh();},6000);document.addEventListener('visibilitychange',()=>{if(!document.hidden&&active())refresh();});}
  return {init,refresh,daily};
})();
