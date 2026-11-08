// D139-3: display-only scale of camera images. fit = whole frame, no crop (default) · fill = fill the box, edges may be cropped ·
// orig = native pixels, centred. Only chooses a CSS object-fit; no data, no request, no inference input changes.
export const FIT_MODES = Object.freeze([
  Object.freeze({ id: 'fit', label: '符合', hint: '整張畫面放進框內，不裁切' }),
  Object.freeze({ id: 'fill', label: '填滿', hint: '填滿整個框，邊緣可能被裁切' }),
  Object.freeze({ id: 'orig', label: '原始', hint: '原始像素大小，置中' }),
]);
export const DEFAULT_FIT = 'fit';
export const FIT_STORAGE_KEY = 'amidst.ui.media-fit.v1';
export const normalizeFit = v => (FIT_MODES.some(m => m.id === v) ? v : DEFAULT_FIT);
