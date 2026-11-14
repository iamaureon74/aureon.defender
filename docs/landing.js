'use strict';
(() => {
  const $ = s => document.querySelector(s), REPO = 'https://github.com/shep95/aureon.defender';
  const API = 'https://api.github.com/repos/shep95/aureon.defender/releases?per_page=10';
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
  function validRelease(r) { return r && !r.draft && !r.prerelease && typeof r.tag_name === 'string' && Array.isArray(r.assets) && typeof r.html_url === 'string' && r.html_url.startsWith(REPO + '/releases/tag/'); }
  function assetFor(os) {
    const patterns = { windows:/^aureon-defender-windows-x64-[\d.]+\.zip$/, android:/^aureon-defender-android-[\d.]+\.apk$/, macos:/^aureon-defender-portable-source-[\w.-]+\.zip$/, linux:/^aureon-defender-portable-source-[\w.-]+\.zip$/ };
    for (const r of releases) for (const a of r.assets) {
      if (patterns[os]?.test(a.name) && typeof a.browser_download_url === 'string' && a.browser_download_url.startsWith(REPO + '/releases/download/')) return { ...a, release:r };
    }
    return null;
  }
  const names = { windows:'Windows', android:'Android', ios:'iPhone / iPad', macos:'macOS', linux:'Linux / Raspberry Pi', other:'Web edition' };
  function renderRecommendation() {
    const os = selected === 'auto' ? platform() : selected, a = assetFor(os), web = os === 'ios' || os === 'other';
    const title = os === 'windows' ? 'Aureon for Windows' : os === 'android' ? 'Aureon for Android' : web ? 'Aureon web edition' : 'Portable source preview';
    const description = {windows:'The full Signal dashboard and Windows host tools. For Windows 10/11 x64.',android:'Native local monitoring and selected-file checks. For Android 12 and later.',ios:'Local file/hash checks and report reading in Safari. Add it to your Home Screen.',macos:'A limited Python companion for supported Macs. No native Mac download is available yet.',linux:'A limited Python companion for supported Linux and Raspberry Pi systems. Requires Python 3.12.',other:'Open the browser-local file/hash and report tools. No installation needed.'}[os];
    const label = web ? 'Open web tools' : a ? os === 'windows' ? 'Download for Windows' : os === 'android' ? 'Download Android APK' : 'Download source preview' : 'View available downloads';
    const href = web ? 'tools.html' : a?.browser_download_url || REPO + '/releases/latest';
    document.querySelectorAll('.recommend').forEach(el => { el.href=href; el.textContent=label+' '+(web?'↗':'↓'); });
    document.querySelectorAll('.recommend-note').forEach(el => { el.textContent=(selected==='auto'?'Recommended for this browser: ':'Selected edition: ')+names[os]+'. You can change it below.'; });
    $('#device-label').textContent=selected==='auto'?'RECOMMENDED FOR THIS DEVICE':'YOUR SELECTED EDITION';
    $('#download-title').textContent=title; $('#download-description').textContent=description;
    $('#mobile-edition').textContent=names[os];
    $('#download-meta').textContent=a ? `${a.release.tag_name} · ${(a.size/1048576).toFixed(a.size < 1048576 ? 2 : 1)} MiB · Direct GitHub download` : web ? 'Browser-local tools · No app-store account' : 'No compatible binary attached. Choose another edition or inspect the source.';
    $('#checksum').href=a?.release.html_url || REPO+'/releases/latest';
    $('#download-boundary').textContent={windows:'Unsigned publisher. Extract the whole ZIP. ARM-based Windows may need x64 compatibility; detection does not verify your CPU or OS version.',android:'Android will ask you to allow installation from your download source. Foreground-service and battery restrictions still apply.',ios:'This is a web app, not an IPA, a system antivirus or an unrestricted background monitor.',macos:'Native macOS builds are currently blocked by GitHub account billing restrictions. Source preview is not Windows feature parity.',linux:'Native Linux builds are currently blocked by GitHub account billing restrictions. Raspberry Pi support depends on your OS, Python and hardware.',other:'Browser access is limited to files you explicitly select. It cannot inspect all files or other apps.'}[os];
    $('#install-instructions').textContent={windows:'1. Download and verify SHA256SUMS.txt from the release. 2. Extract the entire ZIP and keep _internal beside aureon.defender.exe. 3. Open the executable. Machine installation requests administrator approval. Do not disable OS protections.',android:'1. Download the APK. 2. Review the release checksum and publisher. 3. Allow installation from your chosen source if you trust it. 4. Open Aureon and choose Start monitoring. Updates use the same signing identity; installations remain manual.',ios:'Open Web tools in Safari, tap Share, then Add to Home Screen. Wait for the offline-cache-installed message before going offline. File/hash and report tools are available; downloads still need internet.',macos:'Download and extract the source preview. With Python 3.12 installed, run python -m portable.app from the extracted project folder. Optional psutil provides resource observations. This is a source preview, not a signed Mac app.',linux:'Download and extract the source preview. With Python 3.12 installed, run python -m portable.app from the project folder. Optional psutil provides resource observations. The local dashboard binds to loopback only.',other:'Choose Open web tools. Select a file or exported report yourself. Wait for offline-cache-installed status if you want offline use.'}[os];
  }
  function renderReleases(source) {
    const latest=releases[0]; if(!latest) return;
    const isNew=!!seenOnEntry && seenOnEntry!==latest.tag_name;
    $('#release-name').textContent=latest.name || latest.tag_name;
    const date=new Date(latest.published_at); $('#release-date').textContent=latest.tag_name+(isNaN(date)?'':' · Published '+date.toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}));
    $('#release-badge').textContent=isNew?'NEW SINCE YOUR LAST VISIT':'LATEST PUBLISHED RELEASE';
    $('.new-dot').hidden=!isNew; $('#release-link').href=latest.html_url;
    $('#release-notes').textContent=(latest.body || 'No release notes provided.').slice(0,30000);
    $('#release-status').textContent=source==='live'?'Up to date with GitHub · Checked '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'Saved release snapshot · Live updates unavailable. Use the release link to verify the latest version.';
    safeStorage.set('aureon-release-seen',latest.tag_name); renderRecommendation();
  }
  async function fetchJSON(url) { const c=new AbortController(),timer=setTimeout(()=>c.abort(),10000); try { const r=await fetch(url,{signal:c.signal,cache:'no-store',headers:{Accept:'application/json'}}); if(!r.ok) throw Error('Release source unavailable');return await r.json(); } finally { clearTimeout(timer); } }
  function accept(data) { if(!Array.isArray(data)) return false;const list=data.filter(validRelease).slice(0,10);if(!list.length)return false;releases=list.sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at));return true; }
  async function refresh() {
    if(pending)return;pending=true;$('#refresh-updates').disabled=true;lastCheck=Date.now();
    try { const data=await fetchJSON(API); if(!accept(data))throw Error('No published release'); safeStorage.set('aureon-releases',JSON.stringify(data));renderReleases('live'); }
    catch { if(!releases.length) { try { if(!accept(JSON.parse(safeStorage.get('aureon-releases')||'null')))accept(await fetchJSON('./releases.json')); } catch {} } if(releases.length)renderReleases('saved');else {$('#release-name').textContent='Release details unavailable';$('#release-status').textContent='Offline or release service unavailable. Retry or open GitHub releases.';renderRecommendation();} }
    finally {pending=false;$('#refresh-updates').disabled=false;}
  }
  $('#platform').onchange=e=>{selected=e.target.value;renderRecommendation();};
  document.querySelectorAll('[data-edition]').forEach(el=>el.onclick=()=>{selected=el.dataset.edition;$('#platform').value=selected;renderRecommendation();$('#download-title').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
  $('#refresh-updates').onclick=refresh;
  const direction=new URLSearchParams(location.search).get('direction');if(['editorial','compact'].includes(direction))document.body.dataset.direction=direction;
  renderRecommendation();fetchJSON('./releases.json').then(data=>{if(!releases.length&&accept(data))renderReleases('saved');}).catch(()=>{});refresh();
  setInterval(()=>{if(!document.hidden)refresh();},300000);document.addEventListener('visibilitychange',()=>{if(!document.hidden&&Date.now()-lastCheck>60000)refresh();});
  if('serviceWorker' in navigator)navigator.serviceWorker.register('./sw.js').catch(()=>{});
  window.AureonLanding={platform,assetFor};
})();
