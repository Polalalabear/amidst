# D133 Mac playback format and switch latency measurements

Engineering only. No integration merge, model run, source write or formal acceptance.

## Storage (bytes)

Original PNG: 1,253,126,920; safe public PNG stream: 1,252,961,310; JPEG90: 110,611,318; WebP90: 61,637,852.

## Playback: complete 27-case matrix

Same clean #408 event-viewer; all source cameras shown. Mac Chrome **headless**. Native values are image ElementTiming render events, not physical screen Hz. Each case ran its full source duration once; no between-run confidence interval.

| Case | Format | Setting | Native fps/camera mean | Decoded-visible fps/camera mean | Actual source speed | decode() wait P90 ms |
|---|---|---:|---:|---:|---:|---:|
|B-05b|png|1x|19.945|19.972|0.999x|12.900|
|B-05b|jpeg|1x|19.913|19.943|0.997x|5.200|
|B-05b|webp|1x|20.011|20.026|1.001x|6.700|
|B-05b|jpeg|1.5x|24.709|24.743|1.237x|4.700|
|B-05b|webp|1.5x|24.780|24.797|1.240x|6.100|
|B-05b|png|1.5x|24.566|24.607|1.230x|11.600|
|B-05b|webp|2x|24.741|24.764|1.238x|6.600|
|B-05b|png|2x|24.720|24.744|1.237x|11.600|
|B-05b|jpeg|2x|24.853|24.871|1.244x|4.600|
|A4-1|jpeg|1x|5.011|5.012|1.002x|9.900|
|A4-1|webp|1x|5.012|5.013|1.003x|25.400|
|A4-1|png|1x|5.013|5.015|1.003x|19.900|
|A4-1|webp|1.5x|7.514|7.518|1.504x|24.800|
|A4-1|png|1.5x|7.510|7.514|1.503x|24.600|
|A4-1|jpeg|1.5x|7.516|7.519|1.504x|11.700|
|A4-1|png|2x|10.005|10.012|2.002x|25.200|
|A4-1|jpeg|2x|10.016|10.021|2.004x|12.000|
|A4-1|webp|2x|10.006|10.012|2.002x|21.900|
|B4-1|webp|1x|5.013|5.016|1.003x|20.600|
|B4-1|png|1x|5.017|5.020|1.004x|21.900|
|B4-1|jpeg|1x|5.014|5.015|1.003x|12.900|
|B4-1|png|1.5x|7.513|7.519|1.504x|28.600|
|B4-1|jpeg|1.5x|7.519|7.521|1.504x|12.700|
|B4-1|webp|1.5x|7.517|7.522|1.504x|20.900|
|B4-1|jpeg|2x|10.009|10.013|2.003x|11.500|
|B4-1|webp|2x|10.003|10.009|2.002x|21.600|
|B4-1|png|2x|10.017|10.023|2.005x|21.800|

decode() promise wait may include pending loading; it is not isolated decoder CPU time. The 27-case raw receipt used the default ResourceTiming buffer, so its http_* fields cover only first buffered entries, not total transfer bytes. FPS/native image events are independent. Later script increases that buffer; this report does not relabel old executions.

Every original PNG retained its source byte pin. Its unsafe metadata was removed in memory before public PNG/codec decoding; the manifest preserves original and served hashes separately.

## B-05b recorded workbench: supplementary 9-case matrix

Single active camera in the same clean #408 player. LOCAL adapter preserves authorization and source-pin checks, replaces only served image bytes/hash/content type, and adapts the hard-coded PNG Blob MIME in the served JS response. Source checkout files are unchanged. This is a codec experiment, not product proxy integration.

| Format | Setting | Native fps | Decoded-visible fps | Actual source speed | decode() wait P90 ms |
|---|---:|---:|---:|---:|---:|
|png|1x|19.743|19.786|0.989x|0.800|
|jpeg|1x|19.773|19.819|0.991x|0.900|
|webp|1x|19.771|19.845|0.992x|0.900|
|png|1.5x|29.330|29.511|1.476x|0.800|
|jpeg|1.5x|29.446|29.623|1.481x|0.800|
|webp|1.5x|29.484|29.665|1.483x|0.800|
|png|2x|38.855|39.173|1.959x|0.900|
|jpeg|2x|39.075|39.390|1.969x|0.800|
|webp|2x|39.135|39.478|1.974x|0.800|

The event-viewer advances at most one source frame per 40 ms tick, so its B-05b high-speed ceiling is approximately 25 fps/camera. The single-view workbench uses a separate player and must be assessed from its own table.

## Switch baselines (ms)

| Mode | Profile | Saved n | Ready median / P90 | Native paint n | Native median / P90 |
|---|---|---:|---|---:|---|
|HEADFUL_INTERRUPTED_SESSION|legacy|30|29.250 / 31.100|30|69.850 / 74.200|
|HEADFUL_INTERRUPTED_SESSION|core|11|15.200 / 31.400|0|UNKNOWN|
|HEADLESS_COMPLETE_SESSION|legacy|30|15.400 / 16.800|30|48.500 / 51.400|
|HEADLESS_COMPLETE_SESSION|core|30|15.200 / 15.600|0|UNKNOWN|

HEADFUL session stopped after 30 B-05b and 11 synthetic core trials when the user reported popup disruption. Saved valid samples remain separate; missing repetitions were not filled. Headless complete-session samples are not pooled with those data.

Legacy = B-05b recorded first matched B frame available at replay clock 5.15s → actual B PNG ready/native render. Core = existing 8765 SYNTHETIC schematic state transition, not a real-camera/detector result.

The offline recording begins the new-camera sighting at 5.15s. Earlier unlabelled physical pixel appearance is UNKNOWN. No live model/inference time is included.

## Sources and methods

- Chrome headless uses the installed Mac Google Chrome executable, fresh isolated contexts and disabled HTTP cache. It does not display or focus windows: https://developer.chrome.com/docs/automation-and-testing/headless
- Native image render timestamps: https://w3c.github.io/element-timing/
- decode() is a decoding readiness promise, not physical display measurement: https://html.spec.whatwg.org/multipage/embedded-content.html#dom-img-decode
- Compression/format background: https://developer.chrome.com/docs/performance/insights/image-delivery

All raw samples/screenshots and proxy images stay LOCAL. Source/code/tool/manifest pins are in the receipts; committed JSON contains only engineering measurement summaries.

Recommendation: **WebP90 for LOCAL playback on this Mac** (95.081% smaller than original PNG, 44.275% smaller than JPEG); JPEG has lower decode-promise wait in the all-camera viewer. Measured FPS gains are small, and this is not an image-quality equivalence claim. Sources for charts and all plotted latency samples are in [the curated JSON](d133_playback_latency_20261108.json).
