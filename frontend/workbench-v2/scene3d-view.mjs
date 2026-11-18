// three.js 3D scene view for the recorded-mode topdown panel (#605). Renders ONLY what scene3d-model gives
// (system outputs); the recorded videos are not re-rendered. three.js and the assets are loaded lazily from the
// local static service (/scene3d/...); missing assets reject with SCENE3D_ASSETS_MISSING and the caller stays on 2D.
export const SCENE3D_BASE = '/scene3d';
export const SCENE3D_ASSETS_MISSING = 'SCENE3D_ASSETS_MISSING';

const C = { active: 0x50fa7b, idle: 0x8fa2e8, blind: 0xffb86c, est: 0xffb86c };
let shared = null; // scene.glb is 34 MB: load once per page

async function loadAssets(base, fetchImpl) {
  if (shared) return shared;
  shared = (async () => {
    const res = await fetchImpl(`${base}/cameras.three.json`);
    if (!res.ok) throw new Error(SCENE3D_ASSETS_MISSING);
    const cameraAsset = await res.json();
    const THREE = await import(`${base}/three/build/three.module.js`);
    const { GLTFLoader } = await import(`${base}/three/examples/jsm/loaders/GLTFLoader.js`);
    const { OrbitControls } = await import(`${base}/three/examples/jsm/controls/OrbitControls.js`);
    const gltf = await new GLTFLoader().loadAsync(`${base}/scene.glb`);
    return { THREE, OrbitControls, gltf, cameraAsset };
  })().catch(e => { shared = null; throw e.message === SCENE3D_ASSETS_MISSING ? e : Object.assign(new Error(SCENE3D_ASSETS_MISSING), { cause: e }); });
  return shared;
}

