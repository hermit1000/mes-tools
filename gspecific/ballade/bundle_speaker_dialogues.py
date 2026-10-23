"""Bundle Ballade dialogue after 201_6 for a smaller set of upload files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export_speaker_review import render_turns, write_markdown
from .speaker_groups import chapter_macros


CUTOFF = "201_6.MES"
MAX_BUNDLE_BYTES = 200_000
EMPTY_BODY = "[텍스트 없음: 원본 레코드 확인]"
INVALID_SPEAKERS = {"側", "筈", "陸"}


def render_bundle(number: int, sections: list[tuple[str, list[str]]]) -> str:
    header = (
        f"# Ballade 대사 묶음 {number:02d} — 201_6 이후\n\n"
        "원본 파일명과 오프셋을 각 줄에 표시했습니다. 화자 미확인 그룹과 본문이 없는 그룹은 제외했습니다. "
        "파일 순서는 실제 플레이 순서와 다를 수 있고 분기 대사도 포함됩니다.\n\n"
    )
    body = "\n\n".join(
        f"## {name} ({len(turns)}그룹)\n\n" + "\n".join(turns)
        for name, turns in sections
    )
    return header + body + "\n"


def byte_size(text: str) -> int:
    return len(text.replace("\n", "\r\n").encode("utf-8"))


def bundle(workspace: Path, *, force: bool = False) -> tuple[int, int, int]:
    source_root = workspace / "script-pc98" / "MES"
    info_paths = sorted(source_root.glob("*_info.json"))
    if not info_paths:
        raise FileNotFoundError(f"no info JSON files found under {source_root}")
    infos = [json.loads(path.read_text(encoding="utf-8")) for path in info_paths]
    catalog = chapter_macros(infos)
    sections: list[tuple[str, list[str]]] = []
    excluded_unknown = 0
    excluded_empty = 0
    excluded_debug = 0
    excluded_invalid = 0
    skipped_files = []

    for info in infos:
        name = Path(info["source"]).name
        if name <= CUTOFF:
            continue
        lang_path = source_root / f"{name}_lang.json"
        lang = json.loads(lang_path.read_text(encoding="utf-8"))
        groups = lang["speaker_groups"]
        turns = render_turns(info, lang, catalog)
        if len(turns) != len(groups):
            raise ValueError(f"speaker group count mismatch: {name}")
        kept = []
        for group, turn in zip(groups, turns):
            if group["speaker"] is None:
                excluded_unknown += 1
            elif group["speaker"] in INVALID_SPEAKERS:
                excluded_invalid += 1
            elif "ＤＥＢＵＧ" in group["speaker"] or "DEBUG" in group["speaker"].upper():
                excluded_debug += 1
            elif EMPTY_BODY in turn:
                excluded_empty += 1
            else:
                kept.append(turn.replace("- **dialogue:", f"- **{name}:", 1))
        if kept:
            sections.append((name, kept))
        elif groups:
            skipped_files.append(name)

    bundles: list[list[tuple[str, list[str]]]] = []
    current: list[tuple[str, list[str]]] = []
    for section in sections:
        proposed = current + [section]
        if current and byte_size(render_bundle(len(bundles) + 1, proposed)) > MAX_BUNDLE_BYTES:
            bundles.append(current)
            current = [section]
        else:
            current = proposed
        if byte_size(render_bundle(len(bundles) + 1, current)) > MAX_BUNDLE_BYTES:
            raise ValueError(f"source file exceeds bundle size limit: {section[0]}")
    if current:
        bundles.append(current)

    output_root = workspace / "speaker_dialogues_grouped_after_201_6"
    index_rows = []
    for number, parts in enumerate(bundles, 1):
        filename = f"bundle_{number:02d}.md"
        content = render_bundle(number, parts)
        write_markdown(output_root / filename, content, replace=force)
        index_rows.append(
            f"| [{filename}]({filename}) | {parts[0][0]} ~ {parts[-1][0]} | "
            f"{len(parts)} | {sum(len(turns) for _, turns in parts)} | {byte_size(content):,} |"
        )

    file_count = len(sections)
    group_count = sum(len(turns) for _, turns in sections)
    readme = (
        "# Ballade: 201_6 이후 업로드용 대사 묶음\n\n"
        f"`201_6.MES` 다음 파일부터 {file_count}개 원본 파일의 대사 {group_count}그룹을 "
        f"{len(bundles)}개 묶음으로 정리했습니다. "
        f"화자 미확인 {excluded_unknown}그룹, 잘못 읽힌 이름 {excluded_invalid}그룹, "
        f"디버그 {excluded_debug}그룹, "
        f"본문이 없는 {excluded_empty}그룹은 제외했습니다. "
        "기존 `speaker_dialogues/` 파일은 보존했습니다.\n\n"
        "| 업로드 파일 | 원본 범위 | 원본 파일 수 | 대사 그룹 | 크기 (바이트) |\n"
        "| --- | --- | ---: | ---: | ---: |\n"
        + "\n".join(index_rows)
        + "\n\n각 묶음 안의 `원본파일:오프셋`을 근거로 인용하세요. "
        "한 파일 안에서도 분기가 있으므로 모든 대사가 한 번의 플레이에서 이어지는 것은 아닙니다.\n"
    )
    if skipped_files:
        readme += "\n화자 미확인 대사만 있어 제외된 파일: " + ", ".join(skipped_files) + "\n"
    write_markdown(output_root / "README.md", readme, replace=force)
    return len(bundles), file_count, group_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--force", action="store_true", help="replace generated bundle files")
    args = parser.parse_args()
    bundles, files, groups = bundle(args.workspace.resolve(), force=args.force)
    print(f"wrote {bundles} bundles with {groups} dialogue groups from {files} source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
