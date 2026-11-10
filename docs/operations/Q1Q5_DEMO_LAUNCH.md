# Q1–Q5 pinned replay 啟動（CQ-41，分段）

> 2026-11-08 起依 D132，GitHub 已整合成四個大問題：A #445（Demo 驗收）、B #479（實驗紀錄）、C #486（大掃除）、D #489（Agentic）。文中舊編號已關閉，括號內註明併入的大問題，以 #93 為準。

目前交付預設 deterministic RECORDED replay，以及 `--live` 未選定 runtime 時的 fail-closed replay。**健康 live 執行與執行途中錯誤後的 UI 回放交接尚未交付**，提案／owner gate 記在 FEAT-5 #372（已關閉，見 #93）。這份啟動器不會呼叫、下載、預載、重啟或卸載模型。

## 一行啟動

從含本 feature 的 checkout 執行（Python ≥3.12）。`P1_BUNDLE` 是既有 LOCAL P1 v4 包的 canonical 絕對路徑；`NEW_STATE` 是 repo 外、包外、父目錄已存在的新 LOCAL 目錄路徑。

```sh
./start_demo.command --bundle "$P1_BUNDLE" --manifest-sha256 6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7 --state-root "$NEW_STATE"
```

也可用 `uv run python scripts/start_q1q5_demo.py` 帶同樣參數。`--no-open` 只輸出網址；`--port 0` 由作業系統配置未占用的 loopback port，指定占用中的埠則回 `PORT_IN_USE`。啟動先驗 manifest／payload bytes、新 state、可用磁碟 ≥8 GiB 與 Python 版本；不改原包或素材。來源 source commit 為 `c26d7cdd07deb43c9991a4f46403ea0236277fb1`，不是正式 r004。

開出的既有 workbench-v2 會載入 pinned RULE_ONLY 錄製，顯示 `RECORDED · SYNTHETIC`。底層保留 RGB 播放所需的 run／clock／index 中繼資料，拒絕新 Q1／Q2／Q3 推論請求；只開回放、既有 artifact 與 hash-bound RGB 讀取路徑。API 的回放 domain response bytes、output hash、decisions／links hash 都維持原錄製。

`--live` 目前印出「fallback：錄製重播（live runtime 未選定；未呼叫模型）」，仍以同一 pinned 錄製開啟；`model_calls=0`。這不是健康 Ollama／D65 live 的完成宣告。畫面目前只有既有 RECORDED 來源標示，額外 fallback 文案與 #337（已關閉，見 #93） 的 demo 導覽仍待 UI 擁有者接線。

停止本次服務：在啟動 terminal 按 Ctrl-C。只結束本次 loopback server；PID／owner nonce／URL 寫在新 state 的 `DEMO_SERVER.json`，不停止舊服務。若 API 關閉，可用新 state 路徑重新啟動；既有 state 不覆寫。

## 驗收與限制

```sh
uv run python -m pytest -q tests/q1q5/test_demo_launcher.py tests/q1q5/test_portable_pack.py
AMIDST_REQUIRE_IMPL=1 uv run python -m pytest -q tests/q1q5/test_check_demo_rehearsal.py
git diff --check origin/codex/q1q5-staging HEAD
```

單元測試禁止 outbound connection；保留 loopback server 所需的 inbound bind。LOCAL 啟停、逐 bytes HTTP 回放、model_calls=0 與 df 記在 [啟動收據](CQ41_REPLAY_LAUNCH_RECEIPT_20261102.json)。瀏覽器只驗 replay 可載入並播放、B 在 5.5 s 顯示 960×540 RGB；完整 demo、D-02 三項演練、UI-01～UI-14／流暢度與 U16／U17 均未驗收。

#337（已關閉，見 #93） 的 demo-mode／steps 尚無交件 head。依 #372（已關閉，見 #93） 歸併順序，本分支目前只合 #243（已關閉，見 #93）→#255（已關閉，見 #93）→#368（已關閉，見 #93） 並交可並行的 launcher 部分；#380（已關閉，見 #93）→#294（已關閉，見 #93）→#388（已關閉，見 #93） 與 B→E→A→C→D 留待 #337（已關閉，見 #93） head 到位後整合。#307（已關閉，見 #93） 未交付前守門為 NOT_RUN。#368（已關閉，見 #93） 兩份 schema 只依 D105 B-11 與使用者 11-02 的直接確認修改 description；`python -I` 同層 import 問題維持不改。

LOCAL 瀏覽器證據位於 `$AMIDST_ARTIFACTS/demo-launcher_20261102_01a199f8/`：`browser.json` 306 bytes、SHA-256 `bba95ac600da754aae4b3b45cde1e9a3da54181ba714803129dd3460400ce45e`；`replay-B.jpg` 96260 bytes、SHA-256 `68b4d33ed3a36e039fc2467ad1bb157eb9804689fd7f52e0bb877cf5837cb92a`。此為本次產生的驗收紀錄／畫面，不含原包副本；需要既有 pinned P1 來源與本分支程式才能重現。
