const readReleaseFeed=require('../lib/release-feed.cjs');
module.exports=async function(req,res){if(req.method!=='GET'){res.setHeader('Allow','GET');return res.status(405).json({error:'GET only'});}res.setHeader('Cache-Control','public, max-age=30, s-maxage=300, stale-while-revalidate=3600');res.setHeader('X-Content-Type-Options','nosniff');return res.status(200).json(await readReleaseFeed());};
