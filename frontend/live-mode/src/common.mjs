export const CHANNEL = 'amidst-live-mode';
export function params() {
  const q = new URLSearchParams(location.search);
  const num = (k, d) => (q.has(k) ? Number(q.get(k)) : d);
  return {
    w: num('w', 320), h: num('h', 180), fps: num('fps', 5),
    cams: q.has('cams') ? q.get('cams').split(',') : null,
    model: q.get('model') || 'capsule', // capsule | glb (N6 character.glb)
    scene: q.get('scene') || 'n6',      // n6 (baked scene.glb) | spike (extruded walls)
    auto: q.get('auto'),                // B4 | A4 : scripted target walk (measurement only)
    duration: num('duration', 60), run: q.get('run') || 'B4-1-v2-4actor',
    sentence: q.get('sentence') || 'a person in a red top', quality: num('q', 0.85),
  };
}
export const now = () => performance.timeOrigin + performance.now(); // epoch ms, shared by both windows
