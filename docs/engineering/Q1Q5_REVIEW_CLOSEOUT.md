# 審查期間五項closeout（2026-10-25）

Refs #194、#145、#117；base #212。依使用者授權逐項提交，最後一次驗收。這是審查前置工程成果，formal_run_allowed=false，沒有正式r004 RGB／索引或人工核定。

[機器可讀成果](../history/Q1Q5_REVIEW_CLOSEOUT_20261025.json)記錄實際數值與來源hash。完整報告／錄製／CSV／圖保持LOCAL，原件不改。

## 1. #145 獨立重現與context補件

```json
{
  "task": "#145 independent recheck and context supplement",
  "status": "COMPLETE_WITH_CONTRACT_ITEMS_OPEN",
  "kit_commit": "807b587aa8f13da68d186933ad9c7969ffd92d3c",
  "original_cases": 176,
  "original_totals": {
    "dynamic": {
      "PASS": 1521,
      "SKIPPED_NO_CONTEXT": 4
    },
    "linked": {
      "PASS": 645,
      "SKIPPED_NO_CONTEXT": 4
    },
    "runner": {
      "PASS": 13143,
      "SKIPPED_NO_CONTEXT": 80,
      "FAIL": 6
    }
  },
  "supplemented_totals": {
    "dynamic": {
      "PASS": 1531
    },
    "linked": {
      "PASS": 655
    },
    "runner": {
      "PASS": 13343,
      "FAIL": 6
    }
  },
  "supplemented_q1_recordings": 44,
  "skip_no_context_removed": 88,
  "network_attempts": 0,
  "remaining_failures": 6,
  "remaining_failure_kind": "SCHEMA_VALID failure-call model_digest=null; pending contract section14 item20; no fabricated digest",
  "product_changes_required_by_current_evidence": false,
  "original_report_sha256": "a18df677fcecb2ffa92859b69a34b9bb2a79b03e7bb0d8b0470c23b327a4de8b",
  "supplemented_report_sha256": "69620d7f9ab127bc1136981a710bd5847b62b89ead906d75f7a12e703e140106",
  "focused_tests": 6,
  "ruff": "PASS"
}
```

## 2. Qwen3 逾時診斷

```json
{
  "task": "Qwen3 recorded timeout diagnosis",
  "status": "COMPLETE_WITH_TIMING_BREAKDOWN_UNKNOWN",
  "summary": {
    "q3": {
      "calls": 12,
      "timeouts": 12,
      "budgets_ms": [
        2000
      ],
      "latency_min_ms": 2001.839582924731,
      "latency_median_ms": 2003.2122079865076,
      "latency_p95_nearest_rank_ms": 2027.825125027448,
      "latency_max_ms": 2027.825125027448
    },
    "q5": {
      "calls": 6,
      "timeouts": 6,
      "budgets_ms": [
        2000
      ],
      "latency_min_ms": 2001.9510840065777,
      "latency_median_ms": 2002.4722705129534,
      "latency_p95_nearest_rank_ms": 2013.333374983631,
      "latency_max_ms": 2013.333374983631
    }
  },
  "calls": 18,
  "llm_used": 0,
  "new_generation_calls": 0,
  "budgets_changed": false,
  "server_probe": {
    "diagnostic_only": true,
    "generation_requests": 0,
    "results": [
      {
        "endpoint": "/api/version",
        "status": "OK",
        "wall_ms": 21.746,
        "version": "0.35.0"
      },
      {
        "endpoint": "/api/tags",
        "status": "OK",
        "wall_ms": 19.114,
        "requested_model_present": true
      },
      {
        "endpoint": "/api/ps",
        "status": "OK",
        "wall_ms": 0.523,
        "loaded_models": []
      }
    ]
  },
  "server_log_window": {
    "start": "2026-10-25T00:41:12.056290+08:00",
    "end": "2026-10-25T00:42:54.900697+08:00",
    "post_chat_status_counts": {
      "499": 1,
      "500": 17
    },
    "cancel_task_lines": 17,
    "supports_task_processing": true,
    "one_to_one_request_id_binding": false,
    "snapshot_sha256": "351375ab7a81e733c0fb0e5a7c0cc00be7c93874c29999498d00ec9ce70d9985"
  },
  "diagnosis": "All recorded calls exhaust the 2000ms provider deadline without completed output; server window shows processing and cancellation. Current non-generating metadata probes succeed. Per-call loading/queue/generation timings were not returned, so their contributions remain UNKNOWN. No verified runner samples is a monitoring gap, not proof the model never ran.",
  "next_action": "If instrumenting future engineering calls, record HTTP phase timings and runner process identity under the same deadline, then evaluate smaller prompt/output variants as separately versioned diagnostics; do not change formal budgets or count fallback as LLM success.",
  "audit_sha256": "8a6dee884b99f1eddc1c110b190c17462362ef24a5bdcf11249dc2801748233f",
  "focused_tests": 7,
  "ruff": "PASS"
}
```

## 3. 新版審查補件

本里程碑尚未執行，不列為完成。

## 4. ROI／轉移機械對照

本里程碑尚未執行，不列為完成。

## 5. Q3獨立填答包

本里程碑尚未執行，不列為完成。

## 重現與界線

工具 `scripts/closeout_q1q5_review.py` 的每項輸入需file SHA-256；所有輸出拒覆寫、低8GiB停止。原工具與來源資料逐檔驗pin，成功回覆只表示本工具完成資料處理；必須另讀各項FAIL／PENDING，不能把CLI完成當正式baseline通過。

CLI格式：`uv run --no-project --offline --no-cache --python <existing-python> python scripts/closeout_q1q5_review.py <command> --input <pinned-input.json> --input-sha256 <sha256> --output <new-local-dir>`。LOCAL驗收入口保留精確argv、環境、輸入pins與逐次報告；`conformance`完整跑原kit全部checks（沒有--only），硬拒網路。kit與詞表格式仍Draft，不代替契約核定。

產品、#127/#135/#189、原review包、checkout/index均不修改；新工具只讀context與工程紀錄。Q3 expected／人審備註不得進推論，GT／actor／劇本不讀。未取得獨立圖ROI、owner必要G4/HSV、正式Q3與程式前置核定前，不產正式資料。
