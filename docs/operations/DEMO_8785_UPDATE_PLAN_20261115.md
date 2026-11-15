# 8785 demo 更新計畫（2026-11-15，只差使用者核准 pin）

狀態：準備工作完成。**本文的指令都還沒有執行**：`local/demo-pin.json` 沒改、8785 沒重啟、`~/amidst` 沒切分支也沒改檔。pin 更新、kill、重啟由使用者在終端執行。

## 1. 候選版本

| 項目 | 值 |
| --- | --- |
| 現行 pin | `74b84463cc4f911f363c6358e2f9ada3748fc7bd`（D197，2026-11-10） |
| **建議的新 pin** | `b24d6a26dc3f556f34270055cab45f5c5dd6382b`（main 上 #542 的 merge commit；core-e2e 修正） |
| 實際測試的 tree | `ca6d0687446b5ac586c8570c2476cd0ceb791e24`（本機 merge：`80f36220`＋#542 `0a0b644f`，於 scratchpad clone，沒有推） |
| 一致性 | `git rev-parse b24d6a26^{tree}` 等於上面的 tree（已核對），所以 `b24d6a26` 就是被測的內容 |
| 之後的 main | `4972f0f9`（#543，WP5 pack）。相對 `b24d6a26` 只多 9 個檔案：`src/amidst/agent_eval/*`、`scripts/agent_decision/build_wp5_packs.py`、WP5 notebook／文件、兩個測試。不在 8785 的路徑上，**閘門沒有測它**。要 pin 它就得重跑閘門 |

建議 pin `b24d6a26`，不要 pin `4972f0f9`，因為只有前者的內容跟閘門測的完全相同。

## 2. 閘門結果

測試環境：scratchpad clone（`uv sync --frozen`，owned Python 3.12）、測試伺服器 `127.0.0.1:8795`（沒有用 8785）、資料根 `local/data/demo-owned-v1`。腳本：與上一輪 `local/evidence/demo-update-prep-20261115/gate-out-rerun/` 相同的流程（unit → dependency → http → core-e2e → real-e2e 900／1300）。

| 閘門 | 結果 | 證據（相對 repo，LOCAL） | SHA-256 |
| --- | --- | --- | --- |
| unit | **通過**：node 576／576；pytest 2633 passed、108 skipped、17 deselected（`.github/ci-linux-deselect.txt`） | `local/evidence/demo-update-prep-20261115/gate-20261115-1829/unit.log` | `073faa1d9fb33817e12e806cecd09384c89b8a4f54be120816008cde31bf00ad` |
| dependency | **通過**：`check_demo_dependencies.py --smoke`，4788 entries、2,756,614,124 bytes | `…/gate-20261115-1829/dependency-check.json` | `073e38b9672318839b8c0fada2c220e1ad5a8a0461b4e9c1fa6c7fc054efe4f4` |
| HTTP 200 | **通過**：`http://127.0.0.1:8795/` 回 200 | `…/gate-20261115-1829/RESULT.txt` | `3e76a13dbfbaf35a5fdae8370da60dd61f2a3d9b784db3e8a63ac512f892d76f` |
| core-e2e | **通過**：130 個 check 全過，無 page error（上一輪卡在 check 84／91，已由 #542 修好） | `…/gate-20261115-1829/core-e2e.log` | `9a0feeca360512687cd337129b2f175458b779328105c470c554888cc0c333a5` |
| real-e2e 900 | **通過**：347 checks、61 張截圖、errors／http 空 | `…/gate-20261115-1829/real-e2e-900.log` | `42357c559130836f84ba96931bc0522df356c8311f445b91a2524379a35e9b78` |
| real-e2e 1300 | **通過**：347 checks、61 張截圖、errors／http 空 | `…/gate-20261115-1829/real-e2e-1300.log` | `af7637c622cf9ce387337808209e50cfa2d179901615b85f50d54ccde32087d9` |

`RESULT.txt` 沒有 FAIL 行，符合 `demo_pin.py approve --gate` 的條件。**它 24 小時後過期**（以檔案修改時間算）；過期就得重跑閘門。

## 3. A4-1-8CAM／B4-1-8CAM 為什麼不在 run 清單

查到兩層：

