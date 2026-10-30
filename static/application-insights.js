/* Native workflow controls, not a new UI shell.
 * Primary: inspect real replies. Secondary: due follow-ups and per-job dossier.
 * Existing settings-card, queue-actions, small and tag tokens carry the hierarchy.
 * Import, export and rubric editing remain optional details; no new palette/framework.
 */
window.ApplicationInsights = (() => {
  const root = document.getElementById('applicationInsights');
  const t = (fr, zh) => Locale.language === 'zh' ? zh : fr;
  let state = null, jobs = [], importedFile = null, currentJob = null;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api = (path, body, method = 'POST') => requestJson('/api/insights'+path,
    body === undefined ? {} : {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const signals = () => ({ack:t('Réception confirmée','已收到申请'), screening:t('Informations demandées','要求补充信息'),
    interview:t('Entretien / évaluation','面试／测评'), offer:t('Proposition reçue','收到录用意向'),
    rejected:t('Candidature refusée','申请被拒'), conflict:t('Signaux contradictoires','信息互相矛盾')});
  const reasons = () => ({ambiguous_application:t('Plusieurs candidatures possibles : vérifiez manuellement.','可能对应多份申请，请人工核对。'),
    unconfirmed_submission:t('Confirmez d’abord l’envoi réel dans le suivi.','请先在申请进度中确认真实投递。'),
    unmatched_application:t('Aucune candidature identifiée avec certitude.','无法确定对应哪份申请。'),
    conflicting_signal:t('Le résultat contredit le suivi actuel : vérifiez manuellement.','与当前进度冲突，请人工核对。')});

  function message(text) {root.querySelector('[data-insight-status]').textContent = text;}
  function shell() {
    root.innerHTML = `<h2>${escape(t('Retours et prochaines actions','招聘反馈与下一步'))}</h2>
      <p>${escape(t('Lisez les retours des recruteurs, confirmez les changements et retrouvez les candidatures à relancer.','查看招聘方的真实反馈，确认进度变化，并找到需要跟进的申请。'))}</p>
      <div class="queue-actions"><button type="button" class="secondary compact" data-insight="mail">${escape(t('Lire les retours Gmail','读取 Gmail 招聘反馈'))}</button>
      <button type="button" class="ghost compact" data-insight="refresh">${escape(t('Actualiser le suivi','更新跟踪信息'))}</button></div>
      <p class="small">${escape(t('Gmail reste facultatif et en lecture seule. Aucun statut ne change avant votre confirmation. Aucun message n’est envoyé.','Gmail 可选，仅用于读取。确认前不会改变投递状态，也不会发送邮件。'))}</p>
      <p data-insight-status role="status" aria-live="polite"></p><div data-mail-proposals></div><div data-followups></div>
      <details><summary>${escape(t('Préparer un entretien / vérifier le CV','准备面试／检查简历'))}</summary>
      <label>${escape(t('Candidature','选择申请'))}<select data-dossier-job></select></label>
      <button type="button" class="ghost compact" data-insight="dossier">${escape(t('Ouvrir le dossier','查看准备资料'))}</button><div data-dossier></div></details>
      <details><summary>${escape(t('Importer ou exporter le suivi','导入／导出申请记录'))}</summary>
      <p class="small">${escape(t('Aperçu avant import. Les lignes existantes ne sont jamais remplacées. Une date d’envoi est obligatoire pour importer un résultat.','先预览再导入，不覆盖已有记录。导入已投递或招聘结果时必须有投递日期。'))}</p>
      <label>${escape(t('Fichier de suivi','申请记录文件'))}<input data-ledger-file type="file" accept=".csv,.tsv,.json,.md,.xlsx"></label>
      <div class="queue-actions"><button type="button" class="ghost compact" data-insight="preview">${escape(t('Prévisualiser','预览导入'))}</button>
      <button type="button" class="secondary compact" data-insight="import" disabled>${escape(t('Importer les nouvelles lignes','导入新增记录'))}</button></div><div data-import-preview></div>
      <div class="queue-actions">${['xlsx','csv','json'].map(format=>`<a class="ghost compact" href="/api/insights/export?format=${format}" download> ${escape(t('Exporter','导出'))} ${format.toUpperCase()}</a>`).join('')}</div></details>
      <details><summary>${escape(t('Règles de suivi et grille de score','跟进规则与评分权重'))}</summary>
      <label>${escape(t('Jours sans réponse avant rappel','多久未回复后提醒（天）'))}<input data-followup-days type="number" min="1" max="90" value="14"></label>
      <label>${escape(t('Nombre maximal de relances','最多跟进次数'))}<input data-followup-max type="number" min="0" max="10" value="1"></label>
      <details><summary>${escape(t('Grille de score personnalisée (facultative)','自定义评分维度（可选）'))}</summary>
      <p class="small">${escape(t('La revue ChatGPT note chaque dimension sur 5. Le calcul est local et ne remplace pas vos contraintes ni votre confirmation. [] conserve la revue actuelle.','ChatGPT 对每个维度评 0–5 分，系统按权重计算。不会覆盖硬性条件或人工确认。填 [] 保留原有复核方式。'))}</p>
      <label>${escape(t('Dimensions et poids JSON','维度和权重 JSON'))}<textarea data-rubric rows="6" spellcheck="false" placeholder='[{"id":"technical","label":"技术匹配","weight":60,"guide":"有实际项目证据"},{"id":"research","label":"科研相关","weight":40}]'>[]</textarea></label></details>
      <button type="button" class="ghost compact" data-insight="save">${escape(t('Enregistrer ces règles','保存这些规则'))}</button></details>`;
  }

  async function load() {
    if (!root.firstElementChild) shell();
    const [data, rows] = await Promise.all([api(''), requestJson('/api/pipeline')]);
    state = data; jobs = rows;
    root.querySelector('[data-followup-days]').value = state.config.follow_up.after_days;
    root.querySelector('[data-followup-max]').value = state.config.follow_up.max_followups;
    root.querySelector('[data-rubric]').value = JSON.stringify(state.config.dimensions, null, 2);
    const select = root.querySelector('[data-dossier-job]'), previous = select.value;
    select.innerHTML = `<option value="">${escape(t('Choisissez une candidature','请选择一份申请'))}</option>`+jobs.map(job=>`<option value="${job.id}">${escape(job.company)} · ${escape(job.title)}</option>`).join('');
    select.value = previous;
    renderOutcomes(); renderFollowups();
  }

  function renderOutcomes() {
    const rows = state.mail_proposals;
    root.querySelector('[data-mail-proposals]').innerHTML = `<h3>${escape(t('Retours à confirmer','待确认的招聘反馈'))} · ${rows.length}</h3>`+
      (rows.length ? rows.map(row=>`<article class="pipeline-card"><h4>${escape(row.company||t('Entreprise à vérifier','企业待核实'))} · ${escape(row.title||row.subject)}</h4>
      <p><strong>${escape(signals()[row.signal]||row.signal)}</strong> · ${escape(row.received_at.slice(0,10))}</p>
      <p class="small">${escape(row.sender)} · ${escape(row.subject)}</p><blockquote>${escape(row.evidence)}</blockquote>
      ${row.reason?`<p>${escape(reasons()[row.reason]||row.reason)}</p>`:`<label class="check"><input type="checkbox" data-mail-id="${escape(row.message_id)}">${escape(t('J’ai vérifié ce retour et la candidature associée.','我已核对反馈内容及其对应的申请。'))}</label>`}
      ${row.signal==='offer'?`<p>${escape(t('Une proposition n’est pas une acceptation : la décision vous appartient.','收到意向不等于已接受录用，由你决定是否接受。'))}</p>`:''}
      <button type="button" class="ghost compact" data-insight="dismiss" data-id="${escape(row.message_id)}">${escape(t('Ignorer ce résultat','忽略此条'))}</button></article>`).join('')+
      `<button type="button" class="secondary compact" data-insight="confirm">${escape(t('Confirmer les retours cochés','确认已勾选的反馈'))}</button>`:
      `<p class="small">${escape(t('Aucun retour en attente. Connectez Gmail dans Profils & comptes puis lancez la lecture, ou enregistrez le résultat manuellement dans le suivi.','暂无待确认反馈。可先在“个人档案与账号”连接 Gmail 后读取，也可在下方申请进度里手动记录结果。'))}</p>`);
  }

  function renderFollowups() {
    root.querySelector('[data-followups]').innerHTML = `<h3>${escape(t('À relancer','需要跟进'))} · ${state.followups.length}</h3>`+
      (state.followups.length ? state.followups.map(row=>`<article class="pipeline-card"><strong>${escape(row.company)} · ${escape(row.title)}</strong>
      <p>${escape(t('Dernier contact','最近联系'))} ${escape(row.last_activity)} · ${row.silent_days} ${escape(t('jours sans réponse','天未回复'))}</p>
      <p class="small">${escape(row.channel==='email'?t('Reprenez le fil du recruteur si vous avez son adresse.','如果有招聘人邮箱，可在原邮件会话中跟进。'):t('Vérifiez le portail ou le contact indiqué. Une absence de réponse n’est pas un refus.','请查看招聘门户或联系招聘方。未回复不代表被拒。'))}</p>
      <button type="button" class="ghost compact" data-insight="followup" data-id="${row.job_id}">${escape(t('J’ai envoyé une relance','我已发送跟进'))}</button></article>`).join(''):
      `<p class="small">${escape(t('Aucune relance due. Le rappel démarre après un envoi réellement enregistré.','暂无到期跟进。只有已记录真实投递的申请才开始计算提醒。'))}</p>`);
  }

  async function dossier() {
    currentJob = Number(root.querySelector('[data-dossier-job]').value);
    if (!currentJob) throw Error(t('Choisissez une candidature.','请先选择一份申请。'));
    const data = await api(`/jobs/${currentJob}/dossier`);
    const pack = data.interview, target = root.querySelector('[data-dossier]');
    target.innerHTML = `<h3>${escape(data.job.company)} · ${escape(data.job.title)}</h3>
      <p>${escape(t('CV actuellement routé','当前系统选择的简历'))}: ${escape(data.resume?.label||t('Aucun CV','尚未选择简历'))}</p>
      <details><summary>${escape(t('Comparer mes CV et leurs preuves','比较我的简历及匹配证据'))}</summary>${data.ranked_resumes.map(row=>`<p><strong>${escape(row.label)}</strong> · ${row.score}</p><ul>${row.evidence.map(line=>`<li>${escape(line)}</li>`).join('')}</ul>`).join('')}</details>
      <label>${escape(t('Mots-clés réels de l’offre (séparés par des virgules)','岗位原文关键词（用逗号分隔）'))}<input data-coverage-terms placeholder="Python, CATIA, simulation"></label>
      <button type="button" class="ghost compact" data-insight="coverage">${escape(t('Vérifier leur présence dans le CV','检查简历关键词覆盖'))}</button><p data-coverage-result></p>
      <h4>${escape(t('Préparer mes réponses avec des faits','用真实经历准备回答'))}</h4><ul>${pack.questions.map(q=>`<li>${escape(q)}</li>`).join('')}</ul>
      <h4>${escape(t('Mes preuves à relire','可用于准备的真实项目证据'))}</h4><ul>${pack.candidate_evidence.map(line=>`<li>${escape(line)}</li>`).join('')}</ul>
      <h4>${escape(t('Questions à poser au recruteur','可以问招聘方的问题'))}</h4><ul>${pack.ask_employer.map(q=>`<li>${escape(q)}</li>`).join('')}</ul>
      <p class="small">${escape(t('Ces pistes ne sont pas des réponses inventées. Préparez votre propre exemple et ses limites.','这些是准备提示，不是虚构的面试回答。请用自己的经历和实际能力边界作答。'))}</p>`;
  }

  async function upload(write) {
    const file = root.querySelector('[data-ledger-file]').files[0];
    if (!file) throw Error(t('Choisissez un fichier.','请先选择文件。'));
    if (write && file !== importedFile) throw Error(t('Prévisualisez ce fichier avant de l’importer.','请先预览当前文件再导入。'));
    const body = new FormData(); body.append('file',file); body.append('write',String(write));
    const result = await requestJson('/api/insights/import',{method:'POST',body});
    if (write) {
      message(`${t('Lignes ajoutées','新增记录')}: ${result.added} · ${t('Doublons','重复记录')}: ${result.duplicates} · ${t('Invalides','无效记录')}: ${result.invalid}`);
      importedFile = null; root.querySelector('[data-insight="import"]').disabled = true; await loadPipeline(); await load();
    } else {
      importedFile = file;
      root.querySelector('[data-insight="import"]').disabled = !result.rows.some(row=>!row.errors.length&&!row.duplicate);
      root.querySelector('[data-import-preview]').innerHTML = `<p>${result.rows.length} ${escape(t('lignes lues','条记录'))}</p><ul>`+
        result.rows.slice(0,50).map(row=>`<li>${escape(row.company)} · ${escape(row.title)} · ${escape(row.stage)} · ${escape(row.duplicate?t('Doublon ignoré','重复，将跳过'):row.errors.length?row.errors.join(', '):t('Nouvelle ligne','新记录'))}</li>`).join('')+'</ul>';
    }
  }

  root.addEventListener('change',event=>{if(event.target.matches('[data-ledger-file]')){importedFile=null;root.querySelector('[data-insight="import"]').disabled=true;}});
  root.addEventListener('click',async event=>{
    const button=event.target.closest('[data-insight]'); if(!button)return;
    button.disabled=true;
    try {
      const action=button.dataset.insight;
      if(action==='refresh')await load();
      if(action==='mail'){
        message(t('Lecture des messages récents… Les résultats seront à confirmer.','正在读取近期邮件……识别结果会先让你确认。'));
        const result=await api('/gmail-sync',{days:30});await load();
        message(`${t('Messages lus','已读邮件')}: ${result.read||0} · ${t('Nouveaux résultats','新增反馈')}: ${result.proposed||0}${result.truncated?' · '+t('Limite atteinte : relancez pour poursuivre.','达到本次读取上限，可再次读取。'):''}`);
      }
      if(action==='confirm'||action==='dismiss'){
        const ids=action==='dismiss'?[button.dataset.id]:[...root.querySelectorAll('[data-mail-id]:checked')].map(input=>input.dataset.mailId);
        if(!ids.length)throw Error(t('Vérifiez et cochez les retours à confirmer.','请先核对并勾选要确认的反馈。'));
        await api('/mail-confirm',{message_ids:ids,accept:action==='confirm'});await loadPipeline();await load();
        message(t('Le suivi a été mis à jour.','申请进度已更新。'));
      }
      if(action==='followup'){
        const note=prompt(t('Qu’avez-vous envoyé, à qui et quand ? Annuler si rien n’a été envoyé.','你向谁发送了什么跟进？尚未发送请取消。'));
        if(note?.trim()){await api(`/jobs/${Number(button.dataset.id)}/activities`,{kind:'followup_sent',note:note.trim()});await load();}
      }
      if(action==='dossier')await dossier();
      if(action==='coverage'){
        const keywords=root.querySelector('[data-coverage-terms]').value.split(/[,，]/).map(s=>s.trim()).filter(Boolean);
        const result=await api(`/jobs/${currentJob}/coverage`,{keywords});
        root.querySelector('[data-coverage-result]').textContent=`${t('Présents','已覆盖')}: ${result.coverage_pct}% · ${t('Absents','未出现')}: ${result.missing.join(', ')||'—'} · ${t('Hors annonce','不在岗位原文中')}: ${result.ignored.join(', ')||'—'} · ${t('Ne pas inventer une compétence pour combler un mot-clé.','不要为了补关键词而编造技能。')}`;
      }
      if(action==='preview'||action==='import')await upload(action==='import');
      if(action==='save'){
        await api('/config',{follow_up:{after_days:Number(root.querySelector('[data-followup-days]').value),max_followups:Number(root.querySelector('[data-followup-max]').value)},dimensions:JSON.parse(root.querySelector('[data-rubric]').value)},'PUT');
        message(t('Règles enregistrées pour ce profil.','规则已保存到当前档案。'));
      }
    } catch(error){message(error.message);}
    finally{if(button.isConnected)button.disabled=false;}
  });
  document.addEventListener('localechange',()=>{shell();if(state)load().catch(error=>message(error.message));});
  return {load:()=>load().catch(error=>{if(!root.firstElementChild)shell();message(error.message);})};
})();
