import * as THREE from 'three';
export { chooseCaptureIds } from './capture-plan.mjs';

// Offscreen renderer that turns each virtual camera into a JPEG at a chosen size.
export function makeCapture(world, cams, w, h, quality) {
  const canvas = new OffscreenCanvas(w, h);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, preserveDrawingBuffer: false });
  renderer.setSize(w, h, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const rt = new THREE.WebGLRenderTarget(w, h, { samples: 4, colorSpace: THREE.SRGBColorSpace });
  const buf = new Uint8Array(w * h * 4);
  const out = new OffscreenCanvas(w, h);
  const ctx = out.getContext('2d');
  const img = ctx.createImageData(w, h);
  return {
    renderer,
    async shoot(camId) {
      const c = cams[camId];
      renderer.setRenderTarget(rt);
      renderer.render(world.scene, c.camera);
      renderer.readRenderTargetPixels(rt, 0, 0, w, h, buf);
      renderer.setRenderTarget(null);
      for (let y = 0; y < h; y++) img.data.set(buf.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
      ctx.putImageData(img, 0, 0);
      const blob = await out.convertToBlob({ type: 'image/jpeg', quality });
      return blob.arrayBuffer();
    },
  };
}

export function packInfer(header, jpegs) {
  const hb = new TextEncoder().encode(JSON.stringify(header));
  const total = 4 + hb.length + jpegs.reduce((s, j) => s + j.byteLength, 0);
  const body = new Uint8Array(total);
  new DataView(body.buffer).setUint32(0, hb.length, true);
  body.set(hb, 4);
  let off = 4 + hb.length;
  for (const j of jpegs) { body.set(new Uint8Array(j), off); off += j.byteLength; }
  return body;
}
