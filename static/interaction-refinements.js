/* Small control release, using the reference's 600/30/1 spring parameters.
   The 220ms feedback window is an authored duration, not a settling-time claim. */
(()=>{
  const active=new Set();
  const controls=new WeakMap();
  let press=null;
  const stiffness=600,damping=30,mass=1;
  const omega=Math.sqrt(stiffness/mass),decay=damping/(2*mass);
  const frequency=Math.sqrt(omega*omega-decay*decay);
  const frames=Array.from({length:29},(_,index)=>{
    const t=index/28*.22;
    const displacement=-.015*Math.exp(-decay*t)*(Math.cos(frequency*t)+decay/frequency*Math.sin(frequency*t));
    return {scale:String(index===28?1:1+displacement),offset:index/28};
  });
  function release(button){
    if(!button||button.disabled||!button.isConnected||document.hidden||document.documentElement.dataset.angelinaMode==='quiet'||typeof button.animate!=='function')return;
    controls.get(button)?.cancel();
    const animation=button.animate(frames,{duration:220,easing:'linear'});
    controls.set(button,animation);active.add(animation);
    animation.onfinish=animation.oncancel=()=>active.delete(animation);
  }
  document.addEventListener('pointerdown',event=>{press=event.button===0?{id:event.pointerId,x:event.clientX,y:event.clientY,button:event.target.closest('button')}:null;});
  document.addEventListener('pointercancel',()=>{press=null;});
  document.addEventListener('pointerup',event=>{
    const started=press;press=null;
    if(started&&started.id===event.pointerId&&started.button===event.target.closest('button')&&Math.hypot(event.clientX-started.x,event.clientY-started.y)<4)release(started.button);
  });
  document.addEventListener('keyup',event=>{if(event.key==='Enter'||event.key===' ')release(event.target.closest('button'));});
  const stopPress=()=>{if(document.hidden||document.documentElement.dataset.angelinaMode==='quiet')for(const animation of [...active])animation.cancel();};
  document.addEventListener('visibilitychange',stopPress);
  new MutationObserver(stopPress).observe(document.documentElement,{attributes:true,attributeFilter:['data-angelina-mode']});
})();

/* Native adaptation of open-claude-ui's segmented indicator and quiet reveals.
   Explicit navigation only: background data paints never replay entry motion. */
window.InteractionMotion=(()=>{
 const animations=new Set(),byElement=new WeakMap();
 let current=null,queued=false;
 const allowed=()=>!document.hidden&&document.documentElement.dataset.angelinaMode!=='quiet';
 function reveal(view){
  if(!view||!allowed()||typeof view.animate!=='function')return;
  byElement.get(view)?.cancel();
  const animation=view.animate([{opacity:.72,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],{duration:200,easing:'cubic-bezier(.16,1,.3,1)'});
  byElement.set(view,animation);animations.add(animation);animation.onfinish=animation.oncancel=()=>animations.delete(animation);
 }
 function enterView(view){
  if(!view||view===current)return;
  current=view;
  for(const animation of [...animations])animation.cancel();
  reveal(view);
  if(view.id!=='mainMenuView'&&allowed()){
   for(const [index,section] of [...view.children].filter(node=>node.getClientRects().length&&!node.matches('header')).slice(0,4).entries()){
    const animation=section.animate([{opacity:.55,translate:'0 10px'},{opacity:1,translate:'0 0'}],{duration:280,delay:index*35,easing:'cubic-bezier(.16,1,.3,1)'});
    animations.add(animation);animation.onfinish=animation.oncancel=()=>animations.delete(animation);
   }
  }
 }
 function selection(){
  queued=false;
  const nav=document.querySelector('.primary-nav'),button=nav?.querySelector('.navmain.active');
  if(!nav||!button||!nav.getClientRects().length||!button.getClientRects().length){if(nav)nav.dataset.motionSelected='false';return;}
  const rect=button.getBoundingClientRect(),parent=nav.getBoundingClientRect();
  for(const [name,value] of Object.entries({x:rect.left-parent.left+nav.scrollLeft,y:rect.top-parent.top+nav.scrollTop,w:rect.width,h:rect.height})){
   const result=value+'px';if(nav.style.getPropertyValue('--nav-'+name)!==result)nav.style.setProperty('--nav-'+name,result);
  }
  nav.dataset.motionSelected='true';
 }
 function schedule(){if(!queued){queued=true;requestAnimationFrame(selection);}}
 function stop(){if(!allowed())for(const animation of [...animations])animation.cancel();schedule();}
 const nav=document.querySelector('.primary-nav');
 if(nav){new ResizeObserver(schedule).observe(nav);new MutationObserver(schedule).observe(document.querySelector('aside'),{subtree:true,attributes:true,attributeFilter:['class','aria-current']});}
 new MutationObserver(stop).observe(document.documentElement,{attributes:true,attributeFilter:['data-angelina-mode']});
 document.addEventListener('visibilitychange',stop);document.addEventListener('localechange',schedule);schedule();
 return {enterView,reveal};
})();
