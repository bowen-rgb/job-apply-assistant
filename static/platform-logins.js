/* Refactoring UI constraint brief: platform + session status are primary, next action
   secondary, saved time tertiary. Reuse website-account cards and existing tokens;
   one guided save action, explicit status text, no timed browser interaction. */
window.PlatformLogins=(()=>{
 const text={
 zh:['招聘平台登录','先点“去登录”，在专用 Chrome 完成登录，再点“已登录，保存会话”。以后投递复用当前档案的会话，失效时才需要重新登录。','去登录','回到登录窗口','已登录，保存会话','清除本地会话','尚未连接','等待你完成登录','正在打开登录页','正在检查并保存','会话已保存','需要完成登录或验证','需要人工验证','登录窗口已关闭，请重新打开','保存失败，请重试','保存时已验证','未确认登录成功，投递时再核验','已保存时间：','操作失败，请重试','仅清除当前档案的平台会话，不删除网站账号。继续？','1jeune1solution 是岗位聚合入口，无需单独登录；投递时使用原始招聘网站的账号。','会话保存在本机并加密，不同个人档案分别保存。登录成功并保存后，该登录窗口会关闭；不会发送申请。'],
 en:['Recruitment platform sign-in','Open sign-in, finish in dedicated Chrome, then save the session. Applications reuse this profile’s session until it expires.','Sign in','Return to sign-in','Signed in · save session','Clear local session','Not connected','Waiting for you to sign in','Opening sign-in','Checking and saving','Session saved','Finish sign-in or verification','Human verification required','Window closed · open it again','Save failed · try again','Verified when saved','Sign-in not confirmed; checked again when applying','Saved: ','Action failed · try again','Clear this profile’s local session? The website account is kept.','1jeune1solution aggregates jobs and needs no separate sign-in; use the original recruiter account when applying.','Sessions are encrypted locally and separated by profile. Saving closes this sign-in window and never sends an application.'],
 fr:['Connexion aux plateformes','Ouvrez la connexion dans Chrome dédié, connectez-vous puis enregistrez la session. Les candidatures réutilisent la session de ce profil jusqu’à son expiration.','Se connecter','Revenir à la connexion','Connecté · enregistrer la session','Effacer la session locale','Non connecté','À vous de vous connecter','Ouverture de la connexion','Vérification et enregistrement','Session enregistrée','Terminez la connexion ou la vérification','Vérification humaine nécessaire','Fenêtre fermée · rouvrez-la','Échec · réessayez','Vérifiée à l’enregistrement','Connexion non confirmée ; à vérifier lors de la candidature','Enregistrée : ','Échec · réessayez','Effacer la session locale de ce profil ? Le compte du site est conservé.','1jeune1solution regroupe les offres ; connectez-vous au site recruteur pour postuler.','Sessions chiffrées localement et séparées par profil. Enregistrer ferme cette fenêtre, sans envoyer de candidature.']};
 const t=i=>(text[Locale.language]||text.en)[i];
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={not_connected:6,waiting:7,opening:8,checking:9,saved:10,needs_login:11,verification:12,closed:13,error:14};
 async function api(path,method='GET'){
  const r=await fetch('/api/platform-logins'+path,{method});const data=await r.json();if(!r.ok)throw Error(data.detail||t(18));return data;
 }
 function mount(dialog){
  let root=document.createElement('section');root.id='platformLogins';root.className='platform-logins';
  const before=dialog.querySelector('#savedAccounts');before?.parentNode.insertBefore(root,before.previousElementSibling);
  if(!root.isConnected)return;
  root.innerHTML=`<h3>${esc(t(0))}</h3><p>${esc(t(1))}</p><p class="small">${esc(t(21))}</p><div class="platform-login-grid"></div><p class="small">${esc(t(20))}</p><p class="platform-login-notice" role="status" aria-live="polite"></p>`;
  const grid=root.querySelector('.platform-login-grid'),notice=root.querySelector('.platform-login-notice');
  let timer;
  async function render(){
   if(!root.isConnected||!dialog.open){clearTimeout(timer);return;}
   try{
    const rows=await api('');
    if(!root.isConnected)return;
    grid.innerHTML=rows.map(r=>`<article class="website-account"><h4>${esc(r.label)}</h4><p role="status">${esc(t(labels[r.state]??6))}${r.state==='saved'?' · '+esc(t(r.verified?15:16)):''}</p>${r.saved_at?`<p class="small">${esc(t(17))}${esc(new Date(r.saved_at).toLocaleString())}</p>`:''}${r.error?`<p class="small" role="alert">${esc(r.error)}</p>`:''}<div class="website-account-actions"><button type="button" data-site="${esc(r.key)}" data-login="open">${esc(t(r.window_open?3:2))}</button>${r.window_open?`<button type="button" class="primary" data-site="${esc(r.key)}" data-login="save" ${r.state==='opening'||r.state==='checking'?'disabled':''}>${esc(t(4))}</button>`:''}${r.saved_at?`<button type="button" class="ghost" data-site="${esc(r.key)}" data-login="disconnect">${esc(t(5))}</button>`:''}</div></article>`).join('');
    grid.querySelectorAll('[data-login]').forEach(b=>b.onclick=async()=>{
     if(b.dataset.login==='disconnect'&&!confirm(t(19)))return;
     b.disabled=true;notice.textContent='';
     try{await api('/'+encodeURIComponent(b.dataset.site)+'/'+b.dataset.login,'POST');await render();}
     catch(e){notice.textContent=e.message;b.disabled=false;}
    });
    clearTimeout(timer);if(rows.some(r=>r.window_open||r.state==='opening'||r.state==='checking'))timer=setTimeout(render,2500);
   }catch(e){notice.textContent=e.message;}
  }
  dialog.addEventListener('close',()=>clearTimeout(timer),{once:true});render();
 }
 return {mount};
})();
