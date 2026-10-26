// Evidence-state encoding shared by 2D, 3D, timeline and legend (design §5.3).
// Pure data: no DOM. Colors are CSS custom-property names defined in style.css (dark theme only).

export const EVIDENCE_STATES = Object.freeze([
  {
    code: 'OBS',
    contract_state: 'PROJECTED_OBSERVATION',
    label: '觀測',
    legend: '觀測（單格投影）',
    color_token: '--obs',
    line: { style: 'solid', width_px: 1.5, hollow: false },
    symbol: '├──┤',
  },
  {
    code: 'INC',
    contract_state: 'INFERRED_CONSTRAINED',
    label: '約束區間',
    legend: '推論・約束區間',
    color_token: '--int',
    line: { style: 'solid', width_px: 5, hollow: true },
    symbol: '├══┤',
  },
  {
    code: 'INT',
    contract_state: 'INFERRED_INTERPOLATION',
    label: '推論',
    legend: '推論・內插',
    color_token: '--int',
    line: { style: 'dash-short', dash_px: [3, 3], width_px: 1.5, hollow: false },
    symbol: '┄┄',
  },
  {
    code: 'HYP',
    contract_state: 'INFERRED_HYPOTHESIS',
    label: '假設',
    legend: '假設＋範圍帶',
    color_token: '--hyp',
    line: { style: 'dash-long', dash_px: [10, 6], width_px: 1.5, hollow: false },
    symbol: '╌╌＋帶',
  },
  {
    code: 'MISS',
    contract_state: 'MISSING',
    label: 'MISSING',
    legend: 'MISSING',
    color_token: '--miss',
    line: { style: 'hatch', hollow: false },
    symbol: '╱╱',
  },
  {
    code: 'UNK',
    contract_state: 'UNKNOWN',
    label: 'UNKNOWN',
    legend: 'UNKNOWN',
    color_token: '--unk',
    line: { style: 'dotted', hollow: false },
    symbol: '⋯?',
  },
]);

// Monochrome ink only; never an evidence color (design §5.4).
export const SYNTHETIC = Object.freeze({
  code: 'SYNTHETIC',
  label: 'SYNTHETIC',
  color_token: '--ink',
  line: { style: 'hatch-ink' },
});

// D45: the legend always explains the ± readout.
export const UNCERTAINTY_LEGEND = Object.freeze({
  code: '±m',
  text: '±m 不確定度：區間半長（條件）· m² 切片面積 · 設計估計',
});

export const IDENTITY_LEGEND = '身分 UNCONFIRMED';

export const STATE_CODES = Object.freeze(EVIDENCE_STATES.map((s) => s.code));

export function stateByCode(code) {
  return EVIDENCE_STATES.find((s) => s.code === code) ?? null;
}

export function stateByContractState(contractState) {
  return EVIDENCE_STATES.find((s) => s.contract_state === contractState) ?? null;
}

export function legendItems() {
  return [
    ...EVIDENCE_STATES.map((s) => ({ code: s.code, text: s.legend, symbol: s.symbol, color_token: s.color_token, line: s.line })),
    { code: SYNTHETIC.code, text: SYNTHETIC.label, symbol: '', color_token: SYNTHETIC.color_token, line: SYNTHETIC.line },
    { code: UNCERTAINTY_LEGEND.code, text: UNCERTAINTY_LEGEND.text, symbol: '±', color_token: '--int', line: { style: 'readout' } },
  ];
}

// Q execution states use monochrome ink and symbols.
export { Q_STATES } from './q-tokens.mjs';
