/* Shared headings, section navigation and responsive primary navigation. */
window.Surfaces=(()=>{
  const names={pfeView:'PFE / RESEARCH DISCOVERY',jobsView:'JOB DISCOVERY',profileView:'PERSONAL FILE',pipelineView:'APPLICATION QUEUE',guideView:'GET STARTED',accountsDialog:'PROFILES / ACCOUNTS',pendingTasksDialog:'PERSONAL TASKS'};
  function stamp(root){
    const header=root.querySelector(':scope > header');if(!header)return;
    header.classList.add('surface-heading');
    if(!header.querySelector('.surface-mark')){const mark=document.createElement('span');mark.className='surface-mark';mark.setAttribute('aria-hidden','true');mark.textContent=names[root.id];header.prepend(mark);}
    if(root.tagName==='DIALOG'){const title=header.querySelector('h2');if(title){title.id=root.id+'Title';root.setAttribute('aria-labelledby',title.id);}}
  }
  function rail(root,sections,id){
    let nav=root.querySelector(':scope > .surface-jumps');
    if(!nav){nav=document.createElement('nav');nav.className='surface-jumps';root.querySelector(':scope > header')?.after(nav);}
    const label=({zh:'页面分区',fr:'Sections de la page',en:'Page sections',de:'Seitenbereiche',es:'Secciones de la página',pt:'Secções da página'})[Locale.language];nav.setAttribute('aria-label',label);
    sections.forEach((section,index)=>{
      const title=section.querySelector('h2,h3');if(!title)return;
      if(!section.id)section.id=id+'Section'+index;
      title.tabIndex=-1;
      let button=nav.querySelector(`[data-section="${section.id}"]`);
      if(!button){button=document.createElement('button');button.type='button';button.dataset.section=section.id;button.onclick=()=>{section.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});title.focus({preventScroll:true});};nav.append(button);}
      if(button.textContent!==title.textContent)button.textContent=title.textContent;
    });
  }
  function decorate(){
    Object.keys(names).forEach(id=>{const root=document.getElementById(id);if(root)stamp(root);});
    const profile=document.getElementById('profileView');if(profile)rail(profile,[...profile.querySelectorAll('#profileForm > .settings-card')],'profile');
    const dialog=document.getElementById('accountsDialog');
    if(dialog?.querySelector(':scope > h3')){
      const headings=[...dialog.querySelectorAll(':scope > h3')];
      headings.forEach((heading,index)=>{const section=document.createElement('section');section.className='surface-account-section';section.id='accountSection'+index;heading.before(section);let node=heading;while(node&&!(node!==heading&&node.nodeType===1&&node.tagName==='H3')){const next=node.nextSibling;section.append(node);node=next;}});
    }
    if(dialog?.querySelector('.surface-account-section'))rail(dialog,[...dialog.querySelectorAll(':scope > .surface-account-section')],'account');
  }
  function init(){
    const aside=document.querySelector('aside'),primary=document.querySelector('.primary-nav');
    primary.id='primaryNavigation';
    const toggle=document.createElement('button');toggle.id='mobileNavToggle';toggle.type='button';
    toggle.setAttribute('aria-controls',primary.id);toggle.setAttribute('aria-expanded','false');
    toggle.onclick=()=>{const open=aside.classList.toggle('navigation-open');toggle.setAttribute('aria-expanded',String(open));};
    aside.addEventListener('keydown',event=>{if(event.key==='Escape'&&aside.classList.contains('navigation-open')){aside.classList.remove('navigation-open');toggle.setAttribute('aria-expanded','false');toggle.focus();}});
    aside.querySelector('.brand').after(toggle);
    const updateNavigation=()=>{toggle.textContent=Locale.t('Navigation principale')+' · '+(primary.querySelector('[aria-current="page"]')?.textContent||'');};
    primary.addEventListener('click',event=>{if(event.target.closest('button')&&matchMedia('(max-width:760px)').matches){aside.classList.remove('navigation-open');toggle.setAttribute('aria-expanded','false');toggle.focus();}});
    new MutationObserver(updateNavigation).observe(primary,{attributes:true,subtree:true,characterData:true,childList:true});
    updateNavigation();document.addEventListener('localechange',updateNavigation);
    // A fade indicates additional content; endpoints and keyboard focus stay clear.
    const updateEdges=()=>{
      const distance=aside.scrollHeight-aside.clientHeight;
      aside.classList.add('scroll-edges');
      aside.dataset.edgeTop=String(aside.scrollTop>2);
      aside.dataset.edgeBottom=String(distance-aside.scrollTop>2);
      aside.style.setProperty('--fade-top',aside.scrollTop>2?'24px':'0px');
      aside.style.setProperty('--fade-bottom',distance-aside.scrollTop>2?'24px':'0px');
    };
    aside.addEventListener('scroll',updateEdges,{passive:true});
    new ResizeObserver(updateEdges).observe(aside);
    new MutationObserver(updateEdges).observe(aside,{childList:true,subtree:true});updateEdges();
    // Separate track and selected thumb from SegmentedControl.tsx; retain every metric.
    const metrics=document.getElementById('jobMetrics');
    if(metrics){
      const updateSelection=()=>{
        const item=metrics.querySelector('.selected');
        metrics.dataset.selection=String(Boolean(item?.getClientRects().length));
        if(!item)return;
        const group=metrics.getBoundingClientRect(),box=item.getBoundingClientRect();
        for(const [key,value] of Object.entries({x:box.left-group.left-metrics.clientLeft,y:box.top-group.top-metrics.clientTop,width:box.width,height:box.height}))metrics.style.setProperty('--selection-'+key,value+'px');
      };
      new ResizeObserver(updateSelection).observe(metrics);
      new MutationObserver(updateSelection).observe(metrics,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
      document.addEventListener('localechange',updateSelection);updateSelection();
    }
    decorate();let scheduled=false;
    new MutationObserver(()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;decorate();});}).observe(document.querySelector('.shell'),{childList:true,subtree:true,characterData:true});
    ['accountsDialog','pendingTasksDialog'].forEach(id=>{const dialog=document.getElementById(id);if(dialog)new MutationObserver(decorate).observe(dialog,{childList:true,subtree:true,characterData:true});});
    document.addEventListener('localechange',decorate);
  }
  return {init};
})();
