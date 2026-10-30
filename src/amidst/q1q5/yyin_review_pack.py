"""CQ-28 offline review payloads; human choices never update graph authority."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .yyin_main_pack import ASSETS, canonical, csv_bytes, load, public_text, regular, require, sha

SOURCE_HEAD = "79b34e33975a0e420d64b2fd994cbac97e92de7b"
GRAPH_HEAD = "0c34287b0b0c21c672f863fd281934f37e8aa24b"
RECEIPT_SHA = "55ef71c6fe13d5d9ceef30d35788da6d7764307185f77fd858562776fd586023"
FILES = ("s1-1-wide-door.svg", "s1-2-branch-depth.svg", "s1-3-wide-bottom.svg")
CAMERAS = ("CAM_WIDE", "CAM_BRANCH", "CAM_WIDE")
PROMPTS = ("CAM_WIDE 沒標成出入口的那扇門，是圖上哪一處？A含PORTAL_R102候選，B為右側大開口。",
           "CAM_BRANCH 哪個範圍符合你說的「到轉角處、涵蓋走道」？A為目前E_CORNER_N，B再延伸，C只指下緣中央位置。",
           "CAM_WIDE 你說的「下方的圖片邊緣」出入口，是最下緣左／中／右哪一段？")
COLUMNS = ("題號", "選項", "備註")
IDS = ("s1-1", "s1-2", "s1-3")
ANSWERS = ("A", "B", "C", "都不是", "看不出來")


def review_payloads(inputs, *, synthetic_only):
    require(isinstance(inputs, dict) and set(inputs) == {"path", "receipt_sha256"}, "REVIEW_SOURCE_PIN_REQUIRED")
    root = Path(inputs["path"]).absolute()
    require(root.resolve() == root and root.is_dir(), "REVIEW_SOURCE_CANONICAL_REQUIRED")
    receipt_path = regular(root / "RECEIPT.json")
    raw = receipt_path.read_bytes()
    require(sha(raw) == inputs["receipt_sha256"], "REVIEW_RECEIPT_PIN_MISMATCH")
    doc = load(raw)
    if synthetic_only:
        require(doc.get("fixture_role") == "SYNTHETIC", "SYNTHETIC_REVIEW_REQUIRED")
    else:
        require(sha(raw) == RECEIPT_SHA and doc["graph_source_commit"] == GRAPH_HEAD, "REVIEW_SOURCE_UNSELECTED")
    require(all(doc.get(k) is False for k in ("gt_read", "rendered", "source_blend_read", "events_read")), "REVIEW_SOURCE_BOUNDARY_INVALID")
    require(set(doc["files"]) == set(FILES) and len(doc["questions"]) == 3, "REVIEW_QUESTIONS_INVALID")
    payloads, source_files = {}, {receipt_path: sha(raw)}
    for i, row in enumerate(doc["questions"]):
        require(row["file"] == FILES[i] and row["camera_id"] == CAMERAS[i]
                and row["allowed_answers"] == list(ANSWERS), "REVIEW_QUESTIONS_INVALID")
        path = regular(root / FILES[i]); svg = path.read_bytes()
        require(sha(svg) == doc["files"][FILES[i]], "REVIEW_IMAGE_PIN_MISMATCH")
        # Pinned source SVGs only embed sanitized PNG bytes. Never execute content.
        text = svg.decode("utf-8")
        require("<!" not in text, "SVG_DECLARATION_FORBIDDEN")
        parsed = ET.fromstring(text)
        for element in parsed.iter():
            require(element.tag.rsplit("}", 1)[-1] in {"svg", "rect", "style", "title", "text", "defs", "image", "g", "use", "polygon"}, "SVG_ELEMENT_FORBIDDEN")
            for key, value in element.attrib.items():
                require(not key.lower().startswith("on"), "SVG_EVENT_FORBIDDEN")
                if key.rsplit("}", 1)[-1] == "href":
                    require(value.startswith("#") or value.startswith("data:image/png;base64,"), "SVG_EXTERNAL_REFERENCE")
        require(not re.search(r"url\(|@import", text, re.I), "SVG_STYLE_REFERENCE")
        public_text(re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "PNG", text).encode())
        if synthetic_only:
            require("SYNTHETIC" in text, "SYNTHETIC_REVIEW_REQUIRED")
        payloads["s1/" + IDS[i] + ".svg"] = svg
        source_files[path] = sha(svg)
    data = {"row_ids": list(IDS), "columns": list(COLUMNS), "allowed_answers": list(ANSWERS),
            "questions": [{"id": rid, "prompt": PROMPTS[i], "image": rid + ".svg"} for i, rid in enumerate(IDS)],
            "fixture_role": "SYNTHETIC" if synthetic_only else "STATIC_REVIEW_CANDIDATE"}
    payloads["s1/data.js"] = b"window.REVIEW_DATA=" + canonical(data) + b";\n"
    payloads["s1/DATA.json"] = canonical(data) + b"\n"
    table = csv_bytes(COLUMNS, [{"題號": rid} for rid in IDS])
    payloads["s1/確認.csv"] = payloads["templates/s1.csv"] = table
    for name in ("review.html", "review.js"):
        payloads["s1/" + name] = (ASSETS / name).read_bytes()
    payloads["s1/README.txt"] = "s1審圖約15–20分鐘。開review.html逐題查看A／B／C疊圖，選都不是／看不出來也可以，請加備註。只確認位置，不核准任何設定。\n".encode()
    return payloads, source_files, {"source_receipt_sha256": sha(raw), "source_head": SOURCE_HEAD if not synthetic_only else "SYNTHETIC"}
