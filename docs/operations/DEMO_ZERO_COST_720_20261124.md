# #720 零付費收尾（2026-11-24）

狀態：Argon 互審 APPROVE，待 Claude 第1批。Draft、不合併。
未驗證項目保留，不宣稱 demo gate 通過。GT 不進推論，身分 UNCONFIRMED。

互審紀錄：[Argon APPROVE](https://github.com/Polalalabear/amidst/pull/725#issuecomment-7136562147)，
受審 head `7a390e4ca12ebbbd55648fc85e10efca6bed0479`。
Argon 只讀 GitHub，未重跑20題、檢視 LOCAL 截圖／MANIFEST／PPTX／PDF或正式 launcher。
本次續作只同步審查狀態，不修改程式、預期答案、14/20結果或下列未驗證界線。

## 1. #714 正式 launcher 與截圖

逐張看過既有12張PNG、12/12 hash吻合，新增提交版
[`截圖 README`](DEMO_720_SCREENSHOT_REVIEW_20261124.md) 與 LOCAL README複本。
3個 tmp 不計驗收，B-05兩張是額外圖。console沒有來源紀錄，寫 UNKNOWN。
**正式 launcher／scene3d HTTP／WebGL 未驗證**；本次沒有複製資產或繞過 guard，
也沒有在 pinned owned root 產生新的 launcher state。API harness 不當 launcher 替代驗收。

## 3. 換 pin 後 AC1–AC8

pin 仍 `c988ed607cb2941bde2b84688f9675213efd2a98`。沒有改 pin 或重啟／操作
8785、8791、8795、8796；**換 pin 後 AC1–AC8 未執行／未驗證**。
第2點 r3b 新模型補跑不做，等使用者決定 gate 標準；沒有改判原 gate。

## 4. 海報／簡報文字核對

對照已合併 AR-F5 #715（merge `10a1384c9676875f92d3d9bf12c9f849f8bdfeba`）
`docs/paper/F5_PAPER_DRAFT.md` §4.6、§5與結果來源。數字／判定保留。
找到並只修兩種文字：

- 海報結論與簡報12：原「允許 Agent 回答不在／棄權…皆未做」改成
  「分項比較提問時機、採用與棄權策略；延遲歸零對照（未做）」。既有 AO
  已有 NOT_VISIBLE 74／UNCERTAIN 9，未做的是分項比較。
- 海報表1圖說：補齊原判定的三項連言，錯人秒差區間上界<0、跟對率差下界>−0.05、
  McNemar p<0.05。未放寬門檻、未改原判定。

新副本留 scratch；原海報／簡報未改。兩個 zip 僅海報slide1與簡報slide12的
`a:t`文字改變，**非文字 XML、版面、字型、媒體與其他entry逐位元相同**。
因使用者禁止外傳影格，而原簡報含影格圖片，未上傳 Spaces；採本機 text-only 修補。
`scripts/verification/presentation_720_text_fix.py` 可重製。

用 bundled **LibreOfficeDev 26.8.0.0.alpha0 headless Impress** 實際開啟原檔與新副本，
各轉PDF（海報1頁、簡報12頁）。初次字型設定缺中文；改以 FONTCONFIG_FILE 指定
既有系統字型與 scratch cache，PingFang TC fallback Heiti TC。沒有改 PPTX 的字型設定。
已親看修改頁與海報，中文正常、修改文字在框內；同環境400px渲染的未改11頁逐位元相同。
PowerPoint GUI、精確PingFang換行仍未驗證；不把缺字初版PDF當可用交付。

| LOCAL 交付（相對於本次成品根） | SHA-256 |
|---|---|
| `deliverable/poster_A1_academic_e5_textreview.pptx` | `d89114a270581ab3238e6a8377dbe60e1ab14ba915acded2daf5188192e3e219` |
| `deliverable/amidst_slides_e5_textreview.pptx` | `bd6b53777646fd8e5896b179ddebcc4e9f100a07986578cff0c92ce60ab0cb4e` |
| `office-fonts-final/poster_A1_academic_e5_textreview.pdf` | `3309e95c6e4b4004bc846655aecde3766d2c007753e1ed841e122f49fb065304` |
| `office-fonts-final/amidst_slides_e5_textreview.pdf` | `85478e08d78326adb4614744dff571e94a5b97bd8fbccb9a1b59a8f78f8cccc1` |

原始交付位置：LOCAL `local/evidence/presentation-pack-20261123/deliverable-e5-20261124/`；
原海報 SHA `c345c27028603b92e5cd43b14636fd9489189bd75b83af0e1a3290f262d45575`，
原簡報 SHA `a2e8bf3c23ae80d28fbbd8d44eebb018055e58b7d715c158fcd75636f6cc0985`。

## 5. Q1–Q3 二十題

預期答案先提交 `0be6685e` 再執行；
[`功能驗收詳細結果`](../evaluation/Q1Q3_FUNCTIONAL_20_20261124.md)：精確預期 **14/20**，
6個差異保留（含預期表對字典與run鏡頭的錯誤假設）。實際執行Q1 4/4時段一致，
Q2 3/3種子集合一致；未解析5題不計入檢索。Q1鏡頭時段precision/recall各1.0，
只對執行的4題、對照凍結觀測，不是人物真值或整體準確率。Q1全部PARTIAL，未升格READY。
不做 Agent 查找、完整Q2追蹤或新spotlight的UI驗收。

## 成品、命令與限制

LOCAL scratch `local/evidence/cx-demo-720-20261124/` curated **15檔／10,525,874 bytes**
（不含MANIFEST）；MANIFEST SHA-256
`b7ea94ffd36ce03aa6da06396a8a3d3268300844e6783b87cb39c28e7d258521`。
逐檔大小／SHA都在manifest。中間字型失敗PDF與scratch state保留，但不在curated交付。
`questions-results.json` SHA `b28c532fca35059926d28896bc6bdf3e02ade9b0454238bc5cf17e19d6bcc35d`；
`screenshots-review.json` SHA `1ca33b2cb9407ce040c3892dd14241c57523d76d21bf0b53f9eb343ebe5eb221`。
腳本、預期表、README與結果說明已提交，原影格／GT與二進位成品保持LOCAL。

命令（本次用既有唯讀 Python、UV_CACHE_DIR=local/uv-cache；所有state/out只在scratch）：

```sh
uv run --offline --no-project --python "$DEMO_PYTHON" python -B scripts/verification/q1q3_functional_20.py freeze --evidence "$EVIDENCE_ROOT" --owned "$DEMO_OWNED_ROOT" --state "$OUT/new-freeze-state" --key "$OUT/expected-new.json"
# 本次先提交 configs/evaluation/Q1Q3_20_EXPECTED_20261124.json，才執行下列run。
uv run --offline --no-project --python "$DEMO_PYTHON" python -B scripts/verification/q1q3_functional_20.py run --evidence "$EVIDENCE_ROOT" --owned "$DEMO_OWNED_ROOT" --state "$OUT/new-run-state" --key configs/evaluation/Q1Q3_20_EXPECTED_20261124.json --out "$OUT/new-results.json"
uv run --offline --no-project --python "$DEMO_PYTHON" python -B scripts/verification/presentation_720_text_fix.py --source "$SOURCE_PPTX" --out "$NEW_PPTX"
FONTCONFIG_FILE="$SCRATCH_FONTCONFIG" soffice -env:UserInstallation="file://$SCRATCH_OFFICE_PROFILE" --headless --convert-to pdf --outdir "$PDF_OUT" "$NEW_PPTX"
pdftoppm -f 12 -l 12 -scale-to 1600 -png -singlefile "$SLIDES_PDF" "$PREVIEW_OUT"
```

`ruff check`兩個新工具與 `git diff --check` PASS；本次未跑全套或增加同實作鏡像測試。
初次freeze因相對state路徑被既有canonical path規則拒絕，改成resolve後成功；
沒有執行未提交預期的問句。模型／付費0、外傳0，未刪檔、未複製3D資產。
使用者仍決定gate標準／資產／pin；互審與CI狀態以PR實際產出為準。
