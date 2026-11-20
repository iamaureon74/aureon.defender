'use strict';
(() => {
  const $ = s => document.querySelector(s), REPOS = ['https://github.com/iamaureon74/aureon.defender', 'https://github.com/shep95/aureon.defender'];
  const API = 'https://api.github.com/repos/iamaureon74/aureon.defender/releases?per_page=10';
  const ours = (url, part) => typeof url === 'string' && REPOS.some(r => url.startsWith(r + part));
  let releases = [], selected = 'auto', lastCheck = 0, pending = false;
  const safeStorage = { get: k => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k,v) => { try { localStorage.setItem(k,v); } catch {} } };
  const seenOnEntry=safeStorage.get('aureon-release-seen');
  function platform(n = navigator) {
    const ua = n.userAgent || '', p = n.userAgentData?.platform || n.platform || '';
    if (/android/i.test(ua + p)) return 'android';
    if (/iphone|ipad|ipod/i.test(ua) || (/mac/i.test(p) && n.maxTouchPoints > 1)) return 'ios';
    if (/win/i.test(p + ua)) return 'windows';
    if (/mac/i.test(p + ua)) return 'macos';
    if (/linux|cros/i.test(p + ua)) return 'linux';
    return 'other';
  }
  function validRelease(r) { return r && !r.draft && !r.prerelease && typeof r.tag_name === 'string' && Array.isArray(r.assets) && ours(r.html_url, '/releases/tag/'); }
  function assetFor(os) {
    const patterns = { windows:/^aureon-defender-windows-x64-setup-[\d.]+\.exe$/, android:/^aureon-defender-android-[\d.]+\.apk$/, macos:/^aureon-defender-portable-source-[\w.-]+\.zip$/, linux:/^aureon-defender-portable-source-[\w.-]+\.zip$/ };
    for (const r of releases) for (const a of r.assets) {
      if (patterns[os]?.test(a.name) && ours(a.browser_download_url, '/releases/download/')) return { ...a, release:r };
    }
    return null;
  }
  const names = { windows:'Windows', android:'Android', ios:'iPhone / iPad', macos:'macOS', linux:'Linux / Raspberry Pi', other:'Web edition' };
  function renderRecommendation() {
    const os = selected === 'auto' ? platform() : selected, a = assetFor(os), web = os === 'ios' || os === 'other';
    const title = os === 'windows' ? 'aureon.defender for Windows' : os === 'android' ? 'aureon.defender for Android' : web ? 'aureon.defender web edition' : 'Portable source preview';
    const description = {windows:'The full Signal dashboard and Windows host tools. Setup for Windows 10/11 x64; no manual ZIP extraction.',android:'Native local monitoring and selected-file checks. For Android 12 and later.',ios:'Local file/hash checks and report reading in Safari. Add it to your Home Screen.',macos:'A limited Python companion for supported Macs. No native Mac download is available yet.',linux:'A limited Python companion for supported Linux and Raspberry Pi systems. Requires Python 3.12.',other:'Open the browser-local file/hash and report tools. No installation needed.'}[os];
    const label = web ? 'Open web tools' : a ? os === 'windows' ? 'Download for Windows' : os === 'android' ? 'Download Android APK' : 'Download source preview' : 'View available downloads';
    const href = web ? 'tools.html' : 'api/download?platform='+(['windows','android'].includes(os)?os:'source');
    document.querySelectorAll('.recommend').forEach(el => { el.href=href;if(!web)el.setAttribute('download','');else el.removeAttribute('download');el.textContent=label+' '+(web?'↗':'↓'); });
    document.querySelectorAll('.recommend-note').forEach(el => { el.textContent=(selected==='auto'?'Recommended for this browser: ':'Selected edition: ')+names[os]+'. You can change it below.'; });
    $('#device-label').textContent=selected==='auto'?'RECOMMENDED FOR THIS DEVICE':'YOUR SELECTED EDITION';
    $('#portable-download').hidden=os!=='windows';$('#download-title').textContent=title; $('#download-description').textContent=description;
    $('#mobile-edition').textContent=names[os];
    $('#download-meta').textContent=a ? `${a.release.tag_name} · ${(a.size/1048576).toFixed(a.size < 1048576 ? 2 : 1)} MiB · Direct GitHub download` : web ? 'Browser-local tools · No app-store account' : 'No compatible binary attached. Choose another edition or inspect the source.';
    $('#checksum').href='api/download?platform=checksums';
    $('#download-boundary').textContent={windows:'Unsigned publisher. Download Setup, open it, and approve the Windows installation prompt. ARM-based Windows may need x64 compatibility; detection does not verify your CPU or OS version.',android:'Android will ask you to allow installation from your download source. Foreground-service and battery restrictions still apply.',ios:'This is a web app, not an IPA, a system antivirus or an unrestricted background monitor.',macos:'Native macOS builds are currently blocked by GitHub account billing restrictions. Source preview is not Windows feature parity.',linux:'Native Linux builds are currently blocked by GitHub account billing restrictions. Raspberry Pi support depends on your OS, Python and hardware.',other:'Browser access is limited to files you explicitly select. It cannot inspect all files or other apps.'}[os];
    $('#install-instructions').textContent={windows:'1. Download Setup. 2. Open the downloaded EXE. It unpacks the full application automatically. 3. Review and approve the Windows administrator prompt. The app opens after successful installation. The publisher is unsigned; review the source/checksum. A website cannot run an installer or approve OS prompts for you. The portable ZIP remains available as an alternative.',android:'1. Download the APK. 2. Review the release checksum and publisher. 3. Allow installation from your chosen source if you trust it. 4. Open Aureon and choose Start monitoring. Updates use the same signing identity; installations remain manual.',ios:'Open Web tools in Safari, tap Share, then Add to Home Screen. Wait for the offline-cache-installed message before going offline. File/hash and report tools are available; downloads still need internet.',macos:'Download and extract the source preview. With Python 3.12 installed, run python -m portable.app from the extracted project folder. Optional psutil provides resource observations. This is a source preview, not a signed Mac app.',linux:'Download and extract the source preview. With Python 3.12 installed, run python -m portable.app from the project folder. Optional psutil provides resource observations. The local dashboard binds to loopback only.',other:'Choose Open web tools. Select a file or exported report yourself. Wait for offline-cache-installed status if you want offline use.'}[os];
  }
  function renderReleases(source, checkedAt) {
    const latest=releases[0]; if(!latest) return;
    const isNew=!!seenOnEntry && seenOnEntry!==latest.tag_name;
    $('#release-name').textContent=latest.name || latest.tag_name;
    const date=new Date(latest.published_at); $('#release-date').textContent=latest.tag_name+(isNaN(date)?'':' · Published '+date.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}));
    $('#release-badge').textContent=isNew?'NEW SINCE YOUR LAST VISIT':'LATEST PUBLISHED RELEASE';
    $('.new-dot').hidden=!isNew; $('#release-link').href='#release-notes';if($('#footer-release'))$('#footer-release').textContent='SIGNAL / '+latest.tag_name;
    $('#release-notes').textContent=(latest.body || 'No release notes provided.').slice(0,30000);
    $('#release-status').textContent=source==='live'?'GitHub release feed · Checked '+new Date(checkedAt||Date.now()).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'Saved release snapshot · Live updates unavailable. Use the release link to verify the latest version.';
    safeStorage.set('aureon-release-seen',latest.tag_name); renderRecommendation();
  }
  async function fetchJSON(url) { const c=new AbortController(),timer=setTimeout(()=>c.abort(),10000); try { const r=await fetch(url,{signal:c.signal,cache:'no-store',headers:{Accept:'application/json'}}); if(!r.ok) throw Error('Release source unavailable');return await r.json(); } finally { clearTimeout(timer); } }
  function accept(data) { if(!Array.isArray(data)) return false;const list=data.filter(validRelease).slice(0,10);if(!list.length)return false;releases=list.sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at));return true; }
  async function refresh() {
    if(pending)return;pending=true;$('#refresh-updates').disabled=true;lastCheck=Date.now();
    try { let data,source='live',checkedAt;try{const payload=await fetchJSON('./api/releases');data=payload.releases;checkedAt=payload.checked_at;source=payload.source==='github'?'live':'saved';if(!Array.isArray(data))throw Error('No server feed');}catch{data=await fetchJSON(API);}if(!accept(data))throw Error('No published release');safeStorage.set('aureon-releases',JSON.stringify(data));renderReleases(source,checkedAt); }
    catch { if(!releases.length) { try { if(!accept(JSON.parse(safeStorage.get('aureon-releases')||'null')))accept(await fetchJSON('./releases.json')); } catch {} } if(releases.length)renderReleases('saved');else {$('#release-name').textContent='Release details unavailable';$('#release-status').textContent='Offline or release service unavailable. Retry or open GitHub releases.';renderRecommendation();} }
    finally {pending=false;$('#refresh-updates').disabled=false;}
  }
  $('#platform').onchange=e=>{selected=e.target.value;renderRecommendation();};
  document.querySelectorAll('[data-edition]').forEach(el=>el.onclick=()=>{selected=el.dataset.edition;$('#platform').value=selected;renderRecommendation();$('#download-title').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
  const support=$('#support-dialog');document.querySelectorAll('[data-support]').forEach(b=>b.onclick=()=>support.showModal());$('#support-close').onclick=()=>support.close();support.addEventListener('click',e=>{if(e.target===support){const r=support.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)support.close();}});$('#support-copy').onclick=async()=>{try{await navigator.clipboard.writeText($('#support-address').value);$('#support-status').textContent='Address copied. Verify the full address and Bitcoin network in your own app.';$('#support-copy').textContent='Copied ✓';}catch{$('#support-address').hidden=false;$('#support-address').focus();$('#support-address').select();$('#support-status').textContent='Address selected. Clipboard unavailable; copy it manually.';}};
  const steps={chrome:['Download and extract the Chromium ZIP to a folder you will keep.','Type chrome://extensions into Chrome’s address bar.','Turn on Developer mode.','Choose Load unpacked and select the extracted folder containing manifest.json.','Review the extension, pin its toolbar icon if wanted, and open its settings.'],edge:['Download and extract the Chromium ZIP to a folder you will keep.','Type edge://extensions into Edge’s address bar.','Turn on Developer mode.','Choose Load unpacked and select the folder containing manifest.json.','Review and pin noah.shield, then configure its settings.'],brave:['Download and extract the Chromium ZIP to a folder you will keep.','Type brave://extensions into Brave’s address bar.','Turn on Developer mode.','Choose Load unpacked and select the folder containing manifest.json.','Review the extension and its settings; browser protections may overlap.'],firefox:['Use the original supplied ZIP for compatibility review; the Chromium-adapted package is not a Firefox build.','For temporary developer testing, extract it and open about:debugging#/runtime/this-firefox.','Choose Load Temporary Add-on and select manifest.json.','Temporary loading ends when Firefox restarts. A compatible Mozilla-signed XPI is required for ordinary permanent installation; none is supplied here.'],mobile:['This ZIP does not install as a native extension in mobile Chrome or Safari.','Use aureon.defender’s Android or web edition for their stated features.','A compatible mobile/ Safari extension package and platform-approved installation path would be separate work.']};
  function browserSteps(){const key=$('#extension-browser').value;$('#extension-steps').replaceChildren(...steps[key].map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));$('#extension-boundary').textContent=['chrome','edge','brave'].includes(key)?'Browser-managed devices may block unpacked extensions. Do not change organization policies or disable browser protections. Keep the extracted folder; reload after manual extension updates.':'Compatibility beyond the isolated Chromium smoke check has not been verified.';}
  $('#extension-browser').onchange=browserSteps;browserSteps();
  $('#refresh-updates').onclick=refresh;$('#release-link').onclick=()=>{$('.release-card details').open=true;};
  const direction=new URLSearchParams(location.search).get('direction');if(['editorial','compact'].includes(direction))document.body.dataset.direction=direction;
  renderRecommendation();fetchJSON('./releases.json').then(data=>{if(!releases.length&&accept(data))renderReleases('saved');}).catch(()=>{});refresh();
  setInterval(()=>{if(!document.hidden)refresh();},300000);document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastCheck>60000)refresh();});
  if('serviceWorker' in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});
  window.AureonLanding={platform,assetFor};
})();

