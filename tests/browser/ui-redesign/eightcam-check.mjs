// The D269 real gate can require this check once #576 starts the 8CAM source.
export async function checkEightCamWall(page, base, check, {required = false, label = 'A4-1'} = {}) {
  const response = await page.request.get(new URL('/api/q_bootstrap', base).href);
  check(response.ok(), '8CAM bootstrap request succeeds');
  const boot = await response.json();
  const eightcam = boot.eightcam;
  if (eightcam?.status !== 'READY') {
    if (required) check(false, `8CAM required: ${eightcam?.reason ?? 'UNKNOWN'}`);
    return null;
  }

  const source = boot.eightcam_runs?.find(row => row.label === label + '-8CAM');
  const id = source?.run_id || (label === 'A4-1' ? eightcam.run_id : null);
  const run = boot.runs.find(row => row.run_id === id);
  check(run?.title.startsWith(label + '-8CAM ·') && run.camera_ids.length === 8,
    'exact ' + label + '-8CAM bootstrap source has eight cameras');
  await page.goto(new URL('?run=A4-1&screen=case3', base).href);
  const tab = page.locator(`#ui-events button[data-event="${run.run_id}"]`);
  check((await tab.innerText()).includes(label + '-8CAM'), '8CAM is named in the recorded run menu');
  await tab.click();
  await page.waitForURL(url => url.searchParams.get('run') === run.run_id);
  const ready = '.mr-tile[data-status="READY"] img';
  await page.waitForFunction(selector => {
    const images = [...document.querySelectorAll(selector)];
    return images.length === 8 && images.every(img => img.complete && img.naturalWidth > 0);
  }, ready);
  check(true, 'eight pinned RGB tiles are decoded in the real workbench');

  // The transport polls the decoded wall clock before enabling its seek range.
  const duration = label === 'B4-1' ? 42_000_000 : 50_000_000;
  await page.waitForFunction(max => Number(document.querySelector('#ui-wall-scrub')?.max) === max,
    duration - 1);
  await page.locator('#ui-wall-scrub').evaluate(input => {
    input.value = '1000000';
    input.dispatchEvent(new Event('input', {bubbles: true}));
  });
  await page.waitForFunction(selector => {
    const images = [...document.querySelectorAll(selector)];
    return images.length === 8 && images.every(img =>
      img.dataset.sourceUs === '1000000' && img.complete && img.naturalWidth > 0);
  }, ready);
  check(true, 'eight decoded frames advance to 1.0 seconds');
  return {run_id: run.run_id, camera_ids: run.camera_ids, source_us: 1_000_000};
}
