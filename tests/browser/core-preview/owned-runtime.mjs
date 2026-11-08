// Shared #486 paths for both browser gates; no legacy temporary package fallback.
import {readFileSync} from 'node:fs';
import {resolve,dirname,isAbsolute,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {homedir} from 'node:os';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
export function ownedRuntime(){
  const config=JSON.parse(readFileSync(resolve(repo,'configs/demo_integration_local.json'),'utf8'));
  const raw=process.env.AMIDST_DEMO_HOME??config.owned_root;
  const root=resolve(raw.startsWith('~/')?resolve(homedir(),raw.slice(2)):raw);
  const local=part=>{if(isAbsolute(part))throw Error('OWNED_RELATIVE_PATH_REQUIRED');const result=resolve(root,part);if(!result.startsWith(root+sep))throw Error('OWNED_PATH_ESCAPE');return result;};
  return {root,playwrightModule:local(config.playwright_module),evidenceRoot:local(config.evidence_root)};
}
