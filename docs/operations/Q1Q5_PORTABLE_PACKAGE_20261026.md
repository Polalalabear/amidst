# CX-10 組員可攜測試包（LOCAL）

用途只為P1工程操作；不含正式r004資料、GT、producer、模型權重或組員答案。組員不需torch/Ollama；Python3.12+與瀏覽器即可。原素材與完整錄製只在LOCAL包，不上傳GitHub。

## 成品與驗證

- `q1q5-p1-portable-v4-20261026/`：401檔，149501743bytes，320張RGB、凍結索引／設定、兩種模式錄製、同一整合commit程式。
- `MANIFEST.json` SHA-256：`6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7`。397個不可變payload逐檔hash；RETURN/STATE為人工作業與啟動輸出，明確不作推論輸入。
- ZIP：148511008bytes，SHA-256 `7749cc7877b97e4b8744577529605d5dfafd5c2673b13a1ca273ec984863924c`；壓縮後逐payload重新驗hash、CRC無錯。
- code source：整合分支commit `c26d7cdd07deb43c9991a4f46403ea0236277fb1`，SOURCE.json逐檔hash。沒有8個head的runtime overlay。
- 實際在Shared獨立根目錄（含中文/空白）用 `./start.command --no-open` 啟動；同一OS使用者，未宣稱第二個帳號／另一台實機驗收，Windows未測、不附start.bat。
- 正式builder CLI於Python3.12.12重建；與Python3.14產製原包的401檔逐bytes相同、MANIFEST一致。重建1550.277ms；df可用由11772704 KiB到11624800 KiB，均高於8GiB。這不是用df差額聲稱task總用量。

## 組員操作與回交

README.txt有四段：這份工作內容／要提交項目／操作／不要改。雙擊start.command或執行 `./start.command`；啟動驗證SHA、選未占用loopback埠，網址與PID/nonce在STATE/run-*/SERVER.json。Ctrl-C停止本次服務。

開啟RETURN/index.html，或服務的 `/return/`，逐項填AC1–AC8、T/F/不確定與理由，下載 `RETURN/測試回報_<姓名>_YYYY-MM-DD.csv`。另附問題／不確定／未完成項目、截圖與完整資料夾或ZIP；原包保留。預設全部空白。

瀏覽器下載已用SYNTHETIC_FORM_TEST驗證8列、UTF-8 BOM、指定檔名；不是組員回覆，不放回人審包，也不進正式指標。測試CSV hash `271a8d168fd420fc7637cd37f086291865286aeb2eaf3f4857a0f071c4c97974`。

## 可重建入口

`PYTHONPATH=src uv run --no-project --offline --no-cache --python <既有Python3.12> python scripts/build_q1q5_portable.py --repo <Git來源> --code-commit <40字SHA> --rgb <LOCAL safe/rgb.json> --rgb-sha256 <sha> --registry <LOCAL registry.json> --registry-sha256 <sha> --recordings <LOCAL descriptor.json> --recordings-sha256 <sha> --output <新LOCAL輸出目錄>`。

recordings descriptor schema為 `q-demo.portable-source-recordings.v1`，recordings[]逐筆含path（操作者本機canonical絕對路徑）、recording_id、file_sha256；不複製私有來源檔到GitHub。builder只讀固定Git blobs與明列safe資產，不checkout、不建worktree、不渲染、不推論、不安裝依賴；產物設定全是包根目錄相對路徑，server產生STATE內的本機rebase設定，不回改來源設定。低於8GiB停止，輸出不可覆寫。

9個builder focused PASS＋11 adapter focused PASS；實際P1播放／查詢與限制見 P1_ENGINEERING_ACCEPTANCE_20261026.md。兩錄製replay相同，但AC7全符合性仍未過；G4與正式baseline另受獨立gate。
