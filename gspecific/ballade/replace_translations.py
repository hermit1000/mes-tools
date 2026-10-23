"""Replace literal strings in Ballade lang translations, with preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_WORKSPACE = Path(r"C:\work_han\workspace4")
# (찾을 문자열, 바꿀 문자열). 위에서 아래로 순서대로 적용한다.
REPLACEMENTS = [
    (".……", "……"),
]


def plan_updates(
    root: Path, replacements: list[tuple[str, str]]
) -> tuple[list[tuple[Path, dict]], int]:
    paths = sorted(root.rglob("*_lang.json"))
    if not paths:
        raise ValueError(f"no *_lang.json files found under {root}")
    updates = []
    total = 0
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("format") != "maria-adv98-script-lang-v1":
            raise ValueError(f"unexpected lang format: {path}")
        changed = False
        for entry in document["entries"]:
            current = entry.get("translation", "")
            if not isinstance(current, str):
                raise ValueError(f"translation is not text: {path}:{entry.get('id')}")
            if not current or current == "@keep":
                continue
            updated = current
            for old, new in replacements:
                updated = updated.replace(old, new)
            if updated != current:
                entry["translation"] = updated
                changed = True
                total += 1
                print(
                    f"{path.relative_to(root)}:{entry.get('id', entry.get('offset'))}: "
                    f"{json.dumps(current, ensure_ascii=False)} -> {json.dumps(updated, ensure_ascii=False)}"
                )
        if changed:
            updates.append((path, document))
    return updates, total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument(
        "--lang-dir", type=Path, help="default: workspace/script-pc98/MES"
    )
    parser.add_argument(
        "--replace",
        nargs=2,
        action="append",
        metavar=("OLD", "NEW"),
        help="override REPLACEMENTS; repeat to apply rules in argument order",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without writing; default: write",
    )
    args = parser.parse_args()
    replacements = args.replace if args.replace is not None else REPLACEMENTS
    if any(not old for old, _ in replacements):
        parser.error("OLD must not be empty")
    workspace = args.workspace.resolve()
    root = (args.lang_dir or workspace / "script-pc98/MES").resolve()
    try:
        updates, total = plan_updates(root, replacements)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(
        f"{'preview' if args.dry_run else 'apply'}: {len(updates)} files, {total} translations"
    )
    if not args.dry_run and updates:
        for path, document in updates:
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\r\n",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
