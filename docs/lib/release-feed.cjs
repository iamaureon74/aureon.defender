'use strict';
const snapshot = require('../releases.json');
let cached = null, savedAt = 0;
// New releases are published from iamaureon74/aureon.defender; earlier ones stay on shep95/aureon.defender.
const REPOS = ['iamaureon74/aureon.defender', 'shep95/aureon.defender'];
const OK = url => typeof url === 'string' && REPOS.some(r => url.startsWith('https://github.com/' + r + '/releases/'));
module.exports = async function readReleaseFeed() {
  if (cached && Date.now()-savedAt < 300000) return cached;
  try {
    const data=[];
    for (const repo of REPOS) {
      try {
        const response=await fetch('https://api.github.com/repos/'+repo+'/releases?per_page=10',{
          headers:{Accept:'application/vnd.github+json','User-Agent':'Aureon-Public-Release-Reader'},signal:AbortSignal.timeout(8000)
        });
        if (!response.ok) continue;
        const list=await response.json();
        if (Array.isArray(list)) data.push(...list);
      } catch {}
    }
    data.sort((a,b)=>String(b.published_at).localeCompare(String(a.published_at)));
    const releases=data.filter(r=>!r.draft&&!r.prerelease&&OK(r.html_url)).slice(0,10).map(r=>({
      tag_name:String(r.tag_name).slice(0,100),name:String(r.name||r.tag_name).slice(0,500),body:String(r.body||'').slice(0,30000),published_at:r.published_at,html_url:r.html_url,draft:false,prerelease:false,
      assets:(r.assets||[]).filter(a=>OK(a.browser_download_url)).map(a=>({name:a.name,size:a.size,browser_download_url:a.browser_download_url}))
    }));
    if(!releases.length)throw Error('No public releases');
    cached={source:'github',checked_at:new Date().toISOString(),releases};savedAt=Date.now();
    return cached;
  } catch {
    // No credentials, user data, request addresses, or provider error details are retained.
    return cached || {source:'snapshot',releases:snapshot};
  }
};
