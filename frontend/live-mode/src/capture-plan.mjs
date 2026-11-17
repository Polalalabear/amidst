// Only backend camera ids may guide capture; this API has no operator/world/GT argument.
export function chooseCaptureIds(available, schedule) {
  const wanted = new Set((schedule?.next_camera_ids || []).filter(id => typeof id === 'string'));
  const ids = available.filter(id => wanted.has(id));
  return ids.length ? ids : [...available]; // stale/invalid plan is a full capture, not no evidence
}
