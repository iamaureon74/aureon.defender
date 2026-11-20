'use strict';
/* Browser-only metadata cleaner for the no-install web edition (iPhone, iPad, Android, Mac, Linux, ChromeOS).
   Files never leave the device: they are read with FileReader/Blob APIs, rewritten in memory and handed back as a
   download. Pixels/audio are never re-encoded; only metadata containers are removed. Mirrors the desktop engine. */
(function(){
const q=s=>document.querySelector(s);
const u8=b=>new Uint8Array(b);
const be16=(d,i)=>(d[i]<<8)|d[i+1], be32=(d,i)=>((d[i]<<24)>>>0)+(d[i+1]<<16)+(d[i+2]<<8)+d[i+3];
const le32=(d,i)=>(d[i]|(d[i+1]<<8)|(d[i+2]<<16)|(d[i+3]<<24))>>>0;
function cat(parts){let n=0;for(const p of parts)n+=p.length;const o=new Uint8Array(n);let k=0;for(const p of parts){o.set(p,k);k+=p.length;}return o;}
const ascii=(d,i,n)=>String.fromCharCode(...d.subarray(i,i+n));

function jpegOrientation(d){let i=2;while(i+4<=d.length&&d[i]===0xFF){const m=d[i+1];if(m===0xDA)break;if((m>=0xD0&&m<=0xD7)||m===1){i+=2;continue;}
 const ln=be16(d,i+2),s=i+4;if(m===0xE1&&ascii(d,s,4)==='Exif'){const t=s+6,le=d[t]===0x49;const r16=j=>le?d[j]|(d[j+1]<<8):be16(d,j),r32=j=>le?le32(d,j):be32(d,j);
  const off=t+r32(t+4),n=r16(off);for(let k=0;k<n&&k<512;k++){const e=off+2+12*k;if(r16(e)===0x0112&&r16(e+2)===3){const v=r16(e+8);return v>=1&&v<=8?v:null;}}return null;}
 i+=2+ln;}return null;}
function orientationSeg(v){const tiff=[0x4D,0x4D,0,0x2A,0,0,0,8,0,1,0x01,0x12,0,3,0,0,0,1,0,v,0,0,0,0,0,0];const body=[0x45,0x78,0x69,0x66,0,0,...tiff];const n=body.length+2;return new Uint8Array([0xFF,0xE1,n>>8,n&255,...body]);}
const JPEG_DROP=new Set([0xE1,0xED,0xFE,0xE3,0xE4,0xE5,0xE6,0xE7,0xE8,0xE9,0xEA,0xEB,0xEC,0xEF]);
function jpeg(d){if(d[0]!==0xFF||d[1]!==0xD8)throw Error('not a jpeg');const orient=jpegOrientation(d);const out=[d.subarray(0,2)];const removed=new Set();let i=2,afterApp0=null;
 while(i<d.length){if(d[i]!==0xFF)throw Error('damaged jpeg');const m=d[i+1];if(m===0xDA){let e=-1;for(let k=i+2;k+1<d.length;k++)if(d[k]===0xFF&&d[k+1]===0xD9){e=k;break;}if(e<0){out.push(d.subarray(i));break;}out.push(d.subarray(i,e+2));if(e+2<d.length){const tail=d.subarray(e+2,e+66);removed.add(ascii(tail,4,4)==='ftyp'?'embedded motion-photo video':tail[0]===0xFF&&tail[1]===0xD8?'appended image or depth map':'data appended after the picture');}break;}
  if((m>=0xD0&&m<=0xD7)||m===1){out.push(d.subarray(i,i+2));i+=2;continue;}
  const ln=be16(d,i+2),seg=d.subarray(i,i+2+ln);if(JPEG_DROP.has(m))removed.add(m===0xE1?'exif/xmp (camera, gps, time)':m===0xFE?'comment':m===0xED?'iptc/photoshop':'app data');else if(m===0xE2&&ascii(d,i+4,11)!=='ICC_PROFILE')removed.add(ascii(d,i+4,3)==='MPF'?'multi-picture index (mpf)':'app2 block');else{out.push(seg);if(m===0xE0)afterApp0=out.length;}i+=2+ln;}
 if(orient&&orient!==1)out.splice(afterApp0||1,0,orientationSeg(orient));return[cat(out),[...removed]];}
const PNG_KEEP=new Set(['IHDR','PLTE','IDAT','IEND','tRNS','gAMA','cHRM','sRGB','iCCP','sBIT','bKGD','pHYs','acTL','fcTL','fdAT','cICP','mDCv','cLLi']);
function png(d){if(be32(d,0)!==0x89504E47)throw Error('not a png');const out=[d.subarray(0,8)],removed=new Set();let i=8;
 while(i<d.length){const ln=be32(d,i),t=ascii(d,i+4,4),ch=d.subarray(i,i+12+ln);if(!PNG_KEEP.has(t))removed.add(t==='tIME'?'time':t==='caBX'?'content credentials (c2pa)':t==='dSIG'?'digital signature':/^(tEXt|iTXt|zTXt|eXIf)$/.test(t)?'text/exif':t+' chunk');else out.push(ch);i+=12+ln;if(t==='IEND'){if(i<d.length)removed.add('data after the image end');break;}}
 return[cat(out),[...removed]];}
function webp(d){if(ascii(d,0,4)!=='RIFF'||ascii(d,8,4)!=='WEBP')throw Error('not webp');const out=[d.slice(0,12)],removed=[];let i=12;
 while(i+8<=d.length){const t=ascii(d,i,4),ln=le32(d,i+4),step=8+ln+(ln&1);let ch=d.slice(i,i+step);if(t==='EXIF'||t==='XMP '){removed.push(t.trim().toLowerCase());}else{if(t==='VP8X')ch[8]&=~0x0C;out.push(ch);}i+=step;}
 const o=cat(out);new DataView(o.buffer).setUint32(4,o.length-8,true);return[o,removed];}
function mp3(d){let s=0,e=d.length;const removed=[];
 while(ascii(d,s,3)==='ID3'){let n=0;for(let k=6;k<10;k++)n=(n<<7)|(d[s+k]&0x7F);s+=10+n+((d[s+5]&0x10)?10:0);removed.push('id3v2 tags (artist, comments, pictures)');}
 if(e>=128&&ascii(d,e-128,3)==='TAG'){e-=128;removed.push('id3v1 tags');}
 if(e>=32&&ascii(d,e-32,8)==='APETAGEX'){const size=le32(d,e-20),flags=le32(d,e-12);const tot=size+((flags&0x80000000)?32:0);if(tot<=e){e-=tot;removed.push('ape tags');}}
 return[d.slice(s,e),[...new Set(removed)]];}
function pdf(d){const s=new TextDecoder('latin1').decode(d);let removed=[];
 let t=s.replace(/(\/(?:Author|Creator|Producer|Title|Subject|Keywords|Company|CreationDate|ModDate)\s*)\(((?:[^()\\]|\\.)*)\)/g,(m,a,b)=>{removed.push('document info');return a+'('+' '.repeat(b.length)+')';});
 t=t.replace(/(\/(?:Author|Creator|Producer|Title|Subject|Keywords|CreationDate|ModDate)\s*)<([0-9A-Fa-f\s]*)>/g,(m,a,b)=>{removed.push('document info');return a+'<'+'20'.repeat(b.length>>1)+(b.length&1?'2':'')+'>';});
 t=t.replace(/<\?xpacket begin[\s\S]*?<\?xpacket end=['"]w['"]\?>/g,m=>{removed.push('xmp');const a=m.indexOf('?>')+2,b=m.lastIndexOf('<?xpacket end');return m.slice(0,a)+' '.repeat(b-a)+m.slice(b);});
 const o=new Uint8Array(t.length);for(let k=0;k<t.length;k++)o[k]=t.charCodeAt(k)&255;return[o,[...new Set(removed)]];}
const HANDLERS={jpg:jpeg,jpeg:jpeg,png:png,webp:webp,mp3:mp3,pdf:pdf};
window.aureonClean={jpeg,png,webp,mp3,pdf,jpegOrientation};

const input=q('#clean-files'),list=q('#clean-result');
if(!input||!list)return;
input.onchange=async()=>{list.textContent='';
 for(const f of [...input.files].slice(0,50)){const li=document.createElement('li');list.append(li);
  try{const ext=(f.name.split('.').pop()||'').toLowerCase();const h=HANDLERS[ext];if(!h)throw Error('the web edition handles jpeg, png, webp, mp3 and pdf; other types need the windows app');
   if(f.size>128*1024*1024)throw Error('larger than 128 mib');
   const[out,removed]=h(u8(await f.arrayBuffer()));const blob=new Blob([out],{type:f.type||'application/octet-stream'});
   const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=f.name.replace(/(\.[^.]+)$/,'.clean$1');a.textContent='save a copy';
   const nm=document.createElement('span');nm.className='keep-case';nm.textContent=f.name;li.append(nm,document.createTextNode(': '+(removed.length?'removed '+removed.join(', '):'no known hidden details found')+'. '),a);
   setTimeout(()=>URL.revokeObjectURL(a.href),10*60*1000);}
  catch(e){const nm=document.createElement('span');nm.className='keep-case';nm.textContent=f.name;li.append(nm,document.createTextNode(': not cleaned — '+String(e.message).toLowerCase()+'. the original is unchanged.'));}}};
})();
