# 本機資料夾收尾交接（2026-11-15，#486 大掃除）

狀態：文件與程式在 PR `claude/feat-ops-cleanup`（base `main`）；**合併前不要做 (a)–(c) 的任何刪除或設定變更**。本文只寫指令，沒有任何指令被執行。每個刪除都要使用者先在對話裡同意（AGENTS.md）。

目標狀態（D171、D218）：本機只有 `~/amidst`（branch `main`，8785 demo 的 pin 資料夾，`local/demo-pin.json` 鎖在 `74b84463`）；Claude 與 Codex 都把它當專案資料夾，**雙方都只在 scratchpad clone 寫檔**（`git clone --shared --no-checkout ~/amidst <scratchpad>/clone`，origin 設成 GitHub，從 `origin/main` 開 `claude/feat-<線>`／`codex/feat-<線>` 分支，用完刪除）。LOCAL 產物只在 `~/amidst/local/{data,evidence,archive}`。

## 共用 gate（每個步驟前後各跑一次，三項都過才繼續）

```bash
git -C ~/amidst status --short            # 必須沒有輸出
git -C ~/amidst rev-parse --abbrev-ref HEAD   # main
git -C ~/amidst rev-parse HEAD            # 必須等於 local/demo-pin.json 的 commit（74b84463cc4f911f363c6358e2f9ada3748fc7bd）
cd ~/amidst && python3 scripts/demo_pin.py check; echo "exit=$?"   # exit=0
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8785/    # 200
```

PR 合併後 `main` 會前進，`~/amidst` 的 HEAD 與 pin 不變（8785 照舊）。**不要為了收尾去 pull、checkout 或 `demo_pin.py approve`**；要不要更新 pin 是另一個決定。

## (a) 合併後才能刪：3 個家目錄項目

為什麼要等合併：`scripts/build_office_expanded_static.py`、`scripts/revise_office_static_preview.py` 原本把輸出寫死在 `~/amidst-artifacts/...`；這個 PR 改成 `AMIDST_ARTIFACTS`（預設 `local/evidence`）。合併前刪掉 `~/amidst-artifacts` 不會壞東西，但腳本還會依舊路徑重建實體資料夾。 <!-- local-ref-ignore -->

| 項目 | 實際內容（2026-11-15 盤點） | 刪除影響 |
| --- | --- | --- |
| `~/amidst-artifacts` | 實體資料夾（0 B），裡面 76 個 symlink，目標都在 `~/amidst/local/*` | 目標不動；只移除連結 | <!-- local-ref-ignore -->
| `~/amidst-demo-state` | symlink → `~/amidst/local/data/demo-state` | 目標不動；runbook 已改用 `$AMIDST_ARTIFACTS/demo-state` | <!-- local-ref-ignore -->
| `~/.amidst-d169-boot` | symlink → `~/amidst/local/.migration-d169` | 目標（105 MB）不動 | <!-- local-ref-ignore -->

刪除前先確認沒有東西還在用（輸出都應為空）：

```bash
lsof +D "$HOME/amidst-artifacts" 2>/dev/null | head -3   # local-ref-ignore
find ~/amidst-artifacts -mindepth 1 ! -type l | head     # 只能有 symlink，不可有真檔  # local-ref-ignore
grep -rn "amidst-artifacts\|amidst-demo-state" ~/amidst/scripts ~/amidst/src ~/amidst/*.command | head   # 合併後的 main 不該再有活的引用  # local-ref-ignore
```

刪除指令（只刪 symlink，不用 `rm -r`，不跟隨連結）：

```bash
find ~/amidst-artifacts -mindepth 1 -maxdepth 1 -type l -delete && rmdir ~/amidst-artifacts   # local-ref-ignore
rm ~/amidst-demo-state ~/.amidst-d169-boot   # local-ref-ignore
```

刪除後：共用 gate 三項照舊；另外 `ls ~/amidst/local/evidence | wc -l` 與刪除前相同；`find ~ -maxdepth 1 -name 'amidst-*' -xtype l` 為空；`pytest tests/unit/test_paths.py -q` 通過。

## (b) Codex 改專案資料夾

順序：**N6 完成後**才改（N6 進行中不要動 Codex 的工作區）。

1. 在 Codex 應用裡把專案設為 `/Users/polalabear/amidst`（Codex 的專案選擇器；不用手改設定也行）。若要手改，把 `~/.codex/config.toml` 的 `[projects."/Users/polalabear/Developer/amidst"]`（約第 90 行）改為 `[projects."/Users/polalabear/amidst"]`，保留 `trust_level = "trusted"`。 <!-- local-ref-ignore -->
2. 關掉舊的 Codex 專案分頁，重新開啟一個 session。
3. 貼下面這段給 Codex，等它回報：

