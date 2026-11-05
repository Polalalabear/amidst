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
  const subText = [label, token].filter(Boolean).join(' · ');

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
  api = null,
  onResolved = null,
} = {}) {
  let initialSrc = null;

  if (card?.mediaToken) {
    const tok = String(card.mediaToken);
    if (tok.startsWith('data:') || tok.startsWith('http:') || tok.startsWith('https:') || tok.startsWith('/') || tok.startsWith('blob:')) {
      initialSrc = tok;
    } else {
      initialSrc = createSyntheticFrameDataUri({
        cameraId: card.cameraId,
        label: card.targetObserved ? '代表畫面' : '靜態涵蓋',
        token: tok,
        kind: card.targetObserved ? 'OBSERVED' : 'STATIC',
      });
    }
  } else {
    initialSrc = createSyntheticFrameDataUri({
      cameraId: card?.cameraId ?? 'CAM',
      label: card?.targetObserved ? '代表畫面待載入' : '場景設定涵蓋（靜態）',
      token: card?.frameRef ?? '',
      kind: card?.targetObserved ? 'OBSERVED' : 'STATIC',
    });
  }

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
          if (url && typeof onResolved === 'function') onResolved(url);
        }).catch(() => {});
      } else if (typeof res === 'string' && res) {
        initialSrc = res;
      }
    } catch {}
  } else if (api && card?.mediaToken && typeof api.mediaGrant === 'function') {
    api.mediaGrant(card.mediaToken).then((grant) => {
      const tile = grant?.data?.tiles?.[0];
      if (grant?.ok && tile?.media_url && typeof onResolved === 'function') {
        onResolved(tile.media_url);
      }
    }).catch(() => {});
  }

  return initialSrc;
}

export function resolveFrameImageSrc({
  cameraId,
  currentTUs = 0,
  segmentKind = 'ON_CAMERA',
  lastObservedCameraId = null,
  mediaResolver = null,
  api = null,
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

  let initialSrc = createSyntheticFrameDataUri({
    cameraId: effectiveCam,
    label,
    kind: segmentKind,
  });

  if (typeof mediaResolver === 'function') {
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
          if (url && typeof onResolved === 'function') onResolved(url);
        }).catch(() => {});
      } else if (typeof res === 'string' && res) {
        initialSrc = res;
      }
    } catch {}
  }

  return initialSrc;
}
