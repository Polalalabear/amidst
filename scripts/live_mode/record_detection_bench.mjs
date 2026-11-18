// Evaluation-only RGB recording. Labels are saved separately and never sent to /detect.
// LIVE_BASE=http://127.0.0.1:8797 node scripts/live_mode/record_detection_bench.mjs <output>
import fs from 'node:fs';
import path from 'node:path';
import { launch, BASE } from '../../frontend/live-mode/measure/lib.mjs';
const out = process.argv[2];
if (!out) throw new Error('output directory required');
fs.mkdirSync(path.join(out, 'rgb'), { recursive: true });
const browser = await launch();
try {
  const page = await browser.newPage();
  await page.exposeFunction('saveRGB', (id, base64) => {
    fs.writeFileSync(path.join(out, 'rgb', `${id}.jpg`), Buffer.from(base64, 'base64'));
  });
  await page.goto(`${BASE}/?role=sweep&model=glb&scene=n6&w=320&h=180`);
  await page.waitForFunction('window.__ready === true', { timeout: 60000 });
  const labels = await page.evaluate(async () => {
    const { setupWorld } = await import('/src/setup.mjs');
    const { groundTruthVisible } = await import('/src/world.mjs');
    const { blocked } = await import('/src/sim.mjs');
    const { makePerson, projectBox } = await import('/src/person.mjs');
    const { makeCapture } = await import('/src/capture.mjs');
    const P = { model: 'glb', scene: 'n6', w: 320, h: 180 };
    const { geometry, world, cams, n6 } = await setupWorld(P);
    if (!n6) throw new Error('N6 assets required');
    const person = await makePerson('glb', world, 'red');
    person.update(0.5);
    const caps = [makeCapture(world, cams, 320, 180, 0.85), makeCapture(world, cams, 640, 360, 0.85)];
    const rows = [];
    const save = async (cap, cam, id) => {
      const bytes = new Uint8Array(await cap.shoot(cam));
      let s = ''; for (const b of bytes) s += String.fromCharCode(b);
      await window.saveRGB(id, btoa(s));
    };
    let tick = 0;
    for (const f of geometry.floors) {
      for (let x = f.x_m[0] + 0.5; x < f.x_m[1]; x++) for (let y = f.y_m[0] + 0.5; y < f.y_m[1]; y++) {
        if (blocked(x, y, world.segments, 0.3)) continue;
        for (const heading of [0, 90, 180, 270]) {
          tick++; person.setPose(x, y, heading * Math.PI / 180); world.scene.updateMatrixWorld(true);
          for (const cam of groundTruthVisible(cams, world.blockers, world.root, x, y)) {
            const gt = projectBox(cams[cam].camera, world.root, x, y, 320, 180);
            if (!gt) continue;
            const clip = [Math.max(0, gt[0]), Math.max(0, gt[1]), Math.min(320, gt[2]), Math.min(180, gt[3])];
            const full = (gt[2]-gt[0])*(gt[3]-gt[1]);
            const inside = Math.max(0,clip[2]-clip[0])*Math.max(0,clip[3]-clip[1])/full;
            const id = `${String(tick).padStart(4,'0')}_${cam}`;
            await save(caps[0], cam, id);
            if (['CAM_ENTRY','CAM_R101_IN','CAM_EXT_CAR'].includes(cam)) await save(caps[1],cam,`${id}_640`);
            rows.push({ id, cam, tick, x, y, heading, bbox: clip, inside, gt_h_px: clip[3]-clip[1],
              eligible: Number(inside.toFixed(2)) >= 0.6 && Number((clip[3]-clip[1]).toFixed(1)) >= 16 });
          }
        }
      }
    }
    person.setVisible(false); world.scene.updateMatrixWorld(true);
    for (const cam of Object.keys(cams)) await save(caps[0], cam, `empty_${cam}`);
    return rows;
  });
  fs.writeFileSync(path.join(out, 'evaluation_labels.json'), JSON.stringify(labels));
  console.log(JSON.stringify({ frames: labels.length, eligible: labels.filter(x=>x.eligible).length }));
} finally { await browser.close(); }
