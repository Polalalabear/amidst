// Read-only format adapter over a clean, unmerged #408 event-viewer checkout.
import http from 'node:http';
import {readFile,realpath,open,constants} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
const args=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=',2)));
const repo=await realpath(args.checkout),proxyRoot=await realpath(args.proxies),port=Number(args.port??8780);
const head=execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim();
if(head!=='eb10d4c62ce09a765488cdd0548cfdd3abfd5109'||execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).trim())throw Error('EXACT_CLEAN_408_REQUIRED');
const sha=b=>createHash('sha256').update(b).digest('hex');
const raw=await readFile(path.join(proxyRoot,'manifest.json'));if(sha(raw)!==args['manifest-sha256'])throw Error('MANIFEST_PIN');
const manifest=JSON.parse(raw),rows=new Map(manifest.rows.map(r=>[`${r.case}/${r.camera_id}/${String(r.frame_index).padStart(6,'0')}`,r]));
async function pinned(file,pin){
  if(await realpath(file)!==file)throw Error('CANONICAL_FILE');
  const fd=await open(file,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
  try{const s=await fd.stat();if(!s.isFile()||s.size>16777216)throw Error('BOUNDED_FILE');const b=await fd.readFile();if(sha(b)!==pin)throw Error('FILE_PIN');return b;}finally{await fd.close();}
}
function publicPng(b){
  if(b.subarray(0,8).toString('hex')!=='89504e470d0a1a0a')throw Error('PNG');
  const allowed=new Set(['IHDR','IDAT','IEND','sRGB','gAMA','pHYs','cHRM','bKGD','sBIT']),chunks=[b.subarray(0,8)];let offset=8;
  while(offset<b.length){const n=b.readUInt32BE(offset),end=offset+n+12,kind=b.toString('ascii',offset+4,offset+8);if(end>b.length)throw Error('PNG');if(allowed.has(kind))chunks.push(b.subarray(offset,end));else if((kind.charCodeAt(0)&32)===0)throw Error('PNG_CRITICAL');offset=end;if(kind==='IEND'){if(n||offset!==b.length)throw Error('PNG_END');break;}}
  return Buffer.concat(chunks);
}
const staticFiles=new Map([['/',['index.html','text/html; charset=utf-8']],['/app.mjs',['app.mjs','text/javascript']],['/sync.mjs',['sync.mjs','text/javascript']],['/style.css',['style.css','text/css']]]);
const server=http.createServer(async(req,res)=>{
 const send=(status,type,body)=>{res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Timing-Allow-Origin':`http://127.0.0.1:${port}`});res.end(body);};
 try{
  if(req.headers.host!==`127.0.0.1:${port}`||req.method!=='GET')return send(403,'text/plain','read only loopback');
  const url=new URL(req.url,`http://127.0.0.1:${port}`);let referer;
  try{referer=new URL(req.headers.referer);if(referer.origin!==url.origin)referer=null;}catch{}
  const selected=url.searchParams.get('run')??referer?.searchParams.get('run'),fmt=url.searchParams.get('format')??referer?.searchParams.get('format')??'png';
  if(!['png','jpeg','webp'].includes(fmt))throw Error('FORMAT');
  if(url.pathname==='/health')return send(200,'application/json',JSON.stringify({source_head:head,source_checkout:repo,manifest_sha256:args['manifest-sha256'],scope:'READ_ONLY_PLAYBACK_FORMAT_BENCH'}));
  if(staticFiles.has(url.pathname)){
   const [name,type]=staticFiles.get(url.pathname);let b=await readFile(path.join(repo,'frontend/event-viewer',name));
   if(name==='index.html')b=Buffer.from(b.toString().replace('<body>',`<body><div style="background:#713b09;color:white;padding:8px;font:14px system-ui">LOCAL PLAYBACK BENCH · ${fmt.toUpperCase()} · B-05b=SYNTHETIC; A4/B4=ACTUAL BLENDER · proxies never inference</div>`));
   return send(200,type,b);
  }
  if(url.pathname==='/api/runs'){
   const runs=manifest.cases.map(c=>({...c,runId:c.run_id,label:`${c.key} · ${c.source_kind} · ${fmt}`,status:'OK',wall_origin:null,timezone:'Asia/Taipei'}));
   runs.sort((a,b)=>a.key===selected?-1:b.key===selected?1:0);return send(200,'application/json',JSON.stringify(runs));
  }
  const match=url.pathname.match(/^\/media\/([A-Za-z0-9_-]+)\/([A-Za-z0-9_]+)\/(\d{6})\.png$/);if(!match)return send(404,'text/plain','not found');
  const row=rows.get(match.slice(1).join('/'));if(!row)return send(404,'text/plain','not found');
  if(fmt==='png'){const b=publicPng(await pinned(row.path,row.sha256));if(sha(b)!==row.png_public_sha256)throw Error('PUBLIC_PNG_PIN');return send(200,'image/png',b);}
  const p=row.proxies[fmt],file=path.resolve(proxyRoot,p.relative_path);if(!file.startsWith(proxyRoot+'/'))throw Error('PROXY_PATH');
  return send(200,fmt==='jpeg'?'image/jpeg':'image/webp',await pinned(file,p.sha256));
 }catch{return send(404,'text/plain','unavailable');}
});
server.listen(port,'127.0.0.1',()=>console.log(JSON.stringify({url:`http://127.0.0.1:${port}/`,source_head:head,manifest_sha256:args['manifest-sha256']})));