1. **8785 本身沒有這兩個 run，而且不是登錄問題。** `scripts/serve_demo_integration.py` 只載入 B-05、A4-1、B4-1、r005 四個 run（`bootstrap()['runs']`），沒有任何 8CAM 的程式碼。8CAM 只存在於事件檢視器 `frontend/event-viewer/server.mjs`（`--root-8cam`，由 #534 加入）。要讓 8785 的新 UI 列出它們是新功能，不在這次範圍；**沒有改**，列在「還沒驗證／待辦」。
2. **事件檢視器會列出兩個 run，但沒帶 `--root-8cam` 時狀態是 `UNAVAILABLE`。** 實測（`ev-no8cam.log`、`ev-with8cam.log`）：

   | 啟動方式 | A4-1-8CAM | B4-1-8CAM | 驗證時間 |
   | --- | --- | --- | --- |
   | 只有 `--root` | UNAVAILABLE（250 格／8 鏡頭） | UNAVAILABLE（210 格／8 鏡頭） | 17.1 s |
   | `--root` ＋ `--root-8cam` | **OK**（250 格、8 鏡頭） | **OK**（210 格、8 鏡頭） | 74.6 s（和其他程序同時跑） |

   原因：`start_all_demo.command` 啟動事件檢視器時沒有傳 `--root-8cam`（`start_all_demo.ps1` 同樣沒有）。資料本身是對的：`local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe` 存在，全量驗證通過。

**修法（repo 檔案）**：本 PR 改 `start_all_demo.command`：新增 `CX8_ROOT`（預設 `$ROOT/local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe`），資料夾存在才傳 `--root-8cam`。`start_all_demo.ps1`（Windows）**沒有改**，也沒有測。

**不需要 LOCAL 資料登錄**：資料根已經在 `local/data/`。

單獨啟動事件檢視器（含 8CAM）給使用者看：

```bash
cd ~/amidst && node frontend/event-viewer/server.mjs --root "$HOME/amidst/local/evidence/r004-cx7-d115-20261102-01a199f8" --root-8cam "$HOME/amidst/local/data/r004-4actor-natural-walk-eightcam-20261114/bundle/safe" --port 8780
```

啟動後約 60–75 秒才會 ready（全量驗證 PNG）。

## 4. 截圖

在測試伺服器（8795＝主畫面，8798＝帶 `--root-8cam` 的事件檢視器）上截，Chrome headless 1440×900。原檔在 scratchpad，另複製到 LOCAL `local/evidence/demo-update-prep-20261115/gate-20261115-1829/screenshots/`：

- `01-main-8795.png` 封面；`01b-view.png` 進入後的主畫面（B-05 監控牆）
- `02-run-A4-1-8795.png`、`03-run-B4-1-8795.png` 主畫面的 A4-1、B4-1
- `04-8cam-A4-1-grid-8798.png`、`05-8cam-B4-1-grid-8798.png` 8 鏡頭格狀畫面（8 個鏡頭、3 欄）

## 5. 更新步驟（使用者在終端依序執行）

先決定要不要做：做之前 8785 會中斷約 1–2 分鐘。

**5.0 事前檢查**（每項都要過）

```bash
cd ~/amidst && git status --short && git rev-parse --abbrev-ref HEAD && git rev-parse HEAD
```

輸出：第一個指令沒有任何輸出、分支 `main`、HEAD 是 `74b84463cc4f911f363c6358e2f9ada3748fc7bd`。

```bash
cd ~/amidst && df -h ~ | tail -1 && lsof -nP -iTCP:8785 -sTCP:LISTEN
```

可用空間要大於 8 GiB（程式內建的保護線）；`lsof` 會顯示現在的 8785 程序，記下 PID。

**5.1 備份舊 pin（回滾用）**

```bash
cp ~/amidst/local/demo-pin.json ~/amidst/local/demo-pin.74b84463.bak.json
```

**5.2 把 `~/amidst` 快轉到被測的 commit**

```bash
git -C ~/amidst fetch origin
git -C ~/amidst merge --ff-only b24d6a26dc3f556f34270055cab45f5c5dd6382b
git -C ~/amidst rev-parse HEAD
```

最後一行必須是 `b24d6a26dc3f556f34270055cab45f5c5dd6382b`；`git -C ~/amidst status --short` 要沒有輸出。`--ff-only` 不會產生 merge commit，也不會改工作樹以外的東西。注意：8785 現在跑的程序會直接從這個資料夾讀前端檔，所以 5.2 一完成，舊程序就會開始提供新檔案；直接接 5.4 重啟。

**5.3 核准新 pin**（需要 24 小時內的閘門結果）

```bash
cd ~/amidst && python3 scripts/demo_pin.py approve --approved-by Polalalabear --gate local/evidence/demo-update-prep-20261115/gate-20261115-1829/RESULT.txt
python3 scripts/demo_pin.py check; echo "exit=$?"
```

