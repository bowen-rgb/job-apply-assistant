// SPDX-License-Identifier: GPL-3.0-or-later
// Local menu widgets; no candidate data or media is uploaded.
(()=>{
 const $=id=>document.getElementById(id);
 const root=document.createElement('section');root.className='jaa-center-widget';
 root.innerHTML='<nav class="jaa-widget-tabs"><button type="button" data-widget="music"></button><button type="button" data-widget="map"></button><label><input id="widgetRotate" type="checkbox"><span data-word="rotate"></span></label></nav><div id="musicWidget"><img class="jaa-widget-art" src="/static/artwork/angelina/ride.png" alt=""><strong id="widgetTrack"></strong><audio id="widgetAudio" controls preload="metadata"></audio><div class="jaa-player-actions"><button id="widgetPrevious" type="button" aria-label="Previous">‹</button><label class="jaa-file-label"><span data-word="chooseMusic"></span><input id="widgetMusicFiles" type="file" accept="audio/*" multiple></label><button id="widgetNext" type="button" aria-label="Next">›</button></div><p data-word="localMusic"></p><p id="widgetAudioStatus" role="status"></p></div><div id="mapWidget" hidden><div id="widgetMapCanvas"><span aria-hidden="true">⌖</span><p data-word="locationHint"></p></div><p id="widgetLocationStatus" role="status"></p><div class="jaa-map-actions"><button id="widgetLocate" type="button" data-word="locate"></button><button id="widgetClearLocation" type="button" data-word="clearLocation" hidden></button><a id="widgetGoogleMap" target="_blank" rel="noopener noreferrer" data-word="openMap" hidden></a></div></div>';
 document.querySelector('.ef-stage').append(root);
 const clock=document.createElement('section');clock.className='jaa-menu-clock';clock.innerHTML='<span data-word="clock"></span><time id="menuClock"></time><small id="menuCalendar"></small>';
 EF.scene.layer('top').append(clock);
 let words={},language='fr',active=false,current='music',tracks=[],index=0,lastSwitch=0;
 const audio=$('widgetAudio'),files=$('widgetMusicFiles');
 function show(name){current=name;lastSwitch=Date.now();$('musicWidget').hidden=name!=='music';$('mapWidget').hidden=name!=='map';for(const button of root.querySelectorAll('[data-widget]'))button.setAttribute('aria-pressed',String(button.dataset.widget===name));}
 for(const button of root.querySelectorAll('[data-widget]'))button.onclick=()=>show(button.dataset.widget);
 function selectTrack(next){if(!tracks.length)return;index=(next+tracks.length)%tracks.length;audio.pause();audio.src=tracks[index].url;$('widgetTrack').textContent=tracks[index].name;$('widgetAudioStatus').textContent='';}
 files.onchange=()=>{
  audio.pause();audio.removeAttribute('src');audio.load();for(const track of tracks)URL.revokeObjectURL(track.url);
  tracks=Array.from(files.files).filter(file=>file.type.startsWith('audio/')||/\.(mp3|ogg|wav|m4a|aac|flac|opus)$/i.test(file.name)).map(file=>({name:file.name,url:URL.createObjectURL(file)}));
  $('widgetPrevious').disabled=$('widgetNext').disabled=tracks.length<2;
  if(tracks.length)selectTrack(0);else $('widgetTrack').textContent=words.noTrack||'';
  files.value='';
 };
 function stepTrack(offset){const playing=!audio.paused;selectTrack(index+offset);if(playing)audio.play().catch(()=>{$('widgetAudioStatus').textContent=words.audioError||'';});}
 $('widgetPrevious').onclick=()=>stepTrack(-1);$('widgetNext').onclick=()=>stepTrack(1);
 audio.onerror=()=>$('widgetAudioStatus').textContent=words.audioError||'';
 audio.onended=()=>{if(tracks.length>1){selectTrack(index+1);audio.play().catch(()=>{$('widgetAudioStatus').textContent=words.audioError||'';});}};
 $('widgetLocate').onclick=()=>{$('widgetLocate').disabled=true;$('widgetLocationStatus').textContent=words.locating;document.dispatchEvent(new Event('jaa-widget:locate'));};
 function clearLocation(){$('widgetMapCanvas').replaceChildren();const hint=document.createElement('p');hint.dataset.word='locationHint';hint.textContent=words.locationHint;$('widgetMapCanvas').append(hint);$('widgetGoogleMap').removeAttribute('href');$('widgetGoogleMap').hidden=true;$('widgetClearLocation').hidden=true;$('widgetLocationStatus').textContent='';}
 $('widgetClearLocation').onclick=clearLocation;
 function location(data){
  $('widgetLocate').disabled=false;
  const lat=Number(data.latitude),lon=Number(data.longitude);
  if(data.error||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180){$('widgetLocationStatus').textContent=words.locationError;return;}
  $('widgetLocationStatus').textContent=lat.toFixed(3)+', '+lon.toFixed(3);
  const map=document.createElement('iframe');map.title=words.map;map.referrerPolicy='no-referrer';
  const bbox=[Math.max(-180,lon-.025),Math.max(-90,lat-.015),Math.min(180,lon+.025),Math.min(90,lat+.015)].join(',');
  map.src='https://www.openstreetmap.org/export/embed.html?'+new URLSearchParams({bbox,layer:'mapnik',marker:lat+','+lon});
  $('widgetMapCanvas').replaceChildren(map);$('widgetGoogleMap').href='https://www.google.com/maps/search/?'+new URLSearchParams({api:'1',query:lat+','+lon});$('widgetGoogleMap').hidden=false;$('widgetClearLocation').hidden=false;
 }
 function tick(){
  if(!active)return;
  const now=new Date();$('menuClock').textContent=new Intl.DateTimeFormat(language,{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(now);$('menuClock').dateTime=now.toISOString();
  $('menuCalendar').textContent=new Intl.DateTimeFormat(language,{month:'short',day:'numeric',weekday:'short'}).format(now);
  if($('widgetRotate').checked&&Date.now()-lastSwitch>30000)show(current==='music'?'map':'music');
 }
 function update(state){
  active=state.active;language=state.language||'fr';words=state.widget||{};
  for(const element of document.querySelectorAll('[data-word]'))element.textContent=words[element.dataset.word]||'';
  for(const button of root.querySelectorAll('[data-widget]'))button.textContent=words[button.dataset.widget]||button.dataset.widget;
  if(!tracks.length)$('widgetTrack').textContent=words.noTrack||'';
  tick();
 }
 window.addEventListener('pagehide',()=>{for(const track of tracks)URL.revokeObjectURL(track.url);});
 $('widgetPrevious').disabled=$('widgetNext').disabled=true;show('music');setInterval(tick,1000);
 EF.widgets={update,location};
})();
