/* Configure once, then use the existing confirmed-job queue. */
window.Accounts=(()=>{
  let owner='default',registry={items:[]};
  const originalFetch=window.fetch.bind(window);
  let resolveReady;
  const ready=new Promise(resolve=>resolveReady=resolve);
  window.fetch=async(input,options={})=>{
    if(typeof input==='string'&&input.startsWith('/api/')&&input!=='/api/candidates'){
      await ready;
      const headers=new Headers(options.headers);headers.set('X-Candidate-ID',owner);
      options={...options,headers};
    }
    return originalFetch(input,options);
  };
  const words={fr:['Profils & comptes','Fermer','Qui postule ?','Chaque personne a ses propres CV, offres, comptes et session. Arrêtez les tâches avant de changer.','Nom du nouveau profil','Créer et utiliser','Utiliser ce profil','1 · Complétez votre profil et ajoutez votre CV','Ouvrir mon profil','2 · Enregistrez votre compte du site recruteur','Page de connexion HTTPS','Email / identifiant','Mot de passe','Autoriser la connexion automatique','Enregistrer le compte','Supprimer','3 · Après l’ajout d’une offre confirmée dans la file','Démarrer la file automatiquement','Envoyer automatiquement si le formulaire est complet','Enregistrer les options','Réponse manquante, consentement, CAPTCHA ou MFA : la file s’arrête. Un envoi incertain n’est jamais réessayé automatiquement.','4 · Facultatif : connecter Gmail','Accès en lecture seule. Les codes et réinitialisations ne sont pas encore automatisés.','Google client ID','Google client secret','Enregistrer la configuration Google','Connecter Gmail','Déconnecter localement','Non configuré','Configuré · non connecté','Connecté','Guide de configuration Gmail','Enregistré','Mot de passe oublié ? Ouvrez la page de connexion et utilisez le lien de récupération du site. Aucun compte existant n’est réinitialisé automatiquement.'],
zh:['个人档案与账号','关闭','这次替谁投递？','每个人分别保存简历、岗位、账号和浏览器登录状态。切换前请停止正在运行的任务。','新档案的名字','创建并切换','使用这个档案','1 · 填好个人信息，上传这个人的简历','打开我的个人资料','2 · 保存你在招聘网站已有的账号','网站登录页（HTTPS）','邮箱 / 用户名','密码','允许自动登录','保存账号','删除','3 · 已人工确认的岗位加入队列后，怎么处理？','加入后自动开始处理队列','表单填写完整时自动发送申请','保存设置','缺少答案、隐私同意、验证码或多重验证时会暂停。发送结果不确定时不会自动重发。','4 · 可选：连接 Gmail','只读权限。连接邮箱后，目前还不会自动读取验证码或重置密码。','Google 客户端 ID','Google 客户端密钥','保存 Google 配置','连接 Gmail','断开本地连接','尚未配置','已配置 · 尚未连接','已连接','Gmail 配置指引','已保存','忘记密码？打开登录页，点击网站的找回密码链接。发现已有账号时不会自动重置密码。']};
  const mailCopy={zh:['允许自动读取当前招聘网站的登录验证码','先连接 Gmail，再按需启用。仅尝试同一网站发给当前账号的近期验证码；不确定时请在保留的页面手动完成。首次登录后会保存登录状态，通常无需重复登录。'],
fr:['Lire automatiquement les codes de connexion du recruteur','Connectez Gmail puis activez cette option si souhaité. Codes récents du même site et du même compte uniquement. En cas de doute, terminez sur la page conservée. La session est ensuite réutilisée.']};
  const mc=i=>(mailCopy[Locale.language]||mailCopy.fr)[i];
  const siteWords={zh:['已保存的网站账号','不同网站的账号分别保存。例如：Indeed 和 HelloWork 各保存一份，互不覆盖。','还没有保存网站账号。先添加一个你要用来投递的网站。','添加网站账号','平台名称（选填，例如 Indeed）','编辑','取消编辑','不修改密码时留空，继续使用已保存的密码。','自动登录已开启','自动登录已关闭','这个网站的账号已保存，其他网站的账号不变。','首次添加账号时请填写密码。','打开登录页','删除这个网站保存的账号？','添加一个网站的账号','编辑这个网站的账号','同一网站再次保存会更新已有账号；不同网站的账号互不影响。'],
fr:['Comptes enregistrés par site','Un compte par site : Indeed et HelloWork sont enregistrés séparément, sans se remplacer.','Aucun compte enregistré. Ajoutez un site sur lequel vous souhaitez postuler.','Ajouter un compte de site','Nom du site (facultatif, par ex. Indeed)','Modifier','Annuler la modification','Laissez vide pour conserver le mot de passe enregistré.','Connexion automatique activée','Connexion automatique désactivée','Compte enregistré pour ce site. Les autres comptes restent inchangés.','Renseignez le mot de passe lors du premier ajout.','Ouvrir la connexion','Supprimer le compte enregistré pour ce site ?','Ajouter le compte d’un site','Modifier le compte de ce site','Enregistrer à nouveau le même site met à jour son compte. Les autres sites restent indépendants.']};
  const st=i=>(siteWords[Locale.language]||siteWords.fr)[i];
  const t=i=>(words[Locale.language]||words.fr)[i];
  const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let dialog,nav;
  const api=async(url,method='GET',body)=>{const r=await fetch(url,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw Error(Locale.t(data.detail||'Erreur'));return data;};
  const label=(i,id,type='text')=>`<label>${safe(t(i))}<input id="${id}" type="${type}" ${type==='password'?'autocomplete="new-password"':'autocomplete="off"'} required></label>`;
  const notice=message=>{document.getElementById('accountsNotice').textContent=message;};
  async function render(){
    const [registry,accounts,gmail,profile]=await Promise.all([api('/api/candidates'),api('/api/accounts'),api('/api/gmail'),api('/api/profile')]);
    dialog.innerHTML=`<header><h2>${safe(t(0))}</h2><button id="accountsClose" type="button">${safe(t(1))}</button></header><p id="accountsNotice" role="status" aria-live="polite"></p><h3>${safe(t(2))}</h3><p>${safe(t(3))}</p><div class="candidate-grid">${registry.items.map(row=>`<article class="candidate-card ${row.active?'selected':''}"><span class="candidate-avatar" aria-hidden="true">${safe(row.name.slice(0,2))}</span><strong>${safe(row.name)}</strong><p>${safe(row.identity?.city||'')}</p><button type="button" data-candidate="${row.id}" ${row.active?'disabled':''}>${safe(t(6))}${row.active?' ✓':''}</button></article>`).join('')}</div><form id="candidateCreate">${label(4,'candidateName')}<button>${safe(t(5))}</button></form><h3>${safe(t(7))}</h3><button id="openCandidateProfile" type="button">${safe(t(8))}</button><h3>${safe(t(9))}</h3><p>${safe(st(1))}</p><h4>${safe(st(0))} (${accounts.length})</h4><div id="savedAccounts" role="list">${accounts.length?accounts.map((account,index)=>`<article class="website-account" role="listitem" data-account-origin="${safe(account.origin)}"><h4>${safe(account.site_name||new URL(account.origin).hostname)}</h4><p class="website-origin">${safe(account.origin)}</p><p>${safe(t(11))}: <b>${safe(account.username)}</b></p><label class="account-check"><input type="checkbox" data-toggle-account="${index}" ${account.enabled?'checked':''}>${safe(st(account.enabled?8:9))}</label><div class="website-account-actions"><a class="button" href="${safe(account.login_url)}" target="_blank" rel="noopener noreferrer">${safe(st(12))}</a><button type="button" data-edit-account="${index}">${safe(st(5))}</button><button type="button" data-remove-account="${index}">${safe(t(15))}</button></div></article>`).join(''):`<p>${safe(st(2))}</p>`}</div><button id="accountAdd" type="button" class="secondary compact">${safe(st(3))}</button><details id="accountEditor" ${accounts.length?'':'open'}><summary id="accountEditorTitle">${safe(st(14))}</summary><form id="accountSave"><label>${safe(st(4))}<input id="accountSiteName" maxlength="80" autocomplete="off" placeholder="Indeed / HelloWork / …"></label>${label(10,'accountURL','url')}${label(11,'accountUser')}${label(12,'accountPassword','password')}<p id="accountPasswordHint" class="small">${safe(st(11))}</p><label class="account-check"><input id="accountEnabled" type="checkbox" checked>${safe(t(13))}</label><p class="small">${safe(st(16))}</p><div class="website-account-actions"><button class="primary">${safe(t(14))}</button><button id="accountCancel" type="button">${safe(st(6))}</button></div></form></details><details><summary>${safe(t(33).split(/[?？]/)[0])}?</summary><p>${safe(t(33))}</p></details><h3>${safe(t(16))}</h3><form id="automationOptions"><label><input id="autoStartQueue" type="checkbox" ${profile.automation?.auto_start_queue?'checked':''}>${safe(t(17))}</label><label><input id="autoSubmit" type="checkbox" ${profile.automation?.auto_submit?'checked':''}>${safe(t(18))}</label><p>${safe(t(20))}</p><button>${safe(t(19))}</button></form><h3>${safe(t(21))}</h3><p>${safe(mc(1))}</p><p>${safe(t(gmail.connected?30:gmail.configured?29:28))} ${safe(gmail.email||'')}</p><a href="/api/gmail/guide?language=${Locale.language}" target="_blank" rel="noopener">${safe(t(31))}</a><label class="account-check"><input id="gmailAutoCodes" type="checkbox" ${gmail.auto_codes?'checked':''} ${gmail.connected?'':'disabled'}>${safe(mc(0))}</label><form id="gmailConfigure">${label(23,'googleClientID')}${label(24,'googleClientSecret','password')}<button>${safe(t(25))}</button></form><button id="gmailConnect" type="button" ${gmail.configured?'':'disabled'}>${safe(t(26))}</button><a id="gmailAuthorize" target="_blank" rel="noopener noreferrer" hidden>${safe(t(26))} ↗</a><button id="gmailDisconnect" type="button" ${gmail.connected?'':'disabled'}>${safe(t(27))}</button>`;
    if(window.PlatformLogins)PlatformLogins.mount(dialog,site=>{
      const existing=accounts.find(account=>new URL(account.origin).origin===new URL(site.url).origin);
      edit(existing||null);
      if(!existing){document.getElementById('accountSiteName').value=site.label;document.getElementById('accountURL').value=site.url;}
      const editor=document.getElementById('accountEditor');
      editor.style.scrollMarginTop=((dialog.querySelector(':scope > header')?.getBoundingClientRect().height||0)+16)+'px';editor.scrollIntoView({behavior:'smooth',block:'start'});
      document.getElementById('accountUser').focus({preventScroll:true});
    });
    document.getElementById('accountsClose').onclick=()=>dialog.close();
    document.getElementById('openCandidateProfile').onclick=()=>{dialog.close();showView('profile');};
    const run=fn=>async event=>{event?.preventDefault();const button=event?.submitter||event?.currentTarget;if(button?.tagName==='BUTTON')button.disabled=true;try{await fn();}catch(e){notice(e.message);}finally{if(button?.isConnected&&button.tagName==='BUTTON')button.disabled=false;}};
    dialog.querySelectorAll('[data-candidate]').forEach(button=>button.onclick=run(async()=>{await api(`/api/candidates/${button.dataset.candidate}/activate`,'POST');location.reload();}));
    document.getElementById('candidateCreate').onsubmit=run(async()=>{const result=await api('/api/candidates','POST',{name:document.getElementById('candidateName').value});await api(`/api/candidates/${result.id}/activate`,'POST');location.reload();});
    document.getElementById('accountSave').onsubmit=run(async()=>{await api('/api/accounts','PUT',{site_name:document.getElementById('accountSiteName').value,login_url:document.getElementById('accountURL').value,username:document.getElementById('accountUser').value,password:document.getElementById('accountPassword').value,enabled:document.getElementById('accountEnabled').checked});await render();notice(st(10));});
    dialog.querySelectorAll('[data-remove-account]').forEach(button=>button.onclick=run(async()=>{if(!confirm(st(13)))return;await api('/api/accounts?login_url='+encodeURIComponent(accounts[Number(button.dataset.removeAccount)].login_url),'DELETE');await render();}));
    let editing=null;
    const field=id=>document.getElementById(id);
    function edit(account){
      editing=account;field('accountSave').reset();
      field('accountSiteName').value=account?.site_name||'';
      field('accountURL').value=account?.login_url||'';field('accountURL').readOnly=Boolean(account);
      field('accountUser').value=account?.username||'';field('accountPassword').value='';field('accountPassword').required=!account;
      field('accountEnabled').checked=account?.enabled??true;
      field('accountPasswordHint').textContent=st(account?7:11);field('accountEditorTitle').textContent=st(account?15:14);
      field('accountEditor').open=true;field('accountSiteName').focus();
    }
    field('accountAdd').onclick=()=>edit(null);
    field('accountCancel').onclick=()=>{edit(null);field('accountEditor').open=false;field('accountAdd').focus();};
    field('accountUser').oninput=()=>{field('accountPassword').required=!editing||field('accountUser').value.trim()!==editing.username;};
    dialog.querySelectorAll('[data-edit-account]').forEach(button=>button.onclick=()=>edit(accounts[Number(button.dataset.editAccount)]));
    dialog.querySelectorAll('[data-toggle-account]').forEach(checkbox=>checkbox.onchange=run(async()=>{
      const account=accounts[Number(checkbox.dataset.toggleAccount)];const enabled=checkbox.checked;checkbox.disabled=true;
      try{await api('/api/accounts','PUT',{...account,password:'',enabled});await render();notice(st(10));}
      catch(error){checkbox.checked=account.enabled;throw error;}
      finally{if(checkbox.isConnected)checkbox.disabled=false;}
    }));
    document.getElementById('automationOptions').onsubmit=run(async()=>{await api('/api/automation/options','PUT',{auto_submit:document.getElementById('autoSubmit').checked,auto_start_queue:document.getElementById('autoStartQueue').checked});Coach.configure(await api('/api/profile'));notice(t(32));});
    document.getElementById('gmailAutoCodes').onchange=run(async()=>{await api('/api/gmail/verification','PUT',{enabled:document.getElementById('gmailAutoCodes').checked});notice(t(32));});
    document.getElementById('gmailConfigure').onsubmit=run(async()=>{await api('/api/gmail/config','PUT',{client_id:document.getElementById('googleClientID').value,client_secret:document.getElementById('googleClientSecret').value});await render();notice(t(32));});
    document.getElementById('gmailConnect').onclick=run(async()=>{const result=await api('/api/gmail/connect','POST');const link=document.getElementById('gmailAuthorize');link.href=result.authorization_url;link.hidden=false;link.focus();});
    document.getElementById('gmailDisconnect').onclick=run(async()=>{await api('/api/gmail','DELETE');await render();});
  }
  async function init(){
    try{const response=await originalFetch('/api/candidates');const data=await response.json();owner=data.active_id||'default';registry=data;}
    catch{registry={items:[{id:owner,name:'—'}]};}
    finally{resolveReady();}
    const switchLabels={zh:'当前档案',
fr:'Profil actif'};
    const switcher=document.createElement('div');switcher.className='profile-switcher';
    const caption=document.createElement('label');caption.htmlFor='candidateSelect';caption.textContent=switchLabels[Locale.language]||switchLabels.fr;
    const select=document.createElement('select');select.id='candidateSelect';
    const rows=registry.items?.length?registry.items:[{id:owner,name:'Current profile'}];
    rows.forEach(row=>{const option=document.createElement('option');option.value=row.id;option.textContent=row.name;select.append(option);});select.value=owner;
    const status=document.createElement('p');status.id='candidateSwitchStatus';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    switcher.append(caption,select,status);document.querySelector('.language-control').after(switcher);
    select.onchange=async()=>{
      if(select.value===owner)return;
      select.disabled=true;status.textContent='';
      try{await api(`/api/candidates/${select.value}/activate`,'POST');location.reload();}
      catch(error){select.value=owner;select.disabled=false;status.textContent=Locale.t(error.message);}
    };
    document.addEventListener('localechange',()=>{caption.textContent=switchLabels[Locale.language]||switchLabels.fr;});
    nav=document.createElement('button');nav.type='button';nav.id='accountsNav';nav.className='navmain';nav.textContent=t(0);
    document.querySelector('.primary-nav').append(nav);
    dialog=document.createElement('dialog');dialog.id='accountsDialog';dialog.setAttribute('aria-label',t(0));document.body.append(dialog);
    nav.onclick=async()=>{dialog.innerHTML=`<p role="status">…</p>`;dialog.showModal();try{await render();}catch(e){dialog.innerHTML=`<p role="alert">${safe(e.message)}</p><button type="button">${safe(t(1))}</button>`;dialog.querySelector('button').onclick=()=>dialog.close();}};
    const loginNav=document.createElement('button');loginNav.type='button';loginNav.id='platformLoginNav';loginNav.className='navmain';
    const loginLabel=()=>({zh:'平台登录',
fr:'Connexion plateformes'}[Locale.language]||'Platform sign-in');
    loginNav.textContent=loginLabel();nav.after(loginNav);
    loginNav.onclick=async()=>{
      await nav.onclick();await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      const section=document.getElementById('platformLogins');
      if(section){section.style.scrollMarginTop=((dialog.querySelector(':scope > header')?.getBoundingClientRect().height||0)+16)+'px';section.scrollIntoView({behavior:'smooth',block:'start'});}
    };
    document.addEventListener('localechange',()=>{loginNav.textContent=loginLabel();});
    document.addEventListener('localechange',()=>{nav.textContent=t(0);dialog.setAttribute('aria-label',t(0));if(dialog.open)render().catch(e=>notice(e.message));});
  }
  const actionWords={fr:['Postuler automatiquement','Préparer automatiquement','Vérifier cette offre d’abord'],
zh:['自动投递这个岗位','自动准备这个岗位','先人工确认这个岗位']};
  return {actionLabel:index=>(actionWords[Locale.language]||actionWords.fr)[index],init,ready,key:key=>`${owner}:${key}`,get owner(){return owner;},words};
})();
