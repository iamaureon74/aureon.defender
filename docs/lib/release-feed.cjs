'use strict';
const snapshot = require('../releases.json');
let cached = null, savedAt = 0;
const REPO = 'https://github.com/shep95/aureon.defender';
module.exports = async function readReleaseFeed() {
  if (cached && Date.now()-savedAt < 300000) return cached;
  try {
    const response=await fetch('https://api.github.com/repos/shep95/aureon.defender/releases?per_page=10',{
      headers:{Accept:'application/vnd.github+json','User-Agent':'Aureon-Public-Release-Reader'},signal:AbortSignal.timeout(8000)
    });
    if (!response.ok) throw Error('Release provider unavailable');
    const data=await response.json();
    if(!Array.isArray(data))throw Error('Invalid release response');
    const releases=data.filter(r=>!r.draft&&!r.prerelease&&typeof r.html_url==='string'&&r.html_url.startsWith(REPO+'/releases/tag/')).slice(0,10).map(r=>({
      tag_name:String(r.tag_name).slice(0,100),name:String(r.name||r.tag_name).slice(0,500),body:String(r.body||'').slice(0,30000),published_at:r.published_at,html_url:r.html_url,draft:false,prerelease:false,
      assets:(r.assets||[]).filter(a=>typeof a.browser_download_url==='string'&&a.browser_download_url.startsWith(REPO+'/releases/download/')).map(a=>({name:a.name,size:a.size,browser_download_url:a.browser_download_url}))
    }));
    if(!releases.length)throw Error('No public releases');
    cached={source:'github',checked_at:new Date().toISOString(),releases};savedAt=Date.now();
    return cached;
  } catch {
    // No credentials, user data, request addresses, or provider error details are retained.
    return cached || {source:'snapshot',releases:snapshot};
  }
};
