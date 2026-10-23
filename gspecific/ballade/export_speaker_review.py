"""Export Ballade's speaker groups as pre-translation review material."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .speaker_groups import chapter_macros, macro_id


def write_markdown(path: Path, text: str, *, replace: bool = False) -> None:
    if path.exists() and not replace:
        raise FileExistsError(f"output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\r\n")


def table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def macro_name(
    number: int, local: dict[int, str], chapter: dict[int, list[tuple[str, dict]]]
) -> str | None:
    if number in local:
        return local[number]
    definitions = chapter.get(number, [])
    values = {record["original"] for _, record in definitions}
    return next(iter(values)) if len(values) == 1 else None


def render_turns(info: dict, lang: dict, catalog: dict) -> list[str]:
    records = info["records"]
    chapter = Path(info["source"]).name.split("_", 1)[0].split(".", 1)[0]
    chapter_names = catalog.get(chapter, {})
    groups = {group["id"].split(":", 1)[1]: group for group in lang["speaker_groups"]}
    local: dict[int, str] = {}
    lines = []
    for index, record in enumerate(records):
        definition = macro_id(record, "B9")
        if definition is not None:
            name = next(
                (item for item in records[index + 1:index + 3] if item.get("type") == "text"),
                None,
            )
            if name is not None:
                local[definition] = name["original"]
        group = groups.get(record["offset"])
        if group is None:
            continue
        parts = []
        for item in records[index + 1:]:
            called = macro_id(item, "BA")
            if item.get("type") == "end" or item.get("opcode") == "A6" or called in (18, 19):
                break
            if item.get("type") == "text":
                parts.append(item["original"])
            elif called is not None:
                name = macro_name(called, local, chapter_names)
                parts.append(f"{{이름:{name}}}" if name else f"{{매크로:{called}}}")
            elif item.get("value") == "CONTROL_A5":
                parts.append("⏎")
        speaker = group["speaker"] or (
            f"미확인(매크로 {group['speaker_macro_id']})"
            if "speaker_macro_id" in group else "미확인"
        )
        body = "".join(parts).strip() or "[텍스트 없음: 원본 레코드 확인]"
        lines.append(f"- **{group['id']} · {table_cell(speaker)}**: {body}")
    return lines


def export(workspace: Path, *, force: bool = False) -> tuple[int, int]:
    source_root = workspace / "script-pc98" / "MES"
    info_paths = sorted(source_root.glob("*_info.json"))
    if not info_paths:
        raise FileNotFoundError(f"no info JSON files found under {source_root}")
    infos = [json.loads(path.read_text(encoding="utf-8")) for path in info_paths]
    catalog = chapter_macros(infos)
    packet_root = workspace / "speaker_dialogues"
    roster: Counter[str] = Counter()
    files_by_speaker: defaultdict[str, set[str]] = defaultdict(set)
    first_group: dict[str, str] = {}
    index_rows = []
    total_groups = 0

    for info in infos:
        name = Path(info["source"]).name
        lang_path = source_root / f"{name}_lang.json"
        lang = json.loads(lang_path.read_text(encoding="utf-8"))
        turns = render_turns(info, lang, catalog)
        groups = lang["speaker_groups"]
        total_groups += len(groups)
        unresolved = sum(group["speaker"] is None for group in groups)
        for group in groups:
            speaker = group["speaker"]
            if speaker is None:
                continue
            roster[speaker] += 1
            files_by_speaker[speaker].add(name)
            first_group.setdefault(speaker, f"{name} {group['id']}")
        if not turns:
            continue
        packet = packet_root / f"{name}.md"
        write_markdown(
            packet,
            f"# {name}\n\n"
            "원본 파일 순서입니다. 분기 때문에 모든 줄이 한 번의 플레이에서 이어지지는 않습니다.\n\n"
            f"대사 그룹: {len(groups)}개 · 화자 미확인: {unresolved}개\n\n"
            + "\n".join(turns),
            replace=force,
        )
        index_rows.append(
            f"| [{name}](speaker_dialogues/{name}.md) | {len(groups)} | {unresolved} |"
        )


    roster_rows = [
        f"| {table_cell(name)} | {count} | {len(files_by_speaker[name])} | {first_group[name]} |"
        for name, count in roster.most_common()
    ]
    write_markdown(
        workspace / "speaker_roster.md",
        "# Ballade 화자 표시 목록\n\n"
        "같은 인물의 별칭일 수 있으며, 역할명도 포함된다. 관계와 동일인 여부는 아직 확정하지 않았다.\n\n"
        "| 원문 화자 표시 | 대사 그룹 수 | 등장 파일 수 | 첫 근거 |\n"
        "| --- | ---: | ---: | --- |\n" + "\n".join(roster_rows),
        replace=force,
    )
    write_markdown(
        workspace / "speaker_file_index.md",
        "# Ballade 대사 파일 목록\n\n"
        "| 원본 파일 | 대사 그룹 | 화자 미확인 |\n| --- | ---: | ---: |\n"
        + "\n".join(index_rows),
        replace=force,
    )
    write_markdown(
        workspace / "speaker_review_guide.md",
        "# Ballade 번역 전 화자 검토\n\n"
        f"원본 MES·MEC {len(infos)}개 중 대사가 있는 {len(index_rows)}개 파일에서 대사 그룹 {total_groups}개를 정리했다. "
        f"화자 표시 {len(roster)}종은 [화자 목록](speaker_roster.md)에 있다. "
        "[파일 목록](speaker_file_index.md)에서 장면별 원문을 선택한다.\n\n"
        "`speaker_dialogues/`는 원본 파일 순서이며 실제 플레이의 분기 순서나 대화 상대를 확정하지 않는다. "
        "`{이름:…}`은 원문 중간의 이름 매크로, `{매크로:번호}`는 해석하지 못한 매크로다. "
        "가이지와 비대사 명령은 대화문에서 생략했으므로 필요하면 `script-pc98/MES/*_info.json`을 확인한다.\n\n"
        "## ChatGPT 분석 요청문\n\n"
        "화자 목록과 한 장면의 대사 파일을 함께 제공하고 다음과 같이 요청한다.\n\n"
        "> 번역하지 말고, 화자별 나이대·호칭·말투·성격과 화자 간 관계 및 변화를 분석해 주세요. "
        "각 판단에 파일명과 `dialogue:오프셋` 근거를 붙여 주세요. "
        "화자 표시는 별칭이나 역할명일 수 있습니다. 인접 발화만으로 대화 상대를 단정하지 말고, "
        "나이와 성격은 명시 정보와 추정을 구분하고, 불확실한 내용은 추정 또는 미상으로 표시해 주세요. "
        "결과는 `speaker_relationships.md`와 `speaker_style.md`의 형식에 맞춰 제안해 주세요.\n\n"
        "장면별 분석을 검토해 [관계표](speaker_relationships.md)와 "
        "[말투표](speaker_style.md)를 채운 뒤, 번역할 때 해당 두 파일과 장면 파일을 함께 제공한다.\n",
        replace=force,
    )
    relationships = workspace / "speaker_relationships.md"
    if not relationships.exists():
        write_markdown(
            relationships,
            "# Ballade 화자 관계 검토표\n\n"
            "원문 대사 근거로만 채운다. 관계가 변하면 장면별 행을 추가한다.\n\n"
            "| 화자 A | 화자 B | 관계·호칭 | 근거 파일·그룹 | 확실성 | 메모 |\n"
            "| --- | --- | --- | --- | --- | --- |",
        )
    style = workspace / "speaker_style.md"
    if not style.exists():
        rows = [f"| {table_cell(name)} |  |  |  |  |  |  |  |  |" for name in roster]
        write_markdown(
            style,
            "# Ballade 화자별 말투 검토표\n\n"
            "번역 전에 원문 대사 근거로 채운다. 나이대와 성격은 명시된 사실인지 추정인지 구분한다. "
            "판단할 수 없으면 미상으로 둔다. 한 화자의 말투가 장면별로 달라지면 메모에 기록한다.\n\n"
            "| 화자 표시 | 나이·연령대 | 나이 근거 수준 | 자신을 부르는 말 | 상대 호칭 | 존댓말·말투 | 말투·성격 특징 | 근거 파일·그룹 | 메모 |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(rows),
        )
    return len(infos), total_groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--force", action="store_true", help="replace generated review files")
    args = parser.parse_args()
    files, groups = export(args.workspace.resolve(), force=args.force)
    print(f"exported {groups} dialogue groups from {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
