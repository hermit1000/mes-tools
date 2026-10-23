"""Report Ballade A5 row usage and uncertain layout positions."""

import argparse
from collections import Counter
import json
from pathlib import Path

from .encode_mes import DEFAULT_WORKSPACE
from .text_layout import reviewed_lines
from .inline_names import refresh_inline_names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    items = []
    for path in sorted((workspace / "script-pc98/MES").glob("*_lang.json")):
        lang = json.loads(path.read_text(encoding="utf-8"))
        info = json.loads(path.with_name(lang["source_info"]).read_text(encoding="utf-8"))
        refresh_inline_names(info, lang, path.parent)
        items.extend({"file": Path(info["source"]).name, **line} for line in reviewed_lines(info, lang))
    counts = dict(Counter(item["check_status"] for item in items))
    report = {"format": "ballade-a5-layout-review-v1", "summary": counts, "lines": items}
    output = args.output or workspace / "ballade_a5_layout_review.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(f"A5 layout: {counts}; report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
