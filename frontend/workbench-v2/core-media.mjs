// Pure media resolver and synthetic frame image generator for core screens (W-A5)
// Pure SVG data URIs and resolver hooks; no GT, no z-distance, no private paths.

export function escapeXml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function createSyntheticFrameDataUri({
  cameraId = 'CAM',
  label = '',
  token = '',
  kind = 'OBSERVED',
} = {}) {
  const isGap = kind === 'GAP';
  const isLost = kind === 'LOST';
  const isStatic = kind === 'STATIC';
  const bg = isGap ? '#1f1e1b' : isLost ? '#261b1b' : isStatic ? '#181b22' : '#141c2b';
  const border = isGap ? '#e5c07b' : isLost ? '#e06c75' : isStatic ? '#4b5263' : '#61afef';
  const strokeDash = isGap ? 'stroke-dasharray="6,4"' : '';
  const camText = String(cameraId ?? 'CAM');
  const subText = ['SYNTHETIC',label, token].filter(Boolean).join(' · ');

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
  <rect width="100%" height="100%" fill="${bg}"/>
  <rect x="2" y="2" width="316" height="176" fill="none" stroke="${border}" stroke-width="2" ${strokeDash}/>
  <circle cx="160" cy="70" r="28" fill="${border}" fill-opacity="0.15" stroke="${border}" stroke-width="1.5"/>
  <text x="50%" y="42%" dominant-baseline="middle" text-anchor="middle" fill="#f0f6fc" font-family="system-ui, sans-serif" font-size="14" font-weight="bold">${escapeXml(camText)}</text>
  <text x="50%" y="68%" dominant-baseline="middle" text-anchor="middle" fill="#abb2bf" font-family="system-ui, sans-serif" font-size="11">${escapeXml(subText)}</text>
</svg>`.trim();

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function resolveCardImageSrc({
  card,
  mediaResolver = null,
  synthetic = false,
  onResolved = null,
} = {}) {
  let initialSrc = synthetic ? createSyntheticFrameDataUri({
      cameraId: card?.cameraId ?? 'CAM',
      label: '影像示意',
      kind: card?.targetObserved ? 'OBSERVED' : 'STATIC',
    }) : null;

  if (typeof mediaResolver === 'function') {
    try {
      const res = mediaResolver({
        mediaToken: card?.mediaToken,
        frameRef: card?.frameRef,
        cameraId: card?.cameraId,
        targetObserved: card?.targetObserved,
        rank: card?.rank,
        kind: 'search_card',
      });
      if (res && typeof res.then === 'function') {
        res.then((url) => {
          if (MEDIA_URL.test(url??'') && typeof onResolved === 'function') onResolved(url);
        }).catch(() => {});
      } else if (MEDIA_URL.test(res??'')) {
        initialSrc = res;
      }
    } catch {}
  }

  return initialSrc;
}

export function resolveFrameImageSrc({
  cameraId,
  currentTUs = 0,
  segmentKind = 'ON_CAMERA',
  lastObservedCameraId = null,
  includeCandidate = false,
  mediaResolver = null,
  synthetic = false,
  onResolved = null,
} = {}) {
  const timeSec = (currentTUs / 1000000).toFixed(2);
  let label = '';
  let effectiveCam = cameraId;

  if (segmentKind === 'ON_CAMERA') {
    label = `OBSERVED · ${timeSec}s`;
  } else if (segmentKind === 'GAP') {
    effectiveCam = lastObservedCameraId ?? 'BLIND_GAP';
    label = `盲區間隔 · ${timeSec}s`;
  } else if (segmentKind === 'LOST') {
    effectiveCam = 'LOST';
    label = `目標遺失 · ${timeSec}s`;
  } else {
    effectiveCam = 'UNKNOWN';
    label = `未知狀態 · ${timeSec}s`;
  }

  let initialSrc = synthetic ? createSyntheticFrameDataUri({
    cameraId: effectiveCam,
    label: '影像示意 · '+label,
    kind: segmentKind,
  }) : null;

  if ((segmentKind === 'ON_CAMERA' || (segmentKind === 'CANDIDATE' && includeCandidate)) && typeof mediaResolver === 'function') {
    try {
      const res = mediaResolver({
        cameraId,
        currentTUs,
        segmentKind,
        lastObservedCameraId,
        kind: 'tracking_frame',
      });
      if (res && typeof res.then === 'function') {
        res.then((url) => {
          if (MEDIA_URL.test(url??'') && typeof onResolved === 'function') onResolved(url);
        }).catch(() => {});
      } else if (MEDIA_URL.test(res??'')) {
        initialSrc = res;
      }
    } catch {}
  }

  return initialSrc;
}

const MEDIA_URL=/^\/api\/controlled_scene_media\?token=[A-Za-z0-9_-]{43}$/;
export function createBoundMediaResolver({store,api}) {
  return async ({kind,cameraId,mediaToken,currentTUs,segmentKind,targetObserved}) => {
    const before=store.getState();
    const run=before.activeRun;
    const response=kind==='search_card'?before.coreSearchResponse:before.coreTrackResponse;
    if(!run||!response||!run.clock_id||!run.clock_mapping?.content_sha256||!run.camera_ids?.includes(cameraId)||api.getOrigin?.()==='SYNTHETIC_FIXTURE')return null;
    const scope=response.resolved_scope;
    if((kind==='search_card'&&(scope?.scene_id!==run.scene_id||scope?.run_id!==run.run_id))||response.resolved_time?.clock_mapping_sha256!==run.clock_mapping.content_sha256)return null;
    let result;
    const locationFrame=kind==='search_card'&&targetObserved===false&&response.hits?.some(h=>h.camera_id===cameraId&&h.target_observed===false);
    if(locationFrame){
      const stamp=response.resolved_time?.source_range_us?.[0];
      if(!Number.isSafeInteger(stamp)||stamp<0)return null;
      result=await api.frames(run,stamp,[cameraId]);
    }else if(kind==='search_card'){
      if(typeof mediaToken!=='string'||!mediaToken||!response.hits?.some(h=>h.camera_id===cameraId&&h.segments?.some(s=>s.representative?.media_token===mediaToken)))return null;
      result=await api.mediaGrant(mediaToken);
    }else{
      if(!['ON_CAMERA','CANDIDATE'].includes(segmentKind)||!Number.isSafeInteger(currentTUs)||currentTUs<0||currentTUs>=response.as_of_us)return null;
      result=await api.frames(run,currentTUs,[cameraId]);
    }
    const now=store.getState();
    if(now.activeRun!==run||(kind==='search_card'?now.coreSearchResponse:now.coreTrackResponse)!==response||!result?.ok)return null;
    const data=result.data,tile=data?.tiles?.[0];
    if(data?.schema_version!=='controlled-scene.synced-frames.v1'||data.resolved_scope?.scene_id!==run.scene_id||data.resolved_scope?.run_id!==run.run_id||data.clock_id!==run.clock_id||(run.source_kind&&data.data_origin!==run.source_kind)||data.provenance?.['g'+'t_read']!==false||data.identity_verdict!=='UNCONFIRMED'||data.tiles?.length!==1||tile?.camera_id!==cameraId||tile.status!=='READY'||!MEDIA_URL.test(tile.media_url??''))return null;
    if(!Number.isSafeInteger(data.t_us)||data.t_us<0)return null;
    if(kind==='tracking_frame'&&data.t_us!==currentTUs)return null;
    if(kind==='search_card'&&!locationFrame&&!response.hits.some(h=>h.camera_id===cameraId&&h.segments?.some(s=>s.representative?.media_token===mediaToken&&s.range_us?.[0]<=data.t_us&&data.t_us<s.range_us?.[1])))return null;
    if(locationFrame&&data.t_us!==response.resolved_time.source_range_us[0])return null;
    return tile.media_url;
  };
}
