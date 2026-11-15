// An isolated ephemeral HTTP server and headless Chrome; never touches port 8785.
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const options=Object.fromEntries(process.argv.slice(2).reduce((a,v,i,all)=>i%2===0?[...a,[v.replace(/^--/,''),all[i+1]]]:a,[]));
for(const key of ['assets','runtime','out'])if(!options[key])throw new Error('Missing --'+key);
const {chromium}=await import(pathToFileURL(path.join(options.runtime,'node_modules/playwright-core/index.mjs')));
const viewer=path.join(path.dirname(fileURLToPath(import.meta.url)),'n6_viewer');
const roots={'assets':options.assets,'three':path.join(options.runtime,'node_modules/three'),'viewer':viewer};
const server=http.createServer(async(req,res)=>{
  try{
    const url=new URL(req.url,'http://localhost');
    const [mount,...parts]=url.pathname.slice(1).split('/');
    if(!roots[mount]){res.writeHead(404).end();return;}
    const root=path.resolve(roots[mount]);const file=path.resolve(root,decodeURIComponent(parts.join('/')||'index.html'));
    if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
    const data=await fs.readFile(file);
    const mime={'.html':'text/html','.js':'text/javascript','.json':'application/json','.glb':'model/gltf-binary','.png':'image/png'};
    res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');res.end(data);
  }catch(e){res.writeHead(404).end(String(e));}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const port=server.address().port;
if(options.serve==='true'){
  console.log(`N6 isolated viewer: http://127.0.0.1:${port}/viewer/index.html (Ctrl-C to stop)`);
  await new Promise(()=>{});
}
const browser=await chromium.launch({executablePath:options.chrome||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,
  args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking']});
try{
  await fs.mkdir(options.out,{recursive:true});
  const page=await browser.newPage({viewport:{width:960,height:660},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(`http://127.0.0.1:${port}/viewer/index.html`);
  await page.waitForFunction(()=>window.n6?.ready,{timeout:90000});
  const metrics=await page.evaluate(()=>window.n6.metrics());
  for(const clip of ['walk','run','idle']){
    await page.evaluate(name=>window.n6.showClip(name,.15),clip);
    await page.locator('canvas').screenshot({path:path.join(options.out,'character_'+clip+'.png')});
  }
  for(const actor of ['T','A','B','C']){
    await page.evaluate(actor=>window.n6.showClip('idle',.15,actor),actor);
    await page.locator('canvas').screenshot({path:path.join(options.out,'variant_'+actor+'.png')});
  }
  const ids=await page.evaluate(()=>window.n6.cameraIds);
  for(const id of ids){
    await page.evaluate(id=>window.n6.showCamera(id),id);
    await page.locator('canvas').screenshot({path:path.join(options.out,id+'.png')});
  }
  const report={schema:'amidst.n6-viewer-validation.v1',browser:await browser.version(),three:'0.186.1',
    renderer:'Headless Chrome / ANGLE SwiftShader',image_size_px:[960,540],clips:metrics,cameras:ids,
    irradiance:await page.evaluate(()=>window.n6.irradiance),page_errors:errors,port_8785_touched:false};
  if(errors.length)throw new Error(JSON.stringify(errors));
  await fs.writeFile(path.join(options.out,'VIEWER_REPORT.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
}finally{await browser.close();await new Promise(r=>server.close(r));}
