window.PendingTasks=(()=>{
  const texts={
    zh:['待处理','关闭','当前档案','待处理','已处理','岗位申请','联系实验室','个人材料','打开链接','标为已处理','移回待处理','这份列表属于当前档案。请先核实是否已经投递或联系过；标为已处理不会自动记录投递成功，也不会发送申请。','这里还没有待办。','来源'],
    fr:['À traiter','Fermer','Profil actuel','À traiter','Traité','Candidature','Contacter un laboratoire','Documents personnels','Ouvrir le lien','Marquer traité','Remettre à traiter','Cette liste appartient au profil actuel. Vérifiez si vous avez déjà postulé ou contacté le laboratoire. Traiter une tâche ne signifie pas qu’une candidature a été envoyée et n’envoie rien.','Aucune tâche ici.','Source'],
    en:['To do','Close','Current profile','Pending','Done','Job application','Contact a laboratory','Personal documents','Open link','Mark done','Move back to pending','This list belongs to the current profile. Check whether you have already applied or contacted the team. Completing a task does not record or send an application.','No tasks here.','Source'],
    de:['Zu erledigen','Schließen','Aktuelles Profil','Offen','Erledigt','Bewerbung','Labor kontaktieren','Persönliche Unterlagen','Link öffnen','Als erledigt markieren','Wieder öffnen','Diese Liste gehört zum aktuellen Profil. Frühere Bewerbungen und Kontakte zuerst prüfen. Eine erledigte Aufgabe erfasst oder sendet keine Bewerbung.','Keine Aufgaben vorhanden.','Quelle'],
    es:['Pendientes','Cerrar','Perfil actual','Pendiente','Resuelto','Solicitud de empleo','Contactar laboratorio','Documentos personales','Abrir enlace','Marcar resuelto','Volver a pendiente','La lista pertenece al perfil actual. Comprueba si ya solicitaste o contactaste al equipo. Resolver una tarea no registra ni envía una solicitud.','No hay tareas aquí.','Fuente'],
    pt:['Pendências','Fechar','Perfil atual','Pendente','Resolvido','Candidatura','Contatar laboratório','Documentos pessoais','Abrir link','Marcar resolvido','Voltar a pendente','Esta lista pertence ao perfil atual. Confira se já se candidatou ou contatou a equipe. Resolver uma tarefa não registra nem envia uma candidatura.','Nenhuma tarefa aqui.','Fonte']
  };
  const queueWords={zh:['加入队列','查看队列','将待处理岗位全部加入队列','已加入队列，尚未投递。','入队仅安排申请准备，不会立即发送。联系实验室和个人材料不进入投递队列。'],fr:['Ajouter à la file','Voir la file','Ajouter toutes les offres en attente','Ajouté à la file, candidature non envoyée.','Ajouter à la file prépare le travail sans envoyer immédiatement. Les contacts et documents restent des tâches.'],en:['Add to queue','View queue','Queue all pending jobs','Added to queue; not submitted.','Queueing schedules preparation without sending immediately. Contacts and documents stay as to-dos.'],de:['Zur Warteschlange','Warteschlange anzeigen','Alle offenen Stellen einreihen','Eingereiht, Bewerbung noch nicht gesendet.','Einreihen plant die Vorbereitung, ohne sofort zu senden. Kontakte und Dokumente bleiben Aufgaben.'],es:['Añadir a la cola','Ver cola','Añadir todas las ofertas pendientes','Añadido a la cola; todavía no enviado.','La cola organiza la preparación sin enviar inmediatamente. Contactos y documentos siguen como tareas.'],pt:['Adicionar à fila','Ver fila','Adicionar todas as vagas pendentes','Adicionado à fila; ainda não enviado.','A fila organiza a preparação sem enviar imediatamente. Contatos e documentos permanecem como tarefas.']};
  const qt=i=>(queueWords[Locale.language]||queueWords.en)[i];
  const t=i=>(texts[Locale.language]||texts.en)[i];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const api=async(url,options={})=>{const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw Error(data.detail||Locale.t('Erreur'));return data;};
  let dialog,button,selected='pending';
  async function render(){
    const [data,profiles]=await Promise.all([api('/api/pending-tasks'),api('/api/candidates')]);
    const profile=profiles.items?.find(row=>row.id===Accounts.owner);
    const items=data.items||[];
    dialog.innerHTML=`<header><h2>${esc(t(0))} · ${esc(profile?.name||Accounts.owner)}</h2><button id="pendingClose" type="button">${esc(t(1))}</button></header><p>${esc(t(11))}</p><p class="small">${esc(qt(4))}</p><p id="pendingNotice" role="status" aria-live="polite"></p><div class="pending-filters">${['pending','done'].map((status,index)=>`<button type="button" data-task-filter="${status}" aria-pressed="${selected===status}">${esc(t(index+3))} (${items.filter(item=>item.status===status).length})</button>`).join('')}</div>${selected==='pending'&&items.some(item=>item.kind==='vacancy'&&item.status==='pending'&&!item.queue_status)?`<button id="pendingQueueAll" type="button" class="secondary">${esc(qt(2))}</button>`:''}<div class="pending-items">${items.filter(item=>item.status===selected).map(item=>`<article class="pending-task"><span class="tag">${esc(t({vacancy:5,contact:6,material:7}[item.kind]||5))}</span><h3>${esc(item.title)}</h3><p class="pending-note">${esc(item.note)}</p><p class="small">${esc(t(13))}: ${esc(item.source)}</p><div class="pending-actions">${item.url?`<a class="button" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(t(8))} ↗</a>`:''}${item.kind==='vacancy'&&item.status==='pending'?`<button type="button" class="secondary compact" ${item.queue_status?'data-view-task-queue':`data-queue-task="${item.id}"`}>${esc(qt(item.queue_status?1:0))}</button>`:''}<button type="button" data-task-id="${item.id}">${esc(t(selected==='pending'?9:10))}</button></div></article>`).join('')||`<p>${esc(t(12))}</p>`}</div>`;
    document.getElementById('pendingClose').onclick=()=>dialog.close();
    const goQueue=()=>{dialog.close();showView('pipeline');};
    dialog.querySelectorAll('[data-view-task-queue]').forEach(control=>control.onclick=goQueue);
    const queueRows=async rows=>{
      let error='';let added=0;
      for(const item of rows){try{await api(`/api/pending-tasks/${item.id}/queue`,{method:'POST'});added++;}catch(failure){error+=`${item.title}: ${failure.message}\n`;}}
      await render();document.getElementById('pendingNotice').textContent=`${added} · ${qt(3)}${error?'\n'+error:''}`;
      await load();
    };
    dialog.querySelectorAll('[data-queue-task]').forEach(control=>control.onclick=async()=>{
      control.disabled=true;try{await queueRows(items.filter(item=>item.id===control.dataset.queueTask));}catch(error){document.getElementById('pendingNotice').textContent=error.message;control.disabled=false;}
    });
    const all=document.getElementById('pendingQueueAll');
    if(all)all.onclick=async()=>{all.disabled=true;try{await queueRows(items.filter(item=>item.kind==='vacancy'&&item.status==='pending'&&!item.queue_status));}catch(error){document.getElementById('pendingNotice').textContent=error.message;all.disabled=false;}};

    dialog.querySelectorAll('[data-task-filter]').forEach(filter=>filter.onclick=async()=>{
      const previous=selected;selected=filter.dataset.taskFilter;
      try{await render();}catch(error){selected=previous;document.getElementById('pendingNotice').textContent=error.message;}
    });
    dialog.querySelectorAll('[data-task-id]').forEach(control=>control.onclick=async()=>{
      control.disabled=true;
      try{await api(`/api/pending-tasks/${control.dataset.taskId}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({status:selected==='pending'?'done':'pending'})});await render();}
      catch(error){document.getElementById('pendingNotice').textContent=error.message;control.disabled=false;}
    });
  }
  async function init(){
    button=document.createElement('button');button.className='navmain';button.id='pendingTasksNav';button.type='button';button.textContent=t(0);
    document.querySelector('.primary-nav').append(button);
    dialog=document.createElement('dialog');dialog.id='pendingTasksDialog';document.body.append(dialog);
    button.onclick=async()=>{dialog.innerHTML=`<p role="status">${esc(Locale.t('Chargement…'))}</p>`;dialog.showModal();try{await render();}catch(error){dialog.innerHTML=`<p role="alert">${esc(error.message)}</p><button type="button">${esc(t(1))}</button>`;dialog.querySelector('button').onclick=()=>dialog.close();}};
    document.addEventListener('localechange',()=>{button.textContent=t(0);if(dialog.open)render().catch(error=>document.getElementById('pendingNotice').textContent=error.message);});
  }
  return {init};
})();
