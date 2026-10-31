// SPDX-License-Identifier: GPL-3.0-or-later
// Local menu widgets; no candidate data or media is uploaded.
(()=>{
 const $=id=>document.getElementById(id);
 const root=document.createElement('section');root.className='jaa-center-widget';
 root.innerHTML='<div id="musicWidget"><h2 data-word="music"></h2><img class="jaa-widget-art" src="/static/artwork/angelina/ride.png" alt=""><strong id="widgetTrack"></strong><audio id="widgetAudio" controls preload="metadata"></audio><div class="jaa-player-actions"><button id="widgetPrevious" type="button" aria-label="Previous">‹</button><label class="jaa-file-label"><span data-word="chooseMusic"></span><input id="widgetMusicFiles" type="file" accept="audio/*" multiple></label><button id="widgetNext" type="button" aria-label="Next">›</button></div><p data-word="localMusic"></p><p id="widgetAudioStatus" role="status"></p></div>';
 document.querySelector('.ef-stage').append(root);
 const clock=document.createElement('section');clock.className='jaa-menu-clock';clock.innerHTML='<span data-word="clock"></span><time id="menuClock"></time><small id="menuCalendar"></small>';
 EF.scene.layer('top').append(clock);
 let words={},language='fr',active=false,tracks=[],index=0;
 const audio=$('widgetAudio'),files=$('widgetMusicFiles');
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
 function tick(){
  if(!active)return;
  const now=new Date();$('menuClock').textContent=new Intl.DateTimeFormat(language,{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(now);$('menuClock').dateTime=now.toISOString();
  $('menuCalendar').textContent=new Intl.DateTimeFormat(language,{month:'short',day:'numeric',weekday:'short'}).format(now);
 }
 function update(state){
  active=state.active;language=state.language||'fr';words=state.widget||{};
  for(const element of document.querySelectorAll('[data-word]'))element.textContent=words[element.dataset.word]||'';
  if(!tracks.length)$('widgetTrack').textContent=words.noTrack||'';
  tick();
 }
 window.addEventListener('pagehide',()=>{for(const track of tracks)URL.revokeObjectURL(track.url);});
 $('widgetPrevious').disabled=$('widgetNext').disabled=true;setInterval(tick,1000);
 EF.widgets={update};
})();
