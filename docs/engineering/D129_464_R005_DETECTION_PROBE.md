# D129 / #464 r005 RT-DETR 靜態 RGB 工程探測

狀態：**ENGINEERING_ONLY / PARTIAL**。六張 `STATIC_CAMERA_RGB` 各推論一次；`HUMAN_LAYOUT_ONLY` 不進模型。0.30 為事前固定的報表展示門檻；raw top300 每圖完整留在 LOCAL。下表是模型原始類別與分數，未經獨立標註驗證，不代表正確率或物件不存在。

## 來源與執行邊界

- #418 v2 receipt SHA-256 `0f6b279e4d535959aad7bff769022f6fcf0a2257e2aca922f6f9fa0fac1ea3bd`，逐圖 hash/bytes/purpose/allowlist/symlink 在 decode 前核驗。來源 PNG 原 bytes 未修改。
- 權重 SHA-256 `3ba8b5c909c9a1c4f21e96d0a7251ab1a485093955ca327d0061fef8d33c66f0`（81,001,853 bytes）；model-config SHA-256 `529ef3db2f006bf2ece36bc980406a549f6e3a85601aff03e740f8b264c49213`；49 個 Python source hashes 全相符。
- 本次 source Git HEAD **UNKNOWN**（LOCAL model-source 無 `.git`）。舊 ACCEPTANCE 記 `f1d13cebc7c9437fb27ebf8450b5c43d01d7d77b`；adapter metadata 報 `df2a96c8c3a098567a1149bf0248da6efe6d495d`；二者均非本次 Git HEAD 證據。
- CPU FP32、seed 7、threads 2、`torch.load(weights_only=True)`、`pretrained=False`；既有 artifact runtime-deps：torch 2.6.0、torchvision 0.21.0、Pillow 13.0.0、NumPy 2.5.4。隔離子程序的 `amidst` import 來自 task clone。此設定僅本 task 工程探測，未擴張 #417 正式參數核准。
- #457 Draft #470 `ea707902690d568700c90a3894805f168e244695` 三份小 JSON 以 exact `git show` 複製至 LOCAL contract dir；未 import #457 loader 或餵 graph 給 detector。coverage 仍 `NOT_EVALUATED`。

## 0.30 以上逐項辨識結果

| Camera | 類別 | 分數 | bbox xyxy px |
|---|---|---:|---|
| CAM_R101_IN | chair | 0.823 | [326.37, 300.90, 440.62, 465.71] |
| CAM_R101_IN | laptop | 0.814 | [335.98, 247.89, 388.62, 292.05] |
| CAM_R101_IN | dining table | 0.565 | [297.42, 235.80, 484.15, 356.43] |
| CAM_R101_IN | bottle | 0.503 | [422.07, 231.04, 432.89, 258.26] |
| CAM_R101_IN | chair | 0.494 | [505.47, 233.71, 580.29, 348.83] |
| CAM_R101_IN | chair | 0.413 | [506.28, 234.16, 543.08, 333.90] |
| CAM_R101_IN | laptop | 0.355 | [339.67, 269.85, 388.47, 292.28] |
| CAM_R101_IN | book | 0.324 | [339.67, 269.85, 388.47, 292.28] |
| CAM_R101_IN | bench | 0.305 | [326.37, 300.90, 440.62, 465.71] |
| CAM_R102_IN | book | 0.704 | [342.76, 270.09, 381.95, 289.54] |
| CAM_R102_IN | bench | 0.537 | [325.52, 300.03, 440.34, 465.92] |
| CAM_R102_IN | chair | 0.535 | [325.52, 300.03, 440.34, 465.92] |
| CAM_R102_IN | chair | 0.454 | [505.36, 233.37, 580.09, 349.05] |
| CAM_R102_IN | dining table | 0.452 | [298.63, 238.10, 484.20, 356.35] |
| CAM_R102_IN | bench | 0.419 | [505.36, 233.37, 580.09, 349.05] |
| CAM_R102_IN | dining table | 0.391 | [297.22, 241.01, 483.43, 466.37] |
| CAM_R102_IN | chair | 0.360 | [410.00, 210.25, 481.99, 321.76] |
| CAM_R102_IN | chair | 0.315 | [505.96, 233.98, 543.06, 334.06] |
| CAM_R102_IN | bench | 0.309 | [511.09, 274.37, 580.34, 349.58] |
| CAM_R103_IN | laptop | 0.879 | [316.92, 283.85, 371.30, 330.42] |
| CAM_R103_IN | chair | 0.864 | [516.22, 320.09, 621.84, 466.55] |
| CAM_R103_IN | dining table | 0.801 | [274.24, 281.35, 488.46, 499.41] |
| CAM_R103_IN | chair | 0.632 | [372.22, 244.78, 450.17, 335.81] |
| CAM_R103_IN | cup | 0.520 | [390.79, 339.53, 410.86, 363.25] |
| CAM_R103_IN | bowl | 0.333 | [390.79, 339.53, 410.86, 363.25] |
| CAM_R104_IN | chair | 0.848 | [516.24, 320.08, 621.72, 465.99] |
| CAM_R104_IN | dining table | 0.817 | [274.34, 282.45, 488.15, 499.13] |
| CAM_R104_IN | book | 0.667 | [324.27, 302.77, 365.08, 327.64] |
| CAM_R104_IN | chair | 0.638 | [372.25, 244.75, 450.18, 335.15] |
| CAM_R104_IN | bottle | 0.383 | [392.86, 323.76, 408.54, 363.73] |
| CAM_CORR_W | stop sign | 0.539 | [0.55, 94.07, 438.27, 538.61] |
| CAM_CORR_W | stop sign | 0.361 | [521.24, 90.97, 959.83, 538.67] |
| CAM_CORR_E | vase | 0.321 | [243.31, 265.99, 427.93, 538.98] |

