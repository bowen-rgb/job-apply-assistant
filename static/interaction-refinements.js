/* Small control release, using the reference's 600/30/1 spring parameters.
   The 220ms feedback window is an authored duration, not a settling-time claim. */
(()=>{
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
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
    if(!button||button.disabled||!button.isConnected||reduced.matches||typeof button.animate!=='function')return;
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
  reduced.addEventListener('change',()=>{if(reduced.matches)for(const animation of [...active])animation.cancel();});
})();