// Bounded visual feedback, passive input listeners, no scroll lock or extra navigation.
(()=>{const root=document.documentElement,motion=matchMedia('(prefers-reduced-motion: reduce)');let offset=0,timer,touchY=null;
 const release=()=>{clearTimeout(timer);root.classList.remove('edge-pulling');offset=0;root.style.setProperty('--edge-offset','0px');};
 function pull(delta,target){if(motion.matches||document.querySelector('dialog[open]')||target?.closest('select,textarea,input,dialog'))return;const bottom=Math.max(0,root.scrollHeight-innerHeight),atTop=scrollY<=1,atBottom=scrollY>=bottom-1;if(bottom<2||!(atTop&&delta<0||atBottom&&delta>0))return;offset=Math.max(-24,Math.min(24,offset-delta*.12));root.classList.add('edge-pulling');root.style.setProperty('--edge-offset',offset+'px');clearTimeout(timer);timer=setTimeout(release,110);}
 addEventListener('wheel',e=>pull(e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?innerHeight:1),e.target),{passive:true});
 addEventListener('touchstart',e=>{touchY=e.touches.length===1?e.touches[0].clientY:null;},{passive:true});addEventListener('touchmove',e=>{if(touchY===null||e.touches.length!==1)return;const y=e.touches[0].clientY;pull(touchY-y,e.target);touchY=y;},{passive:true});addEventListener('touchend',()=>{touchY=null;release();},{passive:true});addEventListener('touchcancel',release,{passive:true});motion.addEventListener('change',release);
})();
