// Exact configured aliases; display text never changes request canonical IDs.
export function validateAliases(aliases, validIds, {allowUnavailable=false}={}) {
  if(!aliases||typeof aliases!=='object'||Array.isArray(aliases)||!Array.isArray(validIds))throw new Error('ALIAS_CONFIG_INVALID');
  const map=new Map();
  for(const [alias,target] of Object.entries(aliases)){
    if(!alias||typeof target!=='string'||!target)throw new Error('ALIAS_CONFIG_INVALID');
    const key=alias.toLowerCase();
    if(map.has(key)||(validIds.includes(alias)&&alias!==target))throw new Error('ALIAS_CONFLICT');
    if(!allowUnavailable&&!validIds.includes(target))throw new Error('ALIAS_TARGET_UNKNOWN');
    const canonical=validIds.find(v=>v.toLowerCase()===key);
    if(canonical&&canonical!==target)throw new Error('ALIAS_CONFLICT');
    map.set(key,target);
  }
  return map;
}
export function resolveAlias(value,aliases,validIds,options) {
  const map=validateAliases(aliases,validIds,options);
  const target=typeof value==='string'?(map.get(value.toLowerCase())??(validIds.includes(value)?value:null)):null;
  if(target===null)throw new Error('ALIAS_UNKNOWN');
  if(!validIds.includes(target))throw new Error('ALIAS_TARGET_UNKNOWN');
  return target;
}
export function displayOptions(ids,aliases={}) {
  validateAliases(aliases,ids);
  return ids.map(value=>({value,label:Object.entries(aliases).find(([a,v])=>v===value&&/[\u3400-\u9fff]/u.test(a))?.[0]??value}));
}
export function regionOptions(run) {
  const c=run?.region_catalog;
  if(!c)return {status:'UNKNOWN',options:[]};
  if(c.scene_id!==run.scene_id||c.scene_revision!==run.scene_revision||c.region_graph_sha256!==run.region_graph_sha256||!c.region_graph_sha256||!Array.isArray(c.regions))throw new Error('REGION_CATALOG_MISMATCH');
  const ids=new Set();
  const options=c.regions.map(r=>{if(!r||typeof r.region_id!=='string'||!r.region_id||typeof r.label!=='string'||!r.label||ids.has(r.region_id))throw new Error('REGION_CATALOG_INVALID');ids.add(r.region_id);return {value:r.region_id,label:r.label};});
  return {status:'READY',options};
}
export function selectedRegionIds(run,value) {
  if(!value)return null;
  const r=regionOptions(run);
  if(r.status!=='READY'||!r.options.some(o=>o.value===value))throw new Error('REGION_UNKNOWN');
  return [value];
}
