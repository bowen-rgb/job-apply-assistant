/* The platform owns Chrome and the workers. This panel never starts a queue. */
window.ChromeControl=(()=>{
 let root,busy=false,state=null,unavailable=false;
 const tr=text=>Locale.t(text);
 function paint(){
  if(!root)return;
  root.querySelector('[data-chrome-status]').textContent=tr(unavailable?'Redémarrez la plateforme pour charger le contrôle Chrome.':state?.message||'Vérification de Chrome…');
  root.querySelector('[data-chrome-status]').dataset.connection=state?.ready?'ready':'blocked';
  root.querySelector('#browserOpenChrome').disabled=busy||unavailable||state?.ready===true;
  root.querySelector('#browserCheckChrome').disabled=busy;
 }
 async function request(url,options){const response=await fetch(url,options);let data;try{data=await response.json();}catch{throw Error('Connexion à la plateforme impossible.');}if(response.status===404){unavailable=true;throw Error('Redémarrez la plateforme pour charger le contrôle Chrome.');}if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Connexion à la plateforme impossible.');unavailable=false;return data;}
 async function refresh(known){try{state=known||await request('/api/browser');}catch(error){state={ready:false,message:error.message};}paint();}
 async function open(){if(busy)return;busy=true;paint();try{state=await request('/api/browser/start',{method:'POST'});}catch(error){state={ready:false,message:error.message};}finally{busy=false;paint();}}
 function init(){root=document.getElementById('managedBrowserPanel');if(!root)return;root.querySelector('#browserOpenChrome').onclick=open;root.querySelector('#browserCheckChrome').onclick=()=>refresh();document.addEventListener('localechange',paint);refresh();}
 return {init,refresh};
})();
