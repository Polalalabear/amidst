// Workbench Core Screens View Module: W-A5
// Integrates Search Results Wall and Tracking Single/Multi-view with Topdown Panel.

import { mountCoreSearchWallView } from './core-search-wall-view.mjs';
import { mountCoreTrackingView } from './core-tracking-view.mjs';

export { mountCoreSearchWallView, mountCoreTrackingView };

export function mountCoreScreens({
  wallSlot = null,
  trackSlot = null,
  store,
  api = null,
  playback = null,
  mediaResolver = null,
} = {}) {
  const views = [];

  if (wallSlot) {
    views.push(mountCoreSearchWallView({
      container: wallSlot,
      store,
      api,
      mediaResolver,
      onSelectCard: (card) => {
        if (store?.dispatch) {
          store.dispatch({
            type: 'SET_CORE_SELECTION',
            selection: { rank: card.rank, cameraId: card.cameraId },
          });
        }
      },
    }));
  }

  if (trackSlot) {
    views.push(mountCoreTrackingView({
      container: trackSlot,
      store,
      api,
      mediaResolver,
      onModeChange: (mode) => {
        if (store?.dispatch) {
          store.dispatch({ type: 'SET_PLAYBACK_MODE', value: mode });
        }
      },
      onSpeedChange: (speed) => {
        if (store?.dispatch) {
          store.dispatch({ type: 'SET_SPEED', speed });
        }
      },
    }));
  }

  return {
    views,
    destroy() {
      for (const v of views) {
        v.destroy?.();
      }
    },
  };
}