export function mountScene3dView({ host, base = SCENE3D_BASE, fetchImpl = (...a) => fetch(...a), width = 760, height = 420 } = {}) {
  if (!host) throw new Error('HOST_REQUIRED');
  let ctx = null, destroyed = false, dyn = null, latest = null, renderer = null, camera = null, controls = null, scene = null;
  const labelLayer = document.createElement('div'); labelLayer.className = 'q-scene3d-labels';
  const canvas = document.createElement('canvas'); canvas.className = 'q-scene3d-canvas';
  host.append(canvas, labelLayer);
  const labels = [];

  const ground = (xy, h = 0) => new ctx.THREE.Vector3(xy[0], h, -xy[1]);
  function clearDynamic() {
    if (dyn) { scene.remove(dyn); dyn.traverse(o => { o.geometry?.dispose?.(); o.material?.dispose?.(); }); }
    dyn = new ctx.THREE.Group(); scene.add(dyn); labels.length = 0; labelLayer.replaceChildren();
  }
  function label(text, v, cls = '') {
    const d = document.createElement('div'); d.className = `q-scene3d-label ${cls}`; d.textContent = text; labelLayer.append(d); labels.push([d, v]);
  }
  function draw() {
    if (!ctx || destroyed || !latest) return;
    const { THREE } = ctx, m = latest;
    clearDynamic();
    for (const c of m.cameras) {
      const mx = new THREE.Matrix4().set(...c.cameraToWorld), pos = new THREE.Vector3().setFromMatrixPosition(mx);
      const color = c.isActive ? C.active : c.isGapLast ? C.blind : C.idle;
      const strong = c.isActive || c.isGapLast;
      const L = 5.5, hh = Math.tan(c.fovYRad / 2) * L, hw = hh * c.aspect;
      const far = [[hw, hh], [-hw, hh], [-hw, -hh], [hw, -hh]].map(([x, y]) => new THREE.Vector3(x, y, -L).applyMatrix4(mx));
      const tri = [], push = (...v) => v.forEach(p => tri.push(p.x, p.y, p.z));
      for (let i = 0; i < 4; i++) push(pos, far[i], far[(i + 1) % 4]);
      push(far[0], far[1], far[2], far[0], far[2], far[3]);
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(tri, 3));
      dyn.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: strong ? 0.28 : 0.06, side: THREE.DoubleSide, depthWrite: false })));
      const edges = []; for (let i = 0; i < 4; i++) edges.push(pos, far[i], far[i], far[(i + 1) % 4]);
      dyn.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(edges), new THREE.LineBasicMaterial({ color, transparent: true, opacity: strong ? 1 : 0.4 })));
      const body = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.35, 0.35), new THREE.MeshBasicMaterial({ color }));
      body.position.copy(pos); body.quaternion.setFromRotationMatrix(mx); dyn.add(body);
      label(c.id.replace('CAM_', ''), pos.clone().add(new THREE.Vector3(0, 0.7, 0)), c.isActive ? 'on' : c.isGapLast ? 'blind' : '');
    }
    const blind = m.segmentKind === 'GAP' || m.segmentKind === 'LOST';
    const ring = (xy, r0, r1, color, h) => {
      const mesh = new THREE.Mesh(new THREE.RingGeometry(r0, r1, 48), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
      mesh.rotation.x = -Math.PI / 2; mesh.position.copy(ground(xy, h)); dyn.add(mesh);
    };
    if (m.switchMarker) {
      ring(m.switchMarker.groundXy, 0.9, 1.05, C.active, 0.08);
      label(`切鏡 ${m.switchMarker.from?.replace('CAM_', '') ?? '盲區'} → ${m.switchMarker.to.replace('CAM_', '')} @${(m.switchMarker.tUs / 1e6).toFixed(1)}s`, ground(m.switchMarker.groundXy, 3), 'on');
    }
    const est = m.estimate, col = blind ? C.blind : C.active;
    if (est.status === 'INFERRED') {
      if (est.trail.length > 1) {
        const curve = new THREE.CatmullRomCurve3(est.trail.map(p => ground(p, 0.06)));
        dyn.add(new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(8, est.trail.length * 4), 0.07, 6), new THREE.MeshBasicMaterial({ color: C.active })));
      }
      if (Number.isFinite(est.uncertaintyM)) {
        let shape;
        if (est.uncertaintyFan.length > 2) {
          const sh = new THREE.Shape(est.uncertaintyFan.map(p => new THREE.Vector2(p[0] - est.xy[0], p[1] - est.xy[1])));
          shape = new THREE.ShapeGeometry(sh);
        } else shape = new THREE.CircleGeometry(est.uncertaintyM, 48);
        const disc = new THREE.Mesh(shape, new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.28, side: THREE.DoubleSide, depthWrite: false }));
        disc.rotation.x = -Math.PI / 2; disc.position.copy(ground(est.xy, 0.05)); dyn.add(disc);
        if (!est.clipped) ring(est.xy, est.uncertaintyM * 0.97, est.uncertaintyM, col, 0.06);
      }
      const hm = new THREE.MeshBasicMaterial({ color: C.est, transparent: true, opacity: 0.55 });
      const man = new THREE.Group();
      const bd = new THREE.Mesh(new THREE.CapsuleGeometry(0.22, 0.9, 4, 10), hm); bd.position.y = 0.8;
      const hd = new THREE.Mesh(new THREE.SphereGeometry(0.17, 12, 10), hm); hd.position.y = 1.62;
      man.add(bd, hd); man.position.copy(ground(est.xy)); dyn.add(man);
      label(blind ? '系統估計（盲區，推論）' : '系統估計（推論）', ground(est.xy, 2), '');
    }
    resize(); render();
  }
  function render() {
    if (!ctx || destroyed) return;
    renderer.render(scene, camera);
    const w = canvas.clientWidth || width, h = canvas.clientHeight || height;
    for (const [d, v] of labels) {
      const p = v.clone().project(camera), vis = p.z < 1;
      d.style.display = vis ? '' : 'none';
      d.style.left = `${(p.x * 0.5 + 0.5) * w}px`; d.style.top = `${(-p.y * 0.5 + 0.5) * h}px`;
    }
  }
  function resize() {
    if (!ctx) return;
    const w = host.clientWidth || width, h = Math.round(w * height / width);
    renderer.setSize(w, h, false); canvas.style.height = `${h}px`; camera.aspect = w / h; camera.updateProjectionMatrix();
  }

  const ready = loadAssets(base, fetchImpl).then(a => {
    if (destroyed) return a;
    ctx = a; const { THREE } = a;
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.localClippingEnabled = true;
    scene = new THREE.Scene(); scene.background = new THREE.Color(0x1b2130);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 1.8));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(5, 20, 8); scene.add(sun);
    const clip = new THREE.Plane(new THREE.Vector3(0, -1, 0), 2.6); // hide the roof (y > 2.6 m)
    const room = a.gltf.scene.clone(true);
    room.traverse(o => { if (o.isMesh) (Array.isArray(o.material) ? o.material : [o.material]).forEach(mt => { mt.clippingPlanes = [clip]; }); });
    scene.add(room);
    camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 300); camera.position.set(-4, 30, 26); camera.lookAt(1, 0, -1.5);
    controls = new a.OrbitControls(camera, canvas); controls.target.set(1, 0, -1.5); controls.addEventListener('change', render); controls.update();
    resize(); draw();
    return a;
  });

  return {
    ready,
    cameraAsset: () => ctx?.cameraAsset ?? null,
    update(model) { latest = model; draw(); },
    destroy() { destroyed = true; controls?.dispose(); renderer?.dispose(); canvas.remove(); labelLayer.remove(); },
  };
}