```text
Amidst 大掃除（#486）：專案資料夾已改成 ~/amidst，Claude 與你共用同一個資料夾。請只做檢查並回報，不要改任何檔案：
1. 工作區路徑是你家目錄下的 amidst 資料夾（Claude 的專案路徑，不是 Developer 底下的舊連結）。
2. git -C ~/amidst rev-parse --abbrev-ref HEAD 是 main。
3. git -C ~/amidst rev-parse HEAD 等於 local/demo-pin.json 的 commit（74b84463cc4f911f363c6358e2f9ada3748fc7bd）。
4. git -C ~/amidst status --short 沒有輸出。
5. 確認你之後寫檔只用 scratchpad clone：git clone --shared --no-checkout ~/amidst <scratchpad>/clone，origin 設成 GitHub，從 origin/main 開 codex/feat-<線> 分支（一條功能線一個分支一個 PR，base main，CI checks 綠燈，只用 merge commit）；不要在 ~/amidst 內改檔、切分支、commit，也不要在裡面跑 git clean / checkout . / reset；用完刪除 clone。LOCAL 產物只放 ~/amidst/local/{data,evidence,archive}，附 SHA-256。
回報格式：五項各寫 OK／不 OK 與實際輸出。
```

4. 五項都 OK 才進 (c)。任何一項不 OK：保留 `~/Developer/` 的連結，不要刪。

## (c) Codex 確認後才能刪：`~/Developer/` 三個 symlink

| 項目 | 目標 |
| --- | --- |
| `~/Developer/amidst` | `~/amidst/local/archive/office-canonical`（已封存） | <!-- local-ref-ignore -->
| `~/Developer/amidst-claude` | `~/amidst/local/archive/checkouts/amidst-claude` | <!-- local-ref-ignore -->
| `~/Developer/amidst-q1q5` | `~/amidst` | <!-- local-ref-ignore -->

Claude 的舊對話存在 `~/.claude/projects/`，依專案路徑編碼，**刪除連結不影響**（`-Users-polalabear-Developer-*` 的紀錄資料夾保留不動）。

```bash
ls -l ~/Developer/amidst ~/Developer/amidst-claude ~/Developer/amidst-q1q5   # 確認三個都是 symlink  # local-ref-ignore
grep -n "Developer/amidst" ~/.codex/config.toml   # 改完 (b) 後應該沒有輸出  # local-ref-ignore
rm ~/Developer/amidst ~/Developer/amidst-claude ~/Developer/amidst-q1q5   # local-ref-ignore
```

刪除前後都跑共用 gate。刪完後在 Codex 與 Claude 各開一個新 session，確認都能開在 `~/amidst`。

## (d) 保留項目與之後要刪時的做法

保留（不在本次刪除範圍）：

- `local/archive/office-canonical`（原始 Office 素材，約 943 MB）：`amidst-claude` 是它的 linked worktree，所以**不能先刪 office-canonical**。 <!-- local-ref-ignore -->
- `local/archive/checkouts/amidst-claude`（500 MB）：有 7 個已修改檔案沒有逐檔核對；10 個未推送 commit 都在遠端 `archive/*` 分支上。 <!-- local-ref-ignore -->
- 另兩個舊 checkout（`amidst-d139`：有 1 個沒有保存在別處的 stash；`amidst-demo-20261104`：有未追蹤的資料）。
- 6 個「關閉未合併」的證據分支：`argon/424`、`argon/425`、`argon/426`、`argon/429`、`codex/445-independent-previews`、`codex/467-r005…`（完整名稱以遠端為準）。

之後要刪時（每一步都要使用者同意）：

1. checkout：先 `git -C <checkout> stash list`、`git -C <checkout> status --short`、`git -C <checkout> log --branches --not --remotes` 逐項確認內容已在遠端或使用者說不要；再依序刪 `amidst-claude`（先 `git -C local/archive/office-canonical worktree remove`）→ 其他 checkout → 最後才考慮 office-canonical。 <!-- local-ref-ignore -->
2. 6 個分支：先建 `archive/<分支名>` tag 並推送（`git tag archive/<name> <sha> && git push origin archive/<name>`），確認 `git ls-remote --tags origin` 有它，再 `git push origin --delete <name>`。
3. 刪除後 `git ls-remote --heads origin`、共用 gate、`git merge-base --is-ancestor <sha> origin/main`（已合併分支）都要再跑。

## 實際產出 / Actual output
- Model / effort: Sonnet 5.5 medium
- 本文件的指令：全部**未執行**；盤點數字來自 `local/evidence/cleanup-final-20261115/SUMMARY.md`（LOCAL，唯讀報告；SHA-256 不適用，非交付物）。
- Not verified: 各 symlink 目標在合併後是否仍存在（刪除當天用共用 gate 與 `ls -l` 再確認）；N6 是否已完成（由協調者判斷）。
