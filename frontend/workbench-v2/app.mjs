// Composition root: the only file that imports several views (design §6.1). V2-9 wires the real views.
import { createStore, initialState } from './store.mjs';
import { createPlayer } from './clock.mjs';
import { loadRailPref, mountShell } from './shell-view.mjs';
import { mount as mountGrid } from './grid-view.mjs';
import { mount as mountPlan } from './plan-view.mjs';
import { mount as mountTimeline } from './timeline-view.mjs';
import { mount as mountInspector } from './inspector.mjs';
import { mount as mountQuery } from './query.mjs';
import { mount as mountDemo } from './demo.mjs';

// Placeholder run so the shell is usable before V2-2 adds api.mjs; replaced by the bootstrap payload later.
const SHELL_PREVIEW_RUN = Object.freeze({ run_id: 'SHELL_PREVIEW', fps: 5, duration_s: 20 });

export function bootstrap(root = document) {
  const store = createStore(initialState({ rail: loadRailPref() }));
  const shell = mountShell(root, store);
  const ctx = { store, slots: shell.slots, shell };
  for (const mount of [mountGrid, mountPlan, mountTimeline, mountInspector, mountQuery, mountDemo]) mount(ctx);

  const player = createPlayer({ getState: store.getState, dispatch: store.dispatch });
  store.subscribe(() => player.sync());

  store.dispatch({ type: 'SET_RUN', run: SHELL_PREVIEW_RUN });
  shell.setSynthetic('外框預覽：尚未連接資料來源，畫面內容是空殼。所有數字都是示意。');
  return { store, shell };
}

if (typeof document !== 'undefined') bootstrap();
