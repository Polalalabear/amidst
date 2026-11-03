# D112-3：UI-05 P1 live 未切到 B 的原因

固定 #385＋#388 組合的主要阻擋是 **scope authority 限制**。P1 的 B 鏡頭確有觀測；現行 scope 未核准，候選守門按既有規則排除 A→B。這份診斷不把 UI-05 改判 PASS，也沒有修正／放寬候選規則。

## 固定輸入與結果

完整來源 pins 與 curated 結果見 [audit JSON](UI05_P1_SCOPE_AUDIT_20261102.json)。產品程式、scope 與參數維持 #388 原審查 head `c6eef184955c0ea83c7c3d81d93268b7eaef27db` 的 bytes。

- P1 v4 MANIFEST SHA-256：`6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`；來源程式 commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`。
- scope bytes SHA-256：`e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8`；`status=PROPOSED`、`G4_approved=false`；有效圖狀態為 `DRAFT`。
- 查詢：RULE_ONLY、person／red／STRONG、整段 8,000,000 us；選 A 的 `obs:22f855debd033dee:A:2:0`，來源時間 100,000 us。
- 凍結索引：A 有 38 個 person 偵測；B 有 51 個 person 偵測，其中 5 個在 query score floor 以上且 red=STRONG。這些是偵測輸出，不是人物真值或身分確認。
- 8 份候選快照全部是 0 候選，全部把 `T_A_B` 列入 `excluded_transitions`，理由 `GRAPH_NOT_APPROVED`。
- 8 個執行動作全為 `RETURN_TO_ORIGIN`（3,050,000～5,850,000 us），沒有 SWITCH。回應為 `ENDED_BY_LIMIT`／`SESSION_RESEARCH_ROUND_LIMIT`；ON_CAMERA 只含 A。

## 規則路徑

[`GraphBundle.approval_status`](https://github.com/Polalalabear/amidst/blob/c6eef184955c0ea83c7c3d81d93268b7eaef27db/src/amidst/q1q5/graphs.py#L149) 同時要求兩圖核准與 scope 的 APPROVED／G4_approved=true，否則回 DRAFT。

[`transition_candidates`](https://github.com/Polalalabear/amidst/blob/c6eef184955c0ea83c7c3d81d93268b7eaef27db/src/amidst/q1q5/candidates.py#L62) 對已提供而未核准的 scope，會先把轉移排除為 GRAPH_NOT_APPROVED，再進候選生成。這個檢查早於 B 的 Q4 證據查詢；有 B 觀測也不能越過 authority gate。此處與前端 session binding／bootstrap 的修正不同，原 binding 修正仍有效。

沒有把 scope 改為核准、設 G4_approved=true、移除 scope、放寬參數或改排序。r004 的 G4 核准也不能自動套到這份不同 hashes 的 P1 工程 scope。

Claude 記錄的「約 3.4 s」未附 seed ID，因此該次操作的逐格同一性仍 UNKNOWN。本次記錄明確使用 0.1 s 的合法 A 起點；無論起點造成何種缺口，這份 scope 對 T_A_B 的排除條件都相同。沒有據此重寫 Claude 的瀏覽器驗收。

## 重現

`P1_BUNDLE` 指上述固定 LOCAL P1 v4；兩個輸出路徑都必須是新的 repo 外 canonical 路徑。

```sh
uv run python scripts/audit_p1_live_scope.py \
  --bundle "$P1_BUNDLE" \
  --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 \
  --state-root "$NEW_STATE" --output "$NEW_AUDIT_JSON"
AMIDST_REQUIRE_IMPL=1 AMIDST_P1_BUNDLE="$P1_BUNDLE" \
  uv run python -m pytest -q tests/q1q5/test_p1_live_tracking.py tests/q1q5/test_demo_live_tracking_t.py
```

重跑只讀既有 safe bundle／凍結偵測索引；不開 HTTP server、不跑模型、不渲染，不讀 GT／劇本／renderer 軌跡或 depth。新增回歸檢查同時要求「B 有合法起點觀測」與「未核准 scope 的 T_A_B 仍被排除」，不修改 #387 的 -T。

UI-05 的 live 跨鏡頭要求仍為 FAIL。既有 pinned P1 錄製可供 RECORDED fallback 展示；它保持自己的來源／hash，不能冒稱本次 live 請求已切鏡。若要讓這份 live scope 開放 A→B，須由權威擁有者定案適用的核准方式，不能由本診斷升權。
