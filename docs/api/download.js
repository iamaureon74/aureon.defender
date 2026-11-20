const readReleaseFeed=require('../lib/release-feed.cjs');
module.exports=async function(req,res){
 if(req.method!=='GET'){res.setHeader('Allow','GET');return res.status(405).json({error:'GET only'});}
 const platform=req.query.platform,patterns={checksums:/^SHA256SUMS\.txt$/,windows:/^aureon-defender-windows-x64-setup-[\d.]+\.exe$/,'windows-portable':/^aureon-defender-windows-x64-[\d.]+\.zip$/,noah:/^noah-shield-chromium-[\d.]+\.zip$/,'noah-original':/^noah-shield-[\d.]+\.zip$/,android:/^aureon-defender-android-[\d.]+\.apk$/,source:/^aureon-defender-portable-source-[\w.-]+\.zip$/};
 if(!Object.hasOwn(patterns,platform))return res.status(400).json({error:'Choose a supported device edition.'});
 const feed=await readReleaseFeed();
 for(const release of feed.releases||[])for(const asset of release.assets||[]){
  if(patterns[platform].test(asset.name)&&['iamaureon74','shep95'].some(o=>asset.browser_download_url.startsWith('https://github.com/'+o+'/aureon.defender/releases/download/'))){
   res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Location',asset.browser_download_url);return res.status(302).end();
  }
 }
 return res.status(503).json({error:'No matching published download is available. Please try again later.'});
};
