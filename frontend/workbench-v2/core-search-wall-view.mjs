// DOM View for Search Results Wall (查找結果牆)
// Connects to buildSearchResultsWallModel output. Pure DOM view; no inference inputs.

import {
  buildSearchResultsWallModel,
  CORE_IDENTITY_BADGE,
  CORE_RANKING_NOTE,
} from './core-search-track-model.mjs';
import { resolveCardImageSrc } from './core-media.mjs';

const el = (tag, text, cls) => {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (cls) node.className = cls;
  return node;
};

export function mountCoreSearchWallView({
  container,
  store = null,
  onSelectCard = null,
  onAction = null,
  api = null,
  mediaResolver = null,
} = {}) {
  if (!container) throw new Error('CONTAINER_REQUIRED');

  let currentModel = null;
  let currentPage = 0;
  let destroyed = false;

  function render(model) {
    if (destroyed) return;
    currentModel = model;
    container.replaceChildren();

    const root = el('div', undefined, 'q-core-wall');
    root.setAttribute('role', 'region');
    root.setAttribute('aria-label', '查找結果牆');

    // Header
    const head = el('div', undefined, 'q-core-wall-head');
    const titleGroup = el('div', undefined, 'q-core-title-group');
    const title = el('h2', '查找結果牆', 'q-core-title');
    const badge = el('span', model?.identityBadge ?? CORE_IDENTITY_BADGE, 'q-core-identity-badge');
    titleGroup.append(title, badge);

    const rankingNote = el('p', model?.rankingNote ?? CORE_RANKING_NOTE, 'q-core-ranking-note');
    titleGroup.append(rankingNote);
    head.append(titleGroup);

    const countText = model?.hasResults
      ? `命中鏡頭 ${model.totalHits} · 第 ${model.page + 1} / ${model.pages} 頁`
      : model?.statusText ?? '尚未載入查找結果。';
    const statusEl = el('span', countText, 'q-core-wall-status');
    head.append(statusEl);
    root.append(head);

    // Cards Grid or Empty State
    if (!model?.hasResults || model.cards.length === 0) {
      const emptyBox = el('div', undefined, 'q-core-wall-empty');
      const msg = el('p', model?.statusText ?? '尚未載入查找結果。', 'q-core-empty-message');
      emptyBox.append(msg);
      root.append(emptyBox);
    } else {
      const grid = el('div', undefined, 'q-core-cards-grid');
      for (const card of model.cards) {
        const cardEl = el('article', undefined, 'q-core-card');
        cardEl.dataset.cameraId = card.cameraId;
        cardEl.dataset.rank = String(card.rank);
        cardEl.dataset.selected = String(Boolean(card.isSelected));
        cardEl.dataset.observed = String(Boolean(card.targetObserved));

        // Card Header
        const cardHead = el('div', undefined, 'q-core-card-header');
        const cardTitle = el('h3', `#${card.rank} ${card.cameraId}`, 'q-core-card-title');
        const obsBadge = el('span', card.observedBadge, 'q-core-observed-badge');
        cardHead.append(cardTitle, obsBadge);
        cardEl.append(cardHead);

        // Media Frame (renders actual <img> element with synthetic data URI / media token)
        const media = el('div', undefined, 'q-core-card-media');
        media.dataset.frameRef = card.frameRef ?? '';
        media.dataset.mediaToken = card.mediaToken ?? '';
        media.dataset.cameraId = card.cameraId ?? '';

        const img = el('img', undefined, 'q-core-thumb-img');
        img.alt = `${card.cameraId} 代表畫面 (${card.targetObserved ? 'OBSERVED' : 'STATIC'})`;
        img.dataset.mediaToken = card.mediaToken ?? '';
        img.dataset.frameRef = card.frameRef ?? '';
        img.dataset.cameraId = card.cameraId ?? '';

        const initialSrc = resolveCardImageSrc({
          card,
          mediaResolver,
          api,
          onResolved: (url) => {
            if (!destroyed && url) img.src = url;
          },
        });
        img.src = initialSrc;
        media.append(img);

        const thumbCaption = el(
          'div',
          card.mediaToken ? `token: ${card.mediaToken}` : (card.targetObserved ? '代表畫面待載入' : '場景設定涵蓋（靜態）'),
          'q-core-thumb-caption'
        );
        media.append(thumbCaption);
        cardEl.append(media);

        // Card Info
        const info = el('div', undefined, 'q-core-card-info');
        const wallRange = el('div', `時間窗: ${card.wallRangeText}`, 'q-core-wall-range');
        const frames = el('div', `相符影格: ${card.matchedFrames}`, 'q-core-matched-frames');
        const region = el('div', `地點: ${card.regionName ?? card.regionId ?? '未知區域'}`, 'q-core-region-info');
        info.append(wallRange, frames, region);

        // Basis Badges
        if (card.basisBadges && card.basisBadges.length > 0) {
          const basisList = el('div', undefined, 'q-core-basis-badges');
          for (const b of card.basisBadges) {
            basisList.append(el('span', b, 'q-core-basis-badge'));
          }
          info.append(basisList);
        }
        cardEl.append(info);

        // Action / Select Event
        cardEl.addEventListener('click', () => {
          if (onSelectCard) {
            onSelectCard(card);
          } else if (store?.dispatch) {
            store.dispatch({
              type: 'SET_CORE_SELECTION',
              selection: { rank: card.rank, cameraId: card.cameraId },
            });
          }
        });

        grid.append(cardEl);
      }
      root.append(grid);

      // Pagination Controls
      if (model.pages > 1) {
        const pag = el('nav', undefined, 'q-core-pagination');
        pag.setAttribute('aria-label', '查找結果分頁');

        const prevBtn = el('button', '上一頁', 'q-core-btn q-core-page-prev');
        prevBtn.type = 'button';
        prevBtn.disabled = model.page <= 0;
        prevBtn.addEventListener('click', () => {
          if (model.page > 0) {
            currentPage = model.page - 1;
            const updated = buildSearchResultsWallModel(model.rawResponse ?? null, {
              page: currentPage,
              size: model.pageSize,
              paginate: true,
              selectedRank: model.selectedRank,
              selectedCameraId: model.selectedCameraId,
            });
            render(updated);
          }
        });

        const pageInd = el('span', `${model.page + 1} / ${model.pages}`, 'q-core-page-indicator');

        const nextBtn = el('button', '下一頁', 'q-core-btn q-core-page-next');
        nextBtn.type = 'button';
        nextBtn.disabled = model.page >= model.pages - 1;
        nextBtn.addEventListener('click', () => {
          if (model.page < model.pages - 1) {
            currentPage = model.page + 1;
            const updated = buildSearchResultsWallModel(model.rawResponse ?? null, {
              page: currentPage,
              size: model.pageSize,
              paginate: true,
              selectedRank: model.selectedRank,
              selectedCameraId: model.selectedCameraId,
            });
            render(updated);
          }
        });

        pag.append(prevBtn, pageInd, nextBtn);
        root.append(pag);
      }
    }

    // Not Evaluated Section
    if (model?.notEvaluatedCameras && model.notEvaluatedCameras.length > 0) {
      const notEval = el('section', undefined, 'q-core-not-evaluated');
      const notEvalHead = el('h4', `未評估鏡頭 (${model.notEvaluatedCameras.length})`, 'q-core-not-eval-title');
      notEval.append(notEvalHead);
      const list = el('ul', undefined, 'q-core-not-eval-list');
      for (const item of model.notEvaluatedCameras) {
        const li = el('li', `${item.cameraId}: ${item.reasonText}`, 'q-core-not-eval-item');
        list.append(li);
      }
      notEval.append(list);
      root.append(notEval);
    }

    container.append(root);
  }

  // Initial render
  if (store) {
    const s = store.getState();
    const model = s.coreSearchWall ?? (s.coreSearchResponse ? buildSearchResultsWallModel(s.coreSearchResponse) : null);
    render(model);
    const unsub = store.subscribe(() => {
      if (destroyed) return;
      const state = store.getState();
      const nextModel = state.coreSearchWall ?? (state.coreSearchResponse ? buildSearchResultsWallModel(state.coreSearchResponse, {
        selectedRank: state.coreSelection?.rank,
        selectedCameraId: state.coreSelection?.cameraId,
      }) : null);
      render(nextModel);
    });

    return {
      update(m) { render(m); },
      destroy() {
        destroyed = true;
        unsub();
        container.replaceChildren();
      },
    };
  }

  return {
    update(m) { render(m); },
    destroy() {
      destroyed = true;
      container.replaceChildren();
    },
  };
}
