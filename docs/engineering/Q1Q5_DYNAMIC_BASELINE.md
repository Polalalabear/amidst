# 動態工程 baseline（#210）

本線使用新建工程場景，原 r004／審查包不變。8 秒、20 fps、A/B 共 320 張 960×540 RGB；人物位移與步態由獨立 producer 產生，producer/source.blend 與 motion 設定只留 LOCAL private_producer。推論只讀安全 RGB manifest、像素及靜態相機 hash。這是替代工程來源，身分未確認、物理可行性未知、correctness=null。

## 已驗證的第一階段

- 新 dynamic schema 拒絕 actor 欄位、重複 frame、錯 clock/grid、錯 run、錯 static pin。API 使用來源 50,000us 整數格，不將 20fps 誤作5fps。
- 舊靜態 RGB 保持相容；PNG 文字 metadata 在公開回應剝除，source/served hashes 分別記錄。
- focused `tests/q1q5/test_dynamic_rgb.py test_linked_runtime.py test_linked_workbench.py`：20 passed；變更 Python 檔 ruff 通過。
- 第一版圓滑人偶 pilot 18 張真 RT-DETR 均無 person>=0.5；留 LOCAL evidence/pilot-detections.json。已知失敗，不能算 baseline 成功。下一階段修正外形再測，不降低閾值。
- 依賴恢復獲使用者明確授權：任務專用 runtime-deps，未更改共享 venv。官方 RT-DETR commit df2a96c8c3a098567a1149bf0248da6efe6d495d 的49檔 hash 全符合原配置；原權重不變。

## 後續驗收資料

LOCAL 包 `/Users/polalabear/amidst-artifacts/q1q5-dynamic-baseline-v1_20261025/`。最終 README／ACCEPTANCE 將提供實際 motion、RT-DETR、Qwen3/RULE、replay、browser、cache、故障與前置審查數值。尚未完成的項目不因本階段通過而標成功。正式資料仍待 yyin 回收、Claude 獨立圖/ROI、必要 HSV 與凍結；#145 未解除、不 merge。
