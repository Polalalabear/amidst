// Shared #486 paths for both browser gates; no legacy temporary package fallback.
import {existsSync,readFileSync,realpathSync} from 'node:fs';
import {resolve,dirname,isAbsolute,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {homedir} from 'node:os';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
export function ownedRuntime(){
  const config=JSON.parse(readFileSync(resolve(repo,'configs/demo_integration_local.json'),'utf8'));
  const raw=process.env.AMIDST_DEMO_HOME??config.owned_root;
  const base=process.env.AMIDST_ROOT?resolve(process.env.AMIDST_ROOT):repo;
  const root=resolve(raw.startsWith('~/')?resolve(homedir(),raw.slice(2)):resolve(base,raw));
  if(!existsSync(root))throw Error(`OWNED_ROOT_NOT_FOUND: ${root}. Set AMIDST_DEMO_HOME to the owned demo package, or place it at <repo>/local/data/demo-owned-v1.`);
  const local=part=>{if(isAbsolute(part))throw Error('OWNED_RELATIVE_PATH_REQUIRED');const result=resolve(root,part);if(!result.startsWith(root+sep))throw Error('OWNED_PATH_ESCAPE');return result;};
  const module=resolve(repo,config.node.playwright_module);
  if(!module.startsWith(repo+sep)||!realpathSync(module).startsWith(repo+sep))throw Error('REPOSITORY_NODE_DEPENDENCY_REQUIRED');
  return {root,playwrightModule:module,evidenceRoot:local(config.evidence_root)};
}
