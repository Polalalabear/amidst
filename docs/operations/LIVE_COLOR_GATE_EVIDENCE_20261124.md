# #676 C4 read-only evidence — 2026-11-24

狀態：Codex 已完成，待 Claude 審查（唯讀證據整理）。Refs #676、#589、#690、#703。
原事件與本次現況／合成診斷分開；沒有重啟、模型呼叫、資料外傳或原始錄製修改。

## 原23.5秒事件：已知與UNKNOWN

唯一事件來源仍是#676使用者截圖描述：選藍衣，CAM_W2藍框可見，HUD失聯23.5秒，
事件#8鎖定→#13離開視野→#27失聯，advisor off／規則。
該時刻錄製、source run／capture clock、最後估計、候選距離、實際gate快照及reject_reason分布
均 **UNKNOWN**。沒有原recording就不能把後面的合成23.5秒fixture當作根因重現，
也不能把目前advisor=agent改寫成當時狀態。

## 本次目前runtime的唯讀快照

GET `/config`、8791 listener、PID45196 argv／cwd與runtime git HEAD已只讀核對。
目前runtime是 `c988ed607cb2941bde2b84688f9675213efd2a98`，cwd `local/runtime/live-main`，
advisor=agent、model=terra6.1、adaptive、expand_every=1、recent_red_s=2.0 s。
此舊runtime `/config`沒有gate欄位；不是0，也不是#690已部署。
從該runtime source parser與process未帶gate覆寫參數可得本次啟動設定：
**gate=4.0 m、growth=0.0 m/s、max=8.0 m**。這是source＋argv核對，不是原事件的逐tick量測。
固定growth=0時，失聯23.5秒後gate仍4.0 m；max8.0不是實際已放大的gate。

## #690核准source上的離線診斷輸出

在scratch暫切到#690確切head `4d60514e5b05575bf7c01d6d2d51b063e472abc7`，
執行未修改的 `scripts/verification/live_color_gate_diagnose.py`，內建兩次結果相等assert通過。
沒有影像、detector、renderer或GT輸入；server／scheduler／advisor／tracker SHA全寫在收據。

以下每個顏色分開重播，初始最後估計[0,0]、gate4m、growth0、t_seen=0：

| capture s | 合成觀測 | 距離 m | effective gate m | #690 reject_reason | 結果 |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 無框 | 無 | 4.0 | 無偵測，不計reason分母 | lost_ticks=1 |
| 23.5 | 同色[5,0] | 5.0 | 4.0 | OUT_OF_GATE | 比gate多1.0m，lost_ticks=2 |
| 24.0 | 異色[1,0] | 1.0 | 4.0 | COLOR_MISMATCH | lost_ticks=3 |
| 24.5 | 同色[1,0] | 1.0 | 4.0 | null | TRACKING、lost_ticks=0 |

25.0秒人工USER_PICK把[5,0]當新seed；25.5秒同色[5,0]持續TRACKING。
表中的23.5是合成capture秒，lost_ticks仍2，不能冒充原HUD的23.5秒完整trace。
舊腳本diagnostic.reason用OUTSIDE_GATE／ELIGIBLE／NO_OBSERVATIONS；
本次另外呼叫相同head的 `State._diagnose_detections` 統計真正API欄位值OUT_OF_GATE／null。
不把NO_OBSERVATIONS補成一個虛構偵測。

| 分布（合成） | blue，N=3偵測 | red，N=3偵測 |
| --- | --- | --- |
| OUT_OF_GATE | 1 | 1 |
| COLOR_MISMATCH | 1 | 1 |
| null | 1 | 1 |
| CAM_NOT_SCHEDULED | 0 | 0 |

各有1個空觀測tick，不計入N=3。這不是原事件或LIVE長時間運行的頻率分布。
原事件reason分布仍UNKNOWN。fresh未排程鏡頭不推論，不能從0筆CAM_NOT_SCHEDULED推論全鏡頭都有偵測。

## #676是否必須等#589

**分三個範圍判斷**：

- #690的session色／scheduler記憶與診斷欄位已APPROVE，可在E5結束、使用者核准後合併；不需要等#589。
- 規則模式想在「超出固定4m」時自動接回，須等#589/R2的runtime relock設定、UNKNOWN回退或量測方案核定與adaptive ENTRY驗收。
  不可直接調大growth／gate，亦不可把離線GT-derived外觀尺度放進runtime。
