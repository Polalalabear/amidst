"""Local text-only PPTX corrections for #720; retain every non-text XML byte and media entry."""

import argparse
import hashlib
import json
import re
import zipfile

FUTURE_OLD = "允許 Agent 回答不在／棄權、不確定時才問、延遲歸零對照（皆未做）"
FUTURE_NEW = "分項比較提問時機、採用與棄權策略；延遲歸零對照（未做）"
GATE_OLD = "判定標準為錯人秒差的 95% 區間整個小於 0，且跟對率沒有明顯變差，才算 Agent 較好。"
GATE_NEW = "判定三項均須通過：錯人秒差區間上界小於 0、跟對率差下界大於 −0.05、McNemar p 小於 0.05。"


def patch(source, target):
    if target.exists():
        raise ValueError("OUTPUT_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    edits = []
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w") as dst:
        for item in src.infolist():
            old = src.read(item.filename)
            new = old
            if item.filename.endswith(".xml"):
                for before, after in [(FUTURE_OLD, FUTURE_NEW), (GATE_OLD, GATE_NEW)]:
                    new = new.replace(before.encode(), after.encode())
            if old != new:
                def strip(b):
                    return re.sub(rb"<a:t>.*?</a:t>", b"<a:t/>", b, flags=re.S)
                if strip(old) != strip(new):
                    raise ValueError("NON_TEXT_CHANGE")
                edits.append(item.filename)
            dst.writestr(item, new)
    return {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "changed_entries": edits,
        "non_text_bytes_equal": True,
    }


if __name__ == "__main__":
    from pathlib import Path

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(patch(a.source, a.out), indent=2))
