/* Native career workflows. Shares candidate, backend, queue and design tokens. */
window.CareerTools = (() => {
  const host=document.createElement('section');host.id='careerTools';host.className='settings-card topgap';
  document.getElementById('toolsContent').append(host);
  const t=(fr,zh)=>Locale.language==='zh'?zh:fr;
  const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api=(path,body,method='POST')=>requestJson('/api/capabilities'+path,body===undefined?{}:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const $=s=>host.querySelector(s);
  let category='prepare',state={},jobs=[],current=null,timer=null,ledgerFiles=[],resetState=null,mailToken=null;
  const kinds=()=>({linkedin_scan:t('Rechercher sur LinkedIn (offres et publications)','搜索 LinkedIn 岗位与帖子'),tailor_cv:t('Adapter le CV à une offre','定制该岗位简历'),research:t('Étudier l’entreprise','研究企业与原始来源'),interview:t('Préparer un entretien','准备面试'),upskill:t('Planifier les compétences à renforcer','分析技能缺口与学习计划'),followup_draft:t('Rédiger une relance','起草跟进邮件'),rank:t('Évaluer plusieurs offres','批量评分与筛选'),profile_expand:t('Extraire des faits des documents','从材料中提取个人事实'),search_plan:t('Développer le plan de recherche','扩展求职方向与搜索计划'),calibration:t('Analyser les résultats réels','从真实投递结果总结经验'),portal_analyze:t('Analyser une nouvelle source publique','分析新的公开招聘来源'),template_test:t('Tester un modèle de document','测试文档模板'),pdf_check:t('Vérifier un PDF','检查 PDF 文本与版面'),archive:t('Archiver le dossier','归档本次申请材料')});
  const states=()=>({queued:t('En attente','等待执行'),running:t('En cours','正在处理'),ready:t('Prêt à consulter','已完成，请查看'),error:t('Échec — voir le détail','失败，请看原因'),cancelled:t('Arrêté','已停止')});
  const button=(action,label,extra='')=>`<button type="button" class="ghost compact" data-tool="${action}" ${extra}>${e(label)}</button>`;
  const field=(name,label,type='text',value='')=>`<label>${e(label)}<input name="${name}" type="${type}" value="${e(value)}" ${type==='password'?'autocomplete="new-password"':''}></label>`;
  const select=(name,label,items)=>`<label>${e(label)}<select name="${name}">${items.map(([id,label])=>`<option value="${e(id)}">${e(label)}</option>`).join('')}</select></label>`;
  const say=text=>{ $('[data-tool-status]').textContent=text; };
  function renderValue(value,depth=0){
    if(value===null||value===undefined)return '—';
    if(typeof value!=='object')return e(String(value));
    if(depth>5)return e(JSON.stringify(value));
    if(Array.isArray(value))return value.length?`<ol>${value.slice(0,100).map(v=>`<li>${renderValue(v,depth+1)}</li>`).join('')}</ol>`:'—';
    return `<dl>${Object.entries(value).filter(([key])=>!['fingerprint','profile_fingerprint','cv_sha256','cv'].includes(key)).map(([key,v])=>`<dt><b>${e(key.replaceAll('_',' '))}</b></dt><dd>${renderValue(v,depth+1)}</dd>`).join('')}</dl>`;
  }
  function shell(){
    host.innerHTML=`      <div class="queue-actions">${button('load',t('Actualiser','刷新状态'))}</div>
      <p data-tool-status role="status" aria-live="polite"></p><div data-tool-body>
      <details open><summary>${e(t('1 · Préparer ou analyser','1 · 准备材料与分析岗位'))}</summary>
      <form data-task-form><div class="form-grid cols2">${select('kind',t('Que souhaitez-vous faire ?','你要做什么？'),Object.entries(kinds()))}
      ${select('job',t('Offre concernée','对应岗位'),[])}${select('backend',t('Modèle à utiliser','使用哪个模型'),['chatgpt','compatible','anthropic','ollama','claude','codex','opencode'].map(x=>[x,x]))}
      ${select('template',t('Modèle de CV (facultatif)','简历模板（可选）'),[['',t('Mise en page intégrée','使用内置排版')]])}</div>
      <div data-params="interview" hidden>${select('stage',t('Type d’entretien','面试环节'),[['technical',t('Technique','技术面试')],['hr',t('Ressources humaines','HR 面试')],['final',t('Final','终面')]])}</div>
      <div data-params="portal_analyze" hidden>${field('url',t('Page publique listant les offres','列出岗位的公开网页'),'url')}</div>
      <div data-params="linkedin_scan" hidden><label>${e(t('Requêtes (3 maximum, une par ligne)','搜索词（最多3条，每行一条）'))}<textarea name="queries" rows="3"></textarea></label>${field('location',t('Région','地区'),'text','Île-de-France, France')}${select('only',t('Rechercher dans','搜索范围'),[['all',t('Offres et publications','岗位与帖子')],['jobs',t('Offres','岗位')],['posts',t('Publications','帖子')]])}${button('linkedin-login',t('Ouvrir ma connexion LinkedIn','打开专用 Chrome 的 LinkedIn 登录页'))}</div>
      <div data-params="profile_expand pdf_check" hidden><fieldset><legend>${e(t('Documents importés à utiliser','选择已导入的材料'))}</legend><div data-documents></div></fieldset></div>
      <div data-params="rank" hidden><fieldset><legend>${e(t('Offres à comparer (100 maximum)','选择要比较的岗位（最多100个）'))}</legend><div data-rank-jobs></div></fieldset></div>
      <p class="small">${e(t('Le modèle choisi reçoit le texte du CV, le profil et les sources nécessaires. Les tâches réseau commencent seulement après ce clic.','点击开始后，所选模型会收到该任务需要的简历、档案和来源文本。联网任务此时才会执行。'))}</p>
      <button type="submit" class="primary compact">${e(t('Démarrer cette tâche','开始这项任务'))}</button></form></details>
      <div data-task-result></div><details><summary>${e(t('Historique des tâches','任务历史与进度'))}</summary><div data-task-list></div></details>
      <details><summary>${e(t('2 · Documents et modèles','2 · 导入材料与模板'))}</summary>
      <p>${e(t('Importez CV, projets ou notes. L’extraction propose des faits sourcés que vous choisirez ensuite.','导入简历、项目说明或笔记。提取后会显示原文依据，由你选择哪些写入档案。'))}</p>
      <details><summary>${e(t('Mes préférences de travail','我喜欢怎样的工作'))}</summary><form data-behavior-form>${field('energizers',t('Ce qui me donne envie de travailler','哪些工作让我有动力'))}${field('drainers',t('Ce que je souhaite éviter','希望避免什么'))}${field('work_style',t('Ma façon de travailler','适合我的工作方式'))}${field('motivation',t('Mon objectif professionnel','职业目标'))}${field('assessment',t('Auto-évaluation ou bilan (facultatif)','自我评价或测评摘要（可选）'))}<button class="ghost compact">${e(t('Enregistrer pour ce profil','保存到当前档案'))}</button></form></details>
      <label>${e(t('Documents (plusieurs fichiers)','个人材料（可多选）'))}<input data-document-files type="file" multiple accept=".pdf,.docx,.txt,.md,.json,.csv,.tsv,.xlsx"></label>${button('documents',t('Importer les documents','导入材料'))}
      <form data-template-form><label>${e(t('Modèle DOCX, LaTeX, Typst, PDF ou ZIP','DOCX／LaTeX／Typst／PDF／ZIP 模板'))}<input name="file" type="file" required accept=".docx,.tex,.typ,.pdf,.zip"></label>${field('label',t('Nom du modèle','模板名称'))}<button class="ghost compact" type="submit">${e(t('Enregistrer le modèle','保存模板'))}</button></form>
      <p class="small">${e(t('LaTeX/Typst : [NAME], [CONTACT], [BODY]. Un compilateur local est nécessaire. Un PDF importé est un document fixe, pas un CV réécrit. DOCX : éditez les paragraphes ci-dessous.','LaTeX／Typst 使用 [NAME]、[CONTACT]、[BODY] 占位符，需要本机编译器。PDF 模板是固定文件，不会被当作已重写的简历。DOCX 可在下面按段落编辑。'))}</p><div data-templates></div><div data-docx-editor></div></details>
      <details><summary>${e(t('3 · Modèles, agents et connexions','3 · 模型、来源与连接设置'))}</summary>
      <form data-choice-form>${select('backend',t('Modèle par défaut pour lettres et évaluations','动机信与复核的默认模型'),['chatgpt','compatible','anthropic','ollama','claude','codex','opencode'].map(x=>[x,x]))}<button class="ghost compact">${e(t('Utiliser ce modèle','使用该模型'))}</button></form>
      <p class="small">${e(t('ChatGPT utilise le Chrome dédié existant. Les agents CLI doivent déjà être installés et connectés. Les clés restent chiffrées sur cette machine.','ChatGPT 继续使用平台专用 Chrome；本地 CLI 需要提前安装并登录。密钥仅加密保存在本机。'))}</p><div data-models></div>${button('search-settings',t('Régions, dates et options de recherche','地区、日期与扫描设置'))}<div data-sources></div>
      <details><summary>Notion</summary><form data-notion-form>${field('target_id',t('ID de destination','目标数据库或数据源 ID'))}${select('target_type',t('Type','类型'),[['data_source','Data source'],['database','Database']])}${field('token',t('Jeton d’intégration','集成密钥'),'password')}<button class="ghost compact">${e(t('Enregistrer','保存设置'))}</button></form>
      ${button('notion-check',t('Vérifier la connexion','检查 Notion 连接'))}<label class="check"><input data-notion-ack type="checkbox">${e(t('Copier le suivi de ce profil dans la destination affichée ci-dessus','将当前档案的申请记录写入上方目标'))}</label>${button('notion-sync',t('Synchroniser vers Notion','同步到 Notion'))}</details>
      <details><summary>${e(t('Envoi de relances Gmail (facultatif)','Gmail 跟进邮件（可选）'))}</summary><p>${e(t('La lecture des réponses reste distincte. Pour créer ou envoyer un brouillon, activez cette option puis reconnectez Gmail pour autoriser la rédaction.','读取招聘反馈与发信分开。若要创建或发送草稿，先启用此项，再重新连接 Gmail 授予撰写权限。'))}</p><label class="check"><input data-gmail-compose type="checkbox">${e(t('Autoriser la rédaction Gmail','启用 Gmail 撰写功能'))}</label>${button('gmail-config',t('Enregistrer ce choix','保存此选择'))}${button('gmail-connect',t('Reconnecter Gmail','重新连接 Gmail'))}<div data-gmail-auth></div></details>
      <details><summary>${e(t('Sources publiques personnalisées','自定义公开招聘来源'))}</summary><p>${e(t('Lancez « Analyser une nouvelle source » en haut. La proposition doit extraire de vraies offres avant activation.','先在上方运行“分析新的公开招聘来源”。只有测试确实能读出岗位，才允许启用。'))}</p><div data-portals></div></details></details>
      <details><summary>${e(t('4 · Salaire, rédaction et données','4 · 薪资、写作检查与数据工具'))}</summary>
      <label>${e(t('Échantillons de salaire CSV/JSON/XLSX','薪资样本 CSV／JSON／XLSX'))}<input data-salary-file type="file" accept=".csv,.json,.xlsx"></label><p class="small">salary, currency, period, basis, company, role, city, source</p>${button('salary-upload',t('Importer les échantillons','导入薪资样本'))}
      <form data-salary-form>${select('dataset',t('Jeu de données','样本集'),[])}<div class="form-grid cols2">${field('company',t('Entreprise','企业'))}${field('role',t('Métier','岗位方向'))}${field('city',t('Ville','城市'))}</div><button class="ghost compact">${e(t('Voir les distributions','查看分布'))}</button></form><div data-salary-result></div>
      <form data-lint-form><label>${e(t('Texte à relire','待检查的文本'))}<textarea name="text" rows="5" required></textarea></label>${field('banned',t('Expressions à éviter (une par ligne)','额外禁用套话（每行一个）'))}${field('claims',t('Compétences à ne pas revendiquer (une par ligne)','不得声称掌握的技能（每行一个）'))}<button class="ghost compact">${e(t('Vérifier le style','检查写作'))}</button></form><div data-lint-result></div>
      <label>${e(t('Importer plusieurs suivis','批量导入申请账本'))}<input data-ledger-files type="file" multiple accept=".csv,.json,.xlsx,.md,.tsv,.db,.sqlite,.sqlite3"></label><label>${e(t('Ou choisir un dossier de suivis','或选择账本文件夹'))}<input data-ledger-folder type="file" webkitdirectory multiple></label>${button('ledger-preview',t('Prévisualiser','预览导入'))}${button('ledger-write',t('Ajouter les nouvelles lignes','导入新增记录'),'disabled')}<div data-ledger-result></div>
      <details><summary>${e(t('Réinitialiser des données locales','重置本地数据'))}</summary>${select('reset-scope',t('Périmètre','范围'),[['profile',t('Profil uniquement','仅个人资料')],['documents',t('Copies de documents','本地材料副本')],['all',t('Profil, offres et documents','个人资料、岗位与材料')]])}<p class="small">${e(t('Le compte, les archives et l’historique des outils sont conservés. Seules les données indiquées dans l’aperçu sont réinitialisées.','账号、归档和工具历史会保留；只重置预览列出的资料、岗位和材料副本。'))}</p>${button('reset-preview',t('Voir l’impact et préparer la sauvegarde','查看影响范围'))}<div data-reset-result></div>${field('reset-confirm',t('Après vérification, saisir RESET','核对后输入 RESET'))}${button('reset',t('Sauvegarder puis réinitialiser','备份并重置'),'disabled')}</details></details></div>`;
    organize();updateParams();
  }
  function organize(){
    const body=$('[data-tool-body]');
    const sections=[...body.children];
    const groups=[['prepare',t('Préparer une candidature','准备申请'),sections.slice(0,3)],['materials',t('Documents et CV','材料与简历'),sections.slice(3,4)],['connections',t('Sources et connexions','来源与连接'),sections.slice(4,5)],['data',t('Données et diagnostics','数据与检查'),sections.slice(5)]];
    const tabs=document.createElement('div');tabs.className='tool-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label',t('Outils','工具分类'));
    for(const [id,label,nodes] of groups){
      const panel=document.createElement('section');panel.id='toolPanel-'+id;panel.dataset.toolPanel=id;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','toolTab-'+id);
      const tab=document.createElement('button');tab.id='toolTab-'+id;tab.type='button';tab.dataset.toolCategory=id;tab.setAttribute('role','tab');tab.setAttribute('aria-controls',panel.id);tab.textContent=label;
      tab.onclick=()=>chooseCategory(id);tab.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const buttons=[...tabs.children],i=buttons.indexOf(tab);const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(i+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[next].click();buttons[next].focus();};tabs.append(tab);
      for(const node of nodes){if(node.tagName==='DETAILS'){const heading=document.createElement('h3');heading.textContent=node.querySelector(':scope > summary').textContent;node.querySelector(':scope > summary').remove();panel.append(heading,...node.childNodes);node.remove();}else panel.append(node);}
      body.append(panel);
    }
    body.prepend(tabs);chooseCategory(category);
    const shortcuts=document.createElement('div');shortcuts.className='tool-shortcuts';
    for(const kind of ['research','tailor_cv','interview','rank']){const b=document.createElement('button');b.type='button';b.textContent=kinds()[kind];b.dataset.taskChoice=kind;b.onclick=()=>{$('[name=kind]').value=kind;updateParams();$('[name=job]').focus();};shortcuts.append(b);}
    $('[data-task-form]').before(shortcuts);$('[name=kind]').value='research';
    const advanced=document.createElement('details');advanced.className='task-options';
    const caption=document.createElement('summary');caption.textContent=t('Modèle et mise en page (facultatif)','模型与排版（可选）');advanced.append(caption,$('[name=backend]').closest('label'),$('[name=template]').closest('label'));$('[data-task-form] .form-grid').after(advanced);

  }
  function chooseCategory(id){category=id;host.querySelectorAll('[data-tool-panel]').forEach(panel=>panel.hidden=panel.dataset.toolPanel!==id);host.querySelectorAll('[data-tool-category]').forEach(tab=>{const active=tab.dataset.toolCategory===id;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;});}
  function updateParams(){const kind=$('[name=kind]')?.value;
    const guidance={research:t('Sélectionnez une offre. Vous obtiendrez les activités de l’entreprise et les sources à vérifier.','选择一个岗位，查看企业业务、岗位任务及原始来源。'),tailor_cv:t('Sélectionnez une offre. Téléchargez et vérifiez le CV proposé avant de l’adopter pour cette candidature.','选择岗位后生成专用简历。先下载核对，再决定是否用于这份申请；原简历保留。'),interview:t('Sélectionnez une offre et le type d’entretien. Préparez vos réponses, puis entraînez-vous dans le résultat.','选择岗位和面试环节，生成准备清单；完成后可继续模拟问答。'),rank:t('Cochez les offres à comparer ci-dessous. Vérifiez les résultats avant de les adopter.','勾选下方要比较的岗位。评分结果需核对后才能采用。'),profile_expand:t('Importez vos documents dans Documents et CV, puis cochez ceux à analyser ici.','先在“材料与简历”导入资料，再勾选本次要分析的材料。'),followup_draft:t('Choisissez une candidature envoyée. Le brouillon doit être vérifié avant tout envoi.','选择已投递的申请，生成跟进草稿。核对收件人和正文后才可发送。')};
    let hint=$('[data-task-hint]');if(!hint){hint=document.createElement('p');hint.dataset.taskHint='';hint.className='task-guidance';$('[data-task-form]').prepend(hint);}hint.textContent=guidance[kind]||t('Complétez les champs ci-dessous, puis démarrez. Le résultat et les éventuelles erreurs apparaîtront sous le formulaire.','填写下方所需信息后开始。结果、进度或失败原因会显示在表单下方。');
    host.querySelectorAll('[data-task-choice]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.taskChoice===kind)));
    host.querySelectorAll('[data-params]').forEach(node=>{node.hidden=!node.dataset.params.split(' ').includes(kind);node.querySelectorAll('input,select,textarea').forEach(input=>input.disabled=node.hidden);});}
  async function load(){
    [state,jobs]=await Promise.all([api(''),requestJson('/api/jobs')]);
    if(!Array.isArray(jobs))jobs=[];
    const jobSelect=$('[name=job]');const old=jobSelect.value;jobSelect.innerHTML=`<option value="">${e(t('Choisir une offre','请选择岗位'))}</option>`+jobs.map(j=>`<option value="${j.id}">${e(j.company+' · '+j.title)}</option>`).join('');jobSelect.value=old;
    $('[data-rank-jobs]').innerHTML=jobs.slice(0,100).map(j=>`<label class="check"><input type="checkbox" data-rank-job value="${j.id}">${e(j.company+' · '+j.title)}</label>`).join('')||e(t('Aucune offre','暂无岗位'));
    $('[data-documents]').innerHTML=(state.documents||[]).map(d=>`<label class="check"><input type="checkbox" data-document-id value="${e(d.id)}">${e(d.name)}</label>`).join('')||e(t('Importez d’abord des documents ci-dessous.','请先在下方导入材料。'));
    $('[name=template]').innerHTML=`<option value="">${e(t('Mise en page intégrée','使用内置排版'))}</option>`+(state.templates||[]).filter(x=>['latex','typst','custom'].includes(x.engine)&&x.tested).map(x=>`<option value="${e(x.id)}">${e(x.label)}</option>`).join('');
    $('[data-task-list]').innerHTML=(state.tasks||[]).map(x=>`<div class="queue-actions">${button('task-open',`#${x.id} · ${kinds()[x.kind]||x.kind} · ${states()[x.state]||x.state}`,`data-id="${x.id}"`)}${['queued','running'].includes(x.state)?button('task-cancel',t('Arrêter','停止'),`data-id="${x.id}"`):''}</div>`).join('')||e(t('Aucune tâche lancée','尚未运行任务'));
    $('[data-templates]').innerHTML=(state.templates||[]).map(x=>`<div>${e(x.label)} · ${e(x.engine)} · ${e(x.tested?t('Testé','已测试'):t('À tester','待测试'))}${button(x.engine==='docx'?'docx':'template-test',x.engine==='docx'?t('Modifier les paragraphes','编辑段落'):t('Tester','测试'),`data-id="${e(x.id)}"`)}</div>`).join('');
    $('[data-models]').innerHTML=['compatible','anthropic','ollama'].map(id=>{const cfg=(state.models?.configured||[]).find(x=>x.id===id)||{};return `<details><summary>${id} · ${e(cfg.model||t('À configurer','待配置'))}</summary><form data-model-form="${id}">${field('base_url','URL', 'url',cfg.base_url||'')}${field('model',t('Modèle','模型名称'),'text',cfg.model||'')}${field('api_key',t('Clé (vide = conserver)','密钥（留空保留原值）'),'password')}<button class="ghost compact">${e(t('Enregistrer','保存设置'))}</button>${button('model-check',t('Tester','测试'),`data-id="${id}"`)}</form></details>`}).join('')+`<p class="small">${e(JSON.stringify(state.models?.agents||{}))}</p>`;
    $('[data-choice-form] [name=backend]').value=state.selected_backend||'chatgpt';$('[data-task-form] [name=backend]').value=state.selected_backend||'chatgpt';
    $('[data-sources]').innerHTML=(state.sources||[]).map(s=>`<details><summary>${e(s.label)} · ${e(s.enabled?t('Activée','已启用'):t('Désactivée','未启用'))} · ${e(s.configured?t('Configuration présente','配置齐全'):t('Clé requise','需要密钥'))}</summary><form data-source-form="${e(s.id)}"><label class="check"><input name="enabled" type="checkbox" ${s.enabled?'checked':''}>${e(t('Inclure dans les scans','加入平台扫描'))}</label>${s.keys.map(k=>field(k,k+(s.credentials[k]?t(' (enregistrée)','（已保存）'):''),'password')).join('')}<div class="form-grid cols2">${field('country',t('Pays (fr, dk…)','国家代码（fr、dk…）'),'text',s.settings?.country||'fr')}${field('location',t('Région','地区'),'text',s.settings?.location||'')}${field('query',t('Requête facultative','自定义查询（可选）'),'text',s.settings?.query||'')}${s.id==='freehire'?field('base_url',t('Adresse du serveur','服务地址'),'url',s.settings?.base_url||'https://freehire.me'):''}</div><button class="ghost compact">${e(t('Enregistrer','保存来源设置'))}</button>${button('source-check',t('Tester une recherche','测试搜索'),`data-id="${e(s.id)}"`)}${s.guide?`<a href="${e(s.guide)}" target="_blank" rel="noopener">${e(t('Obtenir une clé','获取密钥与配置说明'))}</a>`:''}</form></details>`).join('');
    const n=state.notion||{};$('[data-notion-form] [name=target_id]').value=n.target_id||'';$('[data-notion-form] [name=target_type]').value=n.target_type||'data_source';
    $('[data-gmail-compose]').checked=!!state.gmail_compose?.enabled;
    $('[data-gmail-auth]').textContent=state.gmail_compose?.authorized?t('Autorisation de rédaction accordée.','已取得 Gmail 撰写权限。'):t('Rédaction non autorisée : la lecture reste possible.','尚未取得撰写权限；原有读取功能不受影响。');
    for(const [key,value] of Object.entries(state.behavioral||{})){const input=$('[data-behavior-form] [name='+key+']');if(input)input.value=value;}
    $('[data-portals]').innerHTML=(state.portals||[]).map(x=>`<div>${e(x.label)} · ${e(x.url)} · ${e(x.enabled?t('Activée','已启用'):t('Désactivée','未启用'))}${button('portal-probe',t('Tester','测试'),`data-id="${e(x.id)}"`)}${button('portal-enable',x.enabled?t('Désactiver','停用'):t('Activer','启用'),`data-id="${e(x.id)}" data-enabled="${!x.enabled}"`)}</div>`).join('');
    $('[name=dataset]').innerHTML=(state.salary||[]).map(x=>`<option value="${e(x.id)}">${e(x.name)}</option>`).join('');
  }
  async function start(kind,params={},job=null,backend=null){const row=await api('/tasks',{kind,job_id:job,backend:backend||$('[data-task-form] [name=backend]').value,params});await load();await showTask(row.id);}
  async function showTask(id){
    clearTimeout(timer);current=await api('/tasks/'+id);const r=current.result||{};
    $('[data-task-result]').innerHTML=`<h3>#${id} · ${e(kinds()[current.kind]||current.kind)} · ${e(states()[current.state]||current.state)}</h3>${current.error?`<p role="alert">${e(current.error)}</p>`:''}
      ${r.artifact?`<a class="ghost compact" href="/api/capabilities/download?path=${encodeURIComponent(r.artifact)}" download>${e(t('Télécharger le résultat','下载生成的文件'))}</a>`:''}
      ${current.state==='ready'&&current.kind==='tailor_cv'?button('adopt-cv',t('Vérifié : utiliser ce CV pour cette offre','已核对：将这份简历用于该岗位')):''}
      ${r.proposal?button('portal-register',t('Enregistrer cette source désactivée','保存来源（暂不启用）')):''}
      ${current.kind==='linkedin_scan'&&current.state==='ready'?button('linkedin-triage',t('Trier ces offres et publications','筛选这些岗位与帖子')):''}
      ${current.kind==='linkedin_triage'&&current.state==='ready'?`<fieldset>${(r.opportunities||[]).map((x,i)=>`<label class="check"><input data-discovery-index type="checkbox" value="${i}">${e(x.company+' · '+x.title)}</label>`).join('')}</fieldset>${button('accept-discovery',t('Ajouter la sélection aux offres à vérifier','将所选机会加入待核验岗位'))}`:''}
      ${current.state==='ready'&&['profile_expand','rank','search_plan','calibration'].includes(current.kind)?`<fieldset><legend>${e(t('Choisissez ce que vous souhaitez conserver','选择要采用的结果'))}</legend>${(current.kind==='search_plan'?[...(r.roles||[]),...(r.queries||[])]:r.facts||r.ranked||r.lessons||[]).map((x,i)=>`<label class="check"><input data-result-index type="checkbox" value="${i}">${e(typeof x==='string'?x:x.text||(x.company?x.company+' · '+x.title:JSON.stringify(x)))}</label>`).join('')}</fieldset>${button('accept-result',t('Confirmer la sélection','确认采用所选结果'))}`:''}
      ${current.kind==='interview'&&current.state==='ready'?`<label>${e(t('Votre réponse pour l’entretien simulé','模拟面试：输入你的回答'))}<textarea data-mock-answer rows="4"></textarea></label>${button('mock',t('Recevoir un retour et la question suivante','查看反馈与下一个问题'))}`:''}
      ${current.kind==='followup_draft'&&current.state==='ready'?`<form data-mail-form>${field('to',t('Adresse exacte du destinataire','收件人准确邮箱'),'email')}${field('subject',t('Objet','主题'),'text',r.subject||'')}<label>${e(t('Message','邮件正文'))}<textarea name="body" rows="6">${e(r.body||'')}</textarea></label>${select('message_id',t('Répondre à un message déjà lié (facultatif)','回复已关联的招聘邮件（可选）'),[['',t('Nouveau message','新邮件')]])}<button class="ghost compact">${e(t('Vérifier le brouillon exact','预览这封邮件'))}</button></form><div data-mail-preview></div>`:''}
      <details><summary>${e(t('Résultat complet et sources','完整结果与依据'))}</summary>${renderValue(r)}</details>`;
    if(current.kind==='followup_draft'&&current.state==='ready'){const r=await api('/jobs/'+current.job_id+'/threads');const select=$('[data-mail-form] [name=message_id]');select.innerHTML+= (r.items||[]).map(x=>`<option value="${e(x.message_id)}" data-recipient="${e(x.recipient)}">${e(x.sender+' · '+x.subject)}</option>`).join('');}
    if(['queued','running'].includes(current.state))timer=setTimeout(()=>showTask(id).catch(err=>say(err.message)),2000);
  }
  async function upload(path,files,extras={}){if(!files.length)throw Error(t('Choisissez un fichier.','请先选择文件。'));const data=new FormData();for(const file of files)data.append(path==='/documents'||path==='/import-ledgers'?'files':'file',file);Object.entries(extras).forEach(([k,v])=>data.append(k,v));return requestJson('/api/capabilities'+path,{method:'POST',body:data});}
  host.addEventListener('change',event=>{if(event.target.matches('[data-mail-form] [name=message_id]')){const recipient=event.target.selectedOptions[0]?.dataset.recipient;if(recipient)$('[data-mail-form] [name=to]').value=recipient;}if(event.target.name==='kind')updateParams();if(event.target.matches('[data-ledger-files],[data-ledger-folder]')){ledgerFiles=[...event.target.files].filter(f=>/\.(csv|json|xlsx|md|tsv|db|sqlite|sqlite3)$/i.test(f.name));$('[data-tool=ledger-write]').disabled=true;}});
  host.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.target;const submit=form.querySelector('button[type=submit],button:not([type])');if(submit)submit.disabled=true;
    try{
      const d=Object.fromEntries(new FormData(form));
      if(form.matches('[data-task-form]')){const kind=d.kind;const params={};let job=['tailor_cv','research','interview','upskill','followup_draft','archive'].includes(kind)?Number(d.job)||null:null;
        if(kind==='tailor_cv'&&d.template)params.template_id=d.template;if(kind==='interview')params.stage=d.stage;
        if(kind==='portal_analyze')params.url=d.url;if(kind==='profile_expand')params.document_ids=[...host.querySelectorAll('[data-document-id]:checked')].map(x=>x.value);
        if(kind==='linkedin_scan'){params.queries=d.queries.split('\n').map(x=>x.trim()).filter(Boolean);params.location=d.location;params.only=d.only;}
        if(kind==='pdf_check'){params.document_id=$('[data-document-id]:checked')?.value;params.max_pages=2;}
        if(kind==='rank')params.job_ids=[...host.querySelectorAll('[data-rank-job]:checked')].map(x=>Number(x.value));
        await start(kind,params,job,d.backend);
      }else if(form.matches('[data-model-form]')){await api('/models/'+form.dataset.modelForm,d,'PUT');await load();}
      else if(form.matches('[data-source-form]')){d.enabled=form.elements.enabled.checked;await api('/sources/'+form.dataset.sourceForm,d,'PUT');await load();}
      else if(form.matches('[data-choice-form]')){await api('/model-choice',d,'PUT');await load();}
      else if(form.matches('[data-behavior-form]')){await api('/behavioral',d,'PUT');await load();}
      else if(form.matches('[data-notion-form]')){await api('/notion',d,'PUT');await load();}
      else if(form.matches('[data-template-form]')){await upload('/templates',[form.elements.file.files[0]].filter(Boolean),{label:d.label});await load();}
      else if(form.matches('[data-lint-form]')){$('[data-lint-result]').innerHTML=renderValue(await api('/lint',{text:d.text,rules:{bannedPhrases:d.banned.split(/\n|,/).filter(Boolean),forbiddenClaims:d.claims.split(/\n|,/).filter(Boolean)}}));}
      else if(form.matches('[data-salary-form]')){const result=await api('/salary/'+encodeURIComponent(d.dataset)+'?'+new URLSearchParams({company:d.company,role:d.role,city:d.city}));$('[data-salary-result]').innerHTML=renderValue(result)+(result.groups||[]).map(g=>g.quantiles?`<figure><figcaption>${e(g.currency+' · '+g.period+' · '+g.basis)} · n=${g.count}</figcaption>${Object.entries(g.quantiles).map(([p,v])=>`<div>P${e(p)} <meter min="0" max="${Number(g.quantiles['90'])||1}" value="${Number(v)}"></meter> ${e(v)}</div>`).join('')}</figure>`:'').join('');}
      else if(form.matches('[data-mail-form]')){const row=await api('/mail-preview',{task_id:current.id,...d});mailToken=row.token;$('[data-mail-preview]').innerHTML=`<p>${e(row.from)} → ${e(row.to)}</p><h4>${e(row.subject)}</h4><p style="white-space:pre-wrap">${e(row.body)}</p>${button('mail-draft',t('Créer ce brouillon dans Gmail','将这封草稿写入 Gmail'))}<label class="check"><input data-mail-ack type="checkbox">${e(t('J’ai vérifié le destinataire et le texte ; envoyer ce message.','我已核对收件人与正文，发送这封邮件。'))}</label>${button('mail-send',t('Envoyer ce brouillon exact','发送已核对的这封邮件'),'disabled')}`;}
      else if(form.matches('[data-docx-form]')){const changes={};form.querySelectorAll('[data-paragraph]').forEach(x=>{if(x.value!==x.defaultValue)changes[x.dataset.paragraph]=x.value;});const result=await api('/templates/'+form.dataset.docxForm+'/build-docx',{changes});$('[data-docx-editor]').innerHTML+=`<a href="/api/capabilities/download?path=${encodeURIComponent(result.artifact)}" download>${e(t('Télécharger le DOCX','下载新 DOCX'))}</a>`;}
      say(t('Terminé. Consultez le résultat ci-dessus.','操作完成，请查看对应结果。'));
    }catch(err){say(err.message);}finally{if(submit?.isConnected)submit.disabled=false;}
  });
  host.addEventListener('click',async event=>{
    const b=event.target.closest('[data-tool]');if(!b)return;b.disabled=true;
    try{const action=b.dataset.tool,id=b.dataset.id;
      if(action==='load')await load();
      if(action==='search-settings'){await showView('profile');document.getElementById('jobSourcesShortcut').click();}
      if(action==='task-open')await showTask(Number(id));if(action==='task-cancel'){await api('/tasks/'+id+'/cancel',{});await load();}
      if(action==='adopt-cv'){await api('/tasks/'+current.id+'/adopt-cv',{});await showTask(current.id);}
      if(action==='accept-result'){const suffix={profile_expand:'accept-facts',rank:'accept-rank',search_plan:'accept-plan',calibration:'accept-plan'}[current.kind];const indexes=[...host.querySelectorAll('[data-result-index]:checked')].map(x=>Number(x.value));if(!indexes.length)throw Error(t('Cochez les éléments à conserver.','请勾选要采用的结果。'));await api('/tasks/'+current.id+'/'+suffix,{indexes});if(window.loadPipeline)await loadPipeline();}
      if(action==='mock')await start('mock_turn',{parent_task:current.id,answer:$('[data-mock-answer]').value});
      if(action==='linkedin-login'){await api('/linkedin/login',{});say(t('Connectez-vous dans Chrome ; cette page ne sera pas actualisée.','请在弹出的专用 Chrome 中登录，该页面不会被刷新。'));}
      if(action==='linkedin-triage')await start('linkedin_triage',{parent_task:current.id});
      if(action==='accept-discovery'){await api('/tasks/'+current.id+'/accept-discovery',{indexes:[...host.querySelectorAll('[data-discovery-index]:checked')].map(x=>Number(x.value))});await load();}
      if(action==='documents'){const r=await upload('/documents',[...$('[data-document-files]').files]);await load();say(t('Documents importés : ','已导入材料：')+r.items.length);}
      if(action==='template-test')await start('template_test',{template_id:id});
      if(action==='docx'){const r=await api('/templates/'+id+'/paragraphs');$('[data-docx-editor]').innerHTML=`<form data-docx-form="${e(id)}">${r.paragraphs.map(p=>`<label>#${p.index}<textarea data-paragraph="${p.index}" rows="2">${e(p.text)}</textarea></label>`).join('')}<button class="ghost compact">${e(t('Créer une copie DOCX','生成新的 DOCX 副本'))}</button></form>`;}
      if(action==='model-check')await start('model_check',{},null,id);
      if(action==='source-check')await start('source_check',{source:id,query:'stage ingénieur',location:'France'});
      if(action==='notion-check')await start('notion_check');
      if(action==='notion-sync'){if(!$('[data-notion-ack]').checked)throw Error(t('Confirmez la destination.','请先核对并勾选写入目标。'));await start('notion_sync',{target_id:state.notion.target_id,acknowledged:true});}
      if(action==='gmail-config'){await api('/gmail-compose',{enabled:$('[data-gmail-compose]').checked},'PUT');say(t('Reconnectez Gmail pour accorder la rédaction.','若启用发信，请重新连接 Gmail 授权。'));}
      if(action==='gmail-connect'){const r=await requestJson('/api/gmail/connect',{method:'POST'});$('[data-gmail-auth]').innerHTML=`<a href="${e(r.url||r.authorization_url)}" target="_blank" rel="noopener">${e(t('Ouvrir la connexion Google','打开 Google 授权页面'))}</a>`;}
      if(action==='portal-register'){await api('/portals',{config:current.result.proposal});await load();}
      if(action==='portal-probe'){const r=await api('/portals/'+id+'/probe',{query:'stage'});await load();say(t('Offres trouvées : ','测试找到岗位：')+r.count);}
      if(action==='portal-enable'){await api('/portals/'+id,{enabled:b.dataset.enabled==='true'},'PUT');await load();}
      if(action==='salary-upload'){await upload('/salary',[...$('[data-salary-file]').files]);await load();}
      if(action==='ledger-preview'||action==='ledger-write'){const r=await upload('/import-ledgers',ledgerFiles,{write:String(action==='ledger-write')});$('[data-ledger-result]').innerHTML=renderValue(r);$('[data-tool=ledger-write]').disabled=action!=='ledger-preview'||!r.rows?.some(x=>!x.duplicate&&!x.errors.length);}
      if(action==='reset-preview'){resetState=await api('/reset-preview?scope='+$('[name=reset-scope]').value);$('[data-reset-result]').innerHTML=renderValue(resetState);$('[data-tool=reset]').disabled=false;}
      if(action==='reset'){if(!resetState||$('[name=reset-confirm]').value!=='RESET')throw Error(t('Relisez l’aperçu et saisissez RESET.','请核对影响范围并输入 RESET。'));const r=await api('/reset',{scope:resetState.scope,token:resetState.token,confirmation:'RESET'});$('[data-reset-result]').innerHTML=`<a href="/api/capabilities/download?path=${encodeURIComponent(r.backup)}" download>${e(t('Télécharger la sauvegarde','下载重置前备份'))}</a>`;resetState=null;await load();}
      if(action==='mail-draft'){await api('/mail-draft',{token:mailToken,acknowledged:true});$('[data-tool=mail-send]').disabled=false;say(t('Brouillon créé ; il n’a pas été envoyé.','已创建 Gmail 草稿，尚未发送。'));}
      if(action==='mail-send'){if(!$('[data-mail-ack]').checked)throw Error(t('Vérifiez puis confirmez le message.','请核对并勾选发送确认。'));const r=await api('/mail-send',{token:mailToken,acknowledged:true});say(t('Gmail confirme l’envoi : ','Gmail 已确认发送：')+r.gmail_message_id);mailToken=null;b.hidden=true;}
    }catch(err){say(err.message);}finally{if(b.isConnected&&b.dataset.tool!=='ledger-write')b.disabled=b.dataset.tool==='mail-send'&&!mailToken;}
  });
  document.addEventListener('localechange',()=>{clearTimeout(timer);shell();load().catch(err=>say(err.message));});
  shell();return {open:async id=>{chooseCategory(id);await load().catch(err=>say(err.message));},load:()=>load().catch(err=>say(err.message))};
})();