- 原23.5秒事件的根因／是否修好，仍缺原recording與逐tick觀測；不能只憑#589完成就保證已修。
  人工reselect／pick與獲准後的Agent SELECT是不同路徑，不等於規則遠距接回驗收。

因此#676整項不關閉、不宣稱根因確定；保留#690的APPROVE和E5合併閘門。
若原錄製確實不存在，需另外由使用者／Claude核定一個可重現且source-bound的新回歸案例，
不能倒填原事件證據。

## LOCAL產物與重現

`local/evidence/cx-live-gate-c4-20261124/`：4檔、15,255 bytes（不含manifest本身），
MANIFEST SHA-256 `3a03998e0b5c6a482ebb03a1503c6d03d891646558a2298904fe3599fcac65a2`。
逐檔hash／bytes在manifest；全部4檔已重新hash相符。
- diagnostic.json：合成兩色trace，8,769 bytes，SHA-256 `057f4b392c386d93affff926335d63e62128af390953e79ae7c6bcdc39e2c3b1`。
- reject-reasons.json：API診斷分布，3,002 bytes，SHA-256 `bb165ba55cf99a58063dfe322a5a56dbda328063c8b59fb508d75a07972a9407`。
- reject_summary.py：只讀統計recipe，1,754 bytes，SHA-256 `25a9438d12266e9672cb82a5995af82ad26669cc1701b55fb38e2ce461743961`。
- runtime-config.json：本次現況快照，1,730 bytes，SHA-256 `f9165f6ca02c53a3acc31c1f0a410fec67749cb63521bc8b0523779cd3a20723`。

合成診斷／統計可從確切4d60514e重建；現況快照含當次時間，未來重讀不能重建同一歷史快照。
沒有引用找不到的舊scratch artifacts，也沒有讀取大型媒體。

```sh
# 自己的scratch clone，先checkout核准4d60514e；C4_OUT放新的LOCAL evidence目錄。
PYTHONPATH=src uv run --offline --no-project --python <existing-env>/bin/python python -B scripts/verification/live_color_gate_diagnose.py --out "$C4_OUT/diagnostic.json"
# 下方Python recipe存成reject_summary.py後，以相同offline uv／PYTHONPATH執行。
```

```python
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from amidst.live_mode.server import State
from amidst.live_mode.candidates import TrackSelection
root=Path(__import__('os').environ['C4_OUT'])
source=json.loads((root/'diagnostic.json').read_text())
result={'scope':source['scope'],'source_sha256':source['source_sha256'],'colors':{}}
for color,case in source['cases'].items():
    state=State.__new__(State)
    state.selection=TrackSelection()
    state.selection.start(color,False)
    counts=Counter({'OUT_OF_GATE':0,'COLOR_MISMATCH':0,'CAM_NOT_SCHEDULED':0,'null':0})
    rows=[]
    last_est=[0,0]
    for row in case['rows']:
        diag=row['diagnostic'][0]
        x=diag['distance_m']
        observations={'CAM_W2':[] if x is None else [{'bbox':[0,0,10,20],'score':0.9,'color':diag['color'],'est_xy':[x,0]}]}
        state.selection.observe(row['tick'],row['capture_s'],observations)
        state._diagnose_detections(observations,row['tracking'],{'CAM_W2'},last_est,4.0)
        reasons=[d['reject_reason'] for d in observations['CAM_W2']]
        counts.update('null' if r is None else r for r in reasons)
        rows.append({'tick':row['tick'],'capture_s':row['capture_s'],'distance_m':x,'gate_m_effective':4.0,
                     'reject_reasons':reasons,'state':row['tracking']['state'],'lost_ticks':row['tracking']['lost_ticks']})
        last_est=row['tracking']['est_xy']
    result['colors'][color]={'detection_count':sum(counts.values()),'empty_observation_ticks':1,'counts':dict(counts),'rows':rows}
(root/'reject-reasons.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({c:d['counts'] for c,d in result['colors'].items()},sort_keys=True))
```

Commands／results：原diagnostic內兩次重播assert PASS；上方helper統計兩色各N=3，
每色OUT_OF_GATE1／COLOR_MISMATCH1／null1／CAM_NOT_SCHEDULED0；manifest4/4 rehash PASS；
git diff --check PASS。純證據整理，沒有再跑完整或focused pytest（A3/B1已另記75 passed）。
未驗證原事件、真實模型、UI新欄位整合、遠距規則自動接回或R2；未改code／門檻／source assets。