## 執行時間及輸出

| Camera | 原始候選 | ≥0.30 | preprocess ms | forward ms | postprocess ms | total ms |
|---|---:|---:|---:|---:|---:|---:|
| CAM_R101_IN | 300 | 9 | 4.63 | 324.28 | 0.56 | 330.41 |
| CAM_R102_IN | 300 | 10 | 4.01 | 246.12 | 0.34 | 251.24 |
| CAM_R103_IN | 300 | 6 | 4.50 | 300.38 | 0.39 | 306.14 |
| CAM_R104_IN | 300 | 5 | 4.74 | 283.74 | 0.48 | 290.00 |
| CAM_CORR_W | 300 | 2 | 6.79 | 312.46 | 0.29 | 320.45 |
| CAM_CORR_E | 300 | 1 | 3.99 | 244.24 | 0.30 | 249.20 |

Cold load 350.06 ms。六張各 300 原始候選。LOCAL `/Users/polalabear/amidst-artifacts/d129-464-r005-probe-20261105-a/raw_top300.jsonl` SHA-256 `1c0d756490a09de73fc006c4fe17f5088c2386e30eb569d118b949fa52cdee53`；`report.json` SHA-256 `0915d54d585fcbd8e89575bf1ab43dec0ae3b8e85839b8e59704fa9d03b6b021`。

## 人工覆蓋待填

目前沒有可核定的 `MANUAL_ON_STATIC_FRAME`。下表僅待人工審查，不將模型偵測或 AI 視檢等同人工覆蓋；`human_approval_verified=false`。

| Camera | Frame SHA-256 | Reviewer | Date | Covered regions | Approval |
|---|---|---|---|---|---|
| CAM_R101_IN | `eb8530511733152a49de710d2ae0bf49233a125c89d7b8cd7ccef5e6247375b9` | PENDING | PENDING | NOT_EVALUATED | PENDING |
| CAM_R102_IN | `42c14c9e1b13bca4b67f1ac662933e8d23341e3ffbb86da193928c0cbb82803e` | PENDING | PENDING | NOT_EVALUATED | PENDING |
| CAM_R103_IN | `4e03f03747d97296f67d92eb4f4dbb87026d6b7b00a21a4dd0596572a9a10702` | PENDING | PENDING | NOT_EVALUATED | PENDING |
| CAM_R104_IN | `aa1705d04961d2652dfe18b29c31ae7f90d9de149f5c6634b8002c23dd4fce3e` | PENDING | PENDING | NOT_EVALUATED | PENDING |
| CAM_CORR_W | `22255ebdbb9a2c06bb5c7a6971b53384c12fad7e42c12ae3609340458db46241` | PENDING | PENDING | NOT_EVALUATED | PENDING |
| CAM_CORR_E | `f75db517ebe9aadd34a859e8b581eea39e5415b3a151db840fad7bc42e9439ee` | PENDING | PENDING | NOT_EVALUATED | PENDING |

需由 @Polalalabear 看原圖並逐 camera 確認覆蓋範圍；#462 可先使用模型偵測結果，但不可將此表當已核定覆蓋。原圖、權重與完整 raw outputs 保持 LOCAL。

## 驗證範圍

Synthetic focused tests 與既有 detection-index tests：14 passed。未跑完整套、Windows、API/runtime 接線、人工審查、正式研究驗收；未計算 accuracy。