`check` 要印 `exit=0`。

**5.4 停掉舊 8785、啟動新的**

```bash
lsof -nP -iTCP:8785 -sTCP:LISTEN -t | xargs kill
```

等 3 秒，`lsof -nP -iTCP:8785 -sTCP:LISTEN` 要沒有輸出（外層的 `uv run` 程序會跟著結束；沒結束就對剩下的 PID 再 `kill` 一次）。然後：

```bash
cd ~/amidst && AMIDST_DEMO_HOME="$HOME/amidst/local/data/demo-owned-v1" nohup ./start_445_demo.command --port 8785 > local/logs/demo-8785-$(date +%Y%m%d).log 2>&1 &
```

**5.5 驗證**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8785/
head -c 700 ~/amidst/local/logs/demo-8785-$(date +%Y%m%d).log
```

要印 `200`，日誌第一行有 `"url": "http://127.0.0.1:8785/workbench-v2/"` 和四個 run（B-05、A4-1、B4-1、r005）。再用瀏覽器開 `http://127.0.0.1:8785/workbench-v2/`，點「進入系統」，確認主畫面有畫面。

**5.6 回滾**（任何一步失敗就做）

```bash
lsof -nP -iTCP:8785 -sTCP:LISTEN -t | xargs kill
git -C ~/amidst reset --hard 74b84463cc4f911f363c6358e2f9ada3748fc7bd
cp ~/amidst/local/demo-pin.74b84463.bak.json ~/amidst/local/demo-pin.json
cd ~/amidst && python3 scripts/demo_pin.py check; echo "exit=$?"
```

`check` 印 `exit=0` 後再執行 5.4 的啟動指令。`reset --hard` 只在 `~/amidst` 工作樹乾淨時做（5.0 已確認）；沒有未提交的東西會被丟掉。

## 6. 還沒驗證的項目

- **沒有在 8785 上測**：閘門跑在 8795（scratchpad clone 的程式＋owned 資料根），不是 pin 資料夾本身。真實的 5.2–5.5 還沒執行。
- **`#543`（`4972f0f9`）沒被閘門測**。若要 pin 到最新的 main，要重跑閘門。
- **8785 的新 UI 沒有 A4-1-8CAM／B4-1-8CAM**（見第 3 節第 1 點）；要加是新功能，沒開 issue 也沒做。
- 本 PR 的 `start_all_demo.command` 修改只做了語法檢查（`bash -n`）；用 `--root-8cam` 手動啟動事件檢視器已驗證 OK，但沒有跑整個一鍵啟動腳本。`start_all_demo.ps1` 沒改。
- core-e2e 只跑了一次；上一輪的失敗（check 84／91）是否完全不再閃爍，一次通過不能證明。
- 閘門進行中我修改了 clone 裡的 `start_all_demo.command`（只有這個檔案，不在任何測試路徑上），所以被測 tree 嚴格說是 `ca6d0687…` 加這一個未提交的檔案；閘門開始時（unit 階段）tree 就是 `ca6d0687…`。
- 沒有跑 Blender、沒有用付費 API。

## 實際產出 / Actual output
- Model / effort: Sonnet 5.5 / medium
- PR / commits: 本 PR（`claude/feat-8785-update`，base `main` `4972f0f9`）；被測內容 `b24d6a26`（tree `ca6d0687…`）
- Files changed: `docs/operations/DEMO_8785_UPDATE_PLAN_20261115.md`（新）、`start_all_demo.command`（加 `--root-8cam`）
- Commands run and results: 見第 2 節（unit／dependency／HTTP／core-e2e／real-e2e 900、1300 全部通過）；事件檢視器有無 `--root-8cam` 的對照見第 3 節
- Artifacts: LOCAL `local/evidence/demo-update-prep-20261115/gate-20261115-1829/`（SHA-256 見第 2 節；`ev-no8cam.log` `4bcd67f863fba15f8c0a63e802d57fa8fa7348817651854be6cd19c941d8eeea`、`ev-with8cam.log` `f62bcb7da347847e1502c519804f2da0a347ab0bc79f1b39026a8d76500dfe55`）；截圖在 `…/screenshots/`
- Verified: 見第 2–4 節
- Not verified: 見第 6 節
- Deviations, UNKNOWN items and follow-ups: 8785 新 UI 沒有 8CAM run（待決定要不要做成功能）；`start_all_demo.ps1` 未改
