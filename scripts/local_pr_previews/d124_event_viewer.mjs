import http from 'node:http';
import {promises as fs, constants} from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const options=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=',2)));
if(!options.checkout||!options.bundle)throw Error('EXPLICIT_CHECKOUT_AND_SAFE_BUNDLE_REQUIRED');
const repo=path.resolve(options.checkout);
const head='62a8979632d800e9ac6d23fc29789e56a11550bc';
const root=path.resolve(options.bundle);
const manifestPin='ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01';
const port=8770, hash=b=>createHash('sha256').update(b).digest('hex');
if(execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim()!==head||execFileSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).trim())throw Error('EXACT_CLEAN_HEAD_REQUIRED');
const {inspectPng}=await import(pathToFileURL(path.join(repo,'frontend/event-viewer/guard.mjs')));
async function readPinned(rel,pin){
 let current=root;
 for(const part of rel.split('/')){if(!part||['.','..'].includes(part)||part.includes('\\'))throw Error('PATH');current=path.join(current,part);if((await fs.lstat(current)).isSymbolicLink())throw Error('SYMLINK');}
 if(!current.startsWith(root+'/')||(await fs.realpath(current))!==current)throw Error('PATH');
 const fd=await fs.open(current,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
 try{const st=await fd.stat();if(!st.isFile()||st.size>16*1024*1024)throw Error('FILE');const b=await fd.readFile();if(hash(b)!==pin)throw Error('PIN');return b;}finally{await fd.close();}
}
const m=JSON.parse(await readPinned('manifest.json',manifestPin));
const runs=[],frames=new Map();
for(const label of ['A4-1','B4-1']){
 const rel=`runs/${label}.json`,d=JSON.parse(await readPinned(rel,m.files[rel]));
 const clock=JSON.parse(await readPinned(d.clock_ref,m.files[d.clock_ref]));
 if(clock.run_id!==d.run_id||!d.run_id.endsWith('-d124-v1'))throw Error('RUN_CLOCK');
 const count=clock.source_duration_us/200000;
 if(d.frames.length!==count*d.camera_ids.length)throw Error('GRID');
 for(const f of d.frames){if(f.filename!==`rgb/${d.run_id}/${f.camera_id}/frame_${String(f.frame_index).padStart(6,'0')}.png`||!d.camera_ids.includes(f.camera_id)||f.frame_index<0||f.frame_index>=count||m.files[f.filename]!==f.file_sha256)throw Error('FRAME_SCOPE');const key=`/media/${label}/${f.camera_id}/${String(f.frame_index).padStart(6,'0')}.png`;if(frames.has(key))throw Error('DUPLICATE');frames.set(key,f);}
 runs.push({key:label,label:`${label} · D124 新 run · 查看`,runId:d.run_id,frames:count,cameras:d.camera_ids,fps:5,status:'OK',wall_origin:clock.wall_origin,timezone:clock.timezone,clock_id:clock.clock_id});
}
let checked=0;const queue=[...frames.values()];
await Promise.all(Array.from({length:4},async()=>{for(let f=queue.shift();f;f=queue.shift()){const b=await readPinned(f.filename,f.file_sha256);if(!inspectPng(b).ok)throw Error('PNG_SAFE_FORMAT');checked++;}}));
const staticFiles=new Map([['/',['index.html','text/html; charset=utf-8']],['/app.mjs',['app.mjs','text/javascript']],['/sync.mjs',['sync.mjs','text/javascript']],['/style.css',['style.css','text/css']]]);
const server=http.createServer(async(req,res)=>{
 const send=(code,type,body)=>{res.writeHead(code,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(body);};
 try{
 if(req.headers.host!==`127.0.0.1:${port}`)return send(403,'text/plain','forbidden');
 if(!['GET','HEAD'].includes(req.method))return send(405,'text/plain','read only');
 const u=new URL(req.url,`http://127.0.0.1:${port}`);
 if(staticFiles.has(u.pathname)){const [name,mime]=staticFiles.get(u.pathname);let b=await fs.readFile(path.join(repo,'frontend/event-viewer',name));if(name==='index.html')b=Buffer.from(b.toString().replace('<body>','<body><div style="background:#143b43;color:white;padding:10px 18px;font:14px system-ui">ACTUAL BLENDER RGB · #442 D124 新 run · 獨立唯讀查看，未整合查找／追蹤。A4 原點 2026-11-01 14:00、B4 原點 14:10（Asia/Taipei）。</div>'));return send(200,mime,b);}
 if(u.pathname==='/api/runs'){let requested='';try{const ref=new URL(req.headers.referer);if(ref.origin===`http://127.0.0.1:${port}`)requested=ref.searchParams.get('run');}catch{}const ordered=[...runs].sort((a,b)=>(a.key===requested?-1:b.key===requested?1:0));return send(200,'application/json',JSON.stringify(ordered));}
 if(u.pathname==='/health')return send(200,'application/json',JSON.stringify({head,source_manifest_sha256:manifestPin,verified_frames:checked,runs:runs.map(r=>r.runId)}));
 const f=frames.get(u.pathname);if(!f)return send(404,'text/plain','not found');
 const b=await readPinned(f.filename,f.file_sha256);if(!inspectPng(b).ok)throw Error('PNG');return send(200,'image/png',b);
 }catch{return send(404,'text/plain','unavailable');}
});
server.listen(port,'127.0.0.1',()=>console.log(JSON.stringify({status:'READY',url:`http://127.0.0.1:${port}/`,head,verified_frames:checked,source_manifest_sha256:manifestPin})));
