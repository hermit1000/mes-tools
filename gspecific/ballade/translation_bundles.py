"""Export and import ordered Ballade translation bundles."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from .speaker_groups import macro_id


FORMAT = "maria-translation-bundle-v1"
INVALID_SPEAKERS = {"ＤＥＢＵＧ！！！", "側", "筈", "陸"}
KEEP_ORIGINALS = {"Ｖ＝", "　Ｎ＝", "　　　　Ｘ＝"}
MENU_TRANSLATIONS = {
    "システム": "시스템",
    "セーブ": "저장",
    "ゲームを終了する": "게임 종료",
    "見る": "보기",
    "辺りの様子": "주변 상황",
    "話す": "대화하기",
    "聞く": "묻기",
    "考える": "생각하기",
    "移動する": "이동하기",
    "他の場所へ": "다른 장소로",
    "会話を終える": "대화 끝내기",
    "見せる": "보여주기",
    "電話する": "전화하기",
    "調べる": "조사하기",
    "未使用": "미사용",
    "ガイの事": "가이에 대해",
    "メリルの事": "메릴에 대해",
    "猟奇殺人事件の事": "엽기 살인 사건에 대해",
    "シンディの事": "신디에 대해",
    "ジェニファーの事": "제니퍼에 대해",
    "トニーの事": "토니에 대해",
    "クリスティの事": "크리스티에 대해",
    "グロリアの事": "글로리아에 대해",
    "ファーバー監督の事": "파버 감독에 대해",
    "エヴァの事": "에바에 대해",
    "ギュンターの事": "귄터에 대해",
    "監督の事": "감독에 대해",
    "仕事の事": "일에 대해",
    "ジニーの事": "지니에 대해",
    "記事の事": "기사에 대해",
    "撮影の事": "촬영에 대해",
    "パーティの事": "파티에 대해",
    "ガブリエラの事": "가브리엘라에 대해",
    "メリルの依頼の事": "메릴의 의뢰에 대해",
    "映画の事": "영화에 대해",
    "ティムの事": "팀에 대해",
    "依頼の事": "의뢰에 대해",
    "アリアナの事": "아리아나에 대해",
    "アンナの事": "안나에 대해",
}
SPEAKER_TRANSLATIONS = json.loads(
    Path(__file__).with_name("speaker_name_dictionary.json").read_text(encoding="utf-8")
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )


def menu_translation(original: str) -> str | None:
    if original == "　報告する　":
        return "보고한다"
    if "\n" in original or "\r" in original:
        return None
    translated = MENU_TRANSLATIONS.get(original.strip())
    if translated is None:
        return None
    left = len(original) - len(original.lstrip())
    right = len(original) - len(original.rstrip())
    return original[:left] + translated + (original[len(original) - right:] if right else "")


def is_special_glyph_only(original: str) -> bool:
    glyphs = original.strip()
    return bool(glyphs) and all(unicodedata.category(char) == "Co" for char in glyphs)


def active_body_offsets(info: dict, group: dict) -> set[str]:
    """Discard offsets accidentally captured after a dialogue end marker."""
    records = info["records"]
    start = next(
        (index for index, record in enumerate(records) if record["offset"] == group["id"].split(":", 1)[1]),
        None,
    )
    if start is None:
        raise ValueError(f"missing dialogue marker: {group['id']}")
    allowed = set(group["body_offsets"])
    result = set()
    for record in records[start + 1:]:
        called = macro_id(record, "BA")
        if record.get("type") == "end" or record.get("opcode") == "A6" or called in (18, 19):
            break
        if record.get("type") == "text" and record["offset"] in allowed:
            result.add(record["offset"])
    return result


def make_file(lang_path: Path) -> dict:
    lang = read_json(lang_path)
    if lang.get("format") != "maria-adv98-script-lang-v1":
        raise ValueError(f"unexpected lang format: {lang_path}")
    info = read_json(lang_path.with_name(lang["source_info"]))
    body_groups = {}
    speaker_offsets = set()
    for group in lang.get("speaker_groups", []):
        local_speaker = group.get("speaker_file", lang_path.name.removesuffix("_lang.json"))
        if (
            group["speaker_offset"] is not None
            and group["speaker"] not in INVALID_SPEAKERS
            and local_speaker == lang_path.name.removesuffix("_lang.json")
        ):
            speaker_offsets.add(group["speaker_offset"])
        for offset in active_body_offsets(info, group):
            if offset in body_groups:
                raise ValueError(f"multiple dialogue groups for {lang_path.name}:{offset}")
            body_groups[offset] = group

    items = []
    for entry in lang["entries"]:
        group = body_groups.get(entry["offset"])
        if group is not None:
            kind = "dialogue"
            group_id = group["id"]
        elif entry["offset"] in speaker_offsets:
            kind = "speaker_name"
            group_id = None
        else:
            kind = "other_text"
            group_id = None
        if kind == "dialogue" and items and items[-1]["kind"] == kind and items[-1]["dialogue_id"] == group_id:
            item = items[-1]
        else:
            item = {"kind": kind}
            if group is not None:
                item.update(
                    dialogue_id=group_id,
                    speaker=None if group["speaker"] in INVALID_SPEAKERS else group["speaker"],
                    speaker_translation=SPEAKER_TRANSLATIONS.get(group["speaker"]),
                    speaker_source=(
                        "invalid_label" if group["speaker"] in INVALID_SPEAKERS else group["speaker_source"]
                    ),
                    speaker_offset=group["speaker_offset"],
                )
                for key in ("speaker_file", "speaker_macro_id"):
                    if key in group:
                        item[key] = group[key]
            item["segments"] = []
            items.append(item)
        segment = {
            "id": entry["id"],
            "offset": entry["offset"],
            "original": entry["original"],
            "translation": entry.get("translation", ""),
        }
        if is_special_glyph_only(entry["original"]):
            segment["translation"] = "@keep"
            segment["pretranslation_source"] = "keep_rule"
            item["segments"].append(segment)
            continue
        if kind == "speaker_name":
            translated_name = SPEAKER_TRANSLATIONS.get(entry["original"])
            if translated_name is not None:
                if not segment["translation"]:
                    segment["translation"] = translated_name
                if segment["translation"] == translated_name:
                    segment["pretranslation_source"] = "speaker_dictionary"
        if kind == "other_text":
            if entry["original"] in KEEP_ORIGINALS:
                preliminary = "@keep"
                source = "keep_rule"
            else:
                preliminary = menu_translation(entry["original"])
                source = "menu_glossary"
            if preliminary is not None:
                if not segment["translation"]:
                    segment["translation"] = preliminary
                if segment["translation"] == preliminary:
                    segment["pretranslation_source"] = source
        item["segments"].append(segment)
    return {
        "source_file": lang_path.name,
        "source_info": lang["source_info"],
        "entry_count": len(lang["entries"]),
        "items": items,
    }


def partition(files: list[dict], count: int) -> list[list[dict]]:
    if count < 1 or count > len(files):
        raise ValueError(f"bundle count must be between 1 and {len(files)}")
    result = []
    index = 0
    remaining_entries = sum(file["entry_count"] for file in files)
    for number in range(count):
        remaining_bundles = count - number
        target = remaining_entries / remaining_bundles
        chunk = []
        chunk_entries = 0
        while index < len(files) - (remaining_bundles - 1):
            next_count = files[index]["entry_count"]
            if remaining_bundles > 1 and chunk and abs(target - chunk_entries) < abs(target - chunk_entries - next_count):
                break
            chunk.append(files[index])
            chunk_entries += next_count
            index += 1
        result.append(chunk)
        remaining_entries -= chunk_entries
    assert index == len(files)
    return result


def export(workspace: Path, output: Path, count: int, force: bool) -> tuple[int, int]:
    source = workspace / "script-pc98" / "MES"
    paths = sorted(source.glob("*_lang.json"))
    if not paths:
        raise FileNotFoundError(f"no lang JSON files under {source}")
    files = [make_file(path) for path in paths]
    bundles = partition(files, count)
    output.mkdir(parents=True, exist_ok=True)
    destinations = [output / f"bundle_{index:02d}.json" for index in range(1, count + 1)]
    existing = list(output.glob("bundle_*.json"))
    if existing and (not force or set(existing) != set(destinations)):
        raise FileExistsError(f"bundle files already exist or do not match the requested count: {output}")
    for index, (destination, chunk) in enumerate(zip(destinations, bundles), 1):
        write_json(destination, {"format": FORMAT, "bundle_index": index, "bundle_count": count, "files": chunk})
    return len(files), sum(file["entry_count"] for file in files)


def validate_bundle(bundle: dict, source: Path) -> list[tuple[Path, dict]]:
    if bundle.get("format") != FORMAT:
        raise ValueError("unexpected bundle format")
    changes = []
    for file in bundle["files"]:
        name = file["source_file"]
        if Path(name).name != name or not name.endswith("_lang.json"):
            raise ValueError(f"invalid source file name: {name}")
        path = source / name
        lang = read_json(path)
        if lang["source_info"] != file["source_info"]:
            raise ValueError(f"source info changed: {name}")
        segments = [segment for item in file["items"] for segment in item["segments"]]
        entries = lang["entries"]
        if len(entries) != file["entry_count"] or len(segments) != len(entries):
            raise ValueError(f"entry count changed: {name}")
        changed = False
        for segment, entry in zip(segments, entries):
            if (segment["id"], segment["offset"], segment["original"]) != (
                entry["id"], entry["offset"], entry["original"]
            ):
                raise ValueError(f"entry identity or order changed: {name}:{entry['id']}")
            translation = segment["translation"]
            if not isinstance(translation, str):
                raise ValueError(f"translation must be text: {name}:{entry['id']}")
            if not translation.strip():
                continue
            current = entry.get("translation", "")
            if current and current != translation:
                raise ValueError(f"existing translation differs: {name}:{entry['id']}")
            if current != translation:
                entry["translation"] = translation
                entry["status"] = "passed" if translation == "@keep" else "translated"
                changed = True
            elif translation == "@keep" and entry.get("status") != "passed":
                entry["status"] = "passed"
                changed = True
        if changed:
            changes.append((path, lang))
    return changes


def import_bundles(workspace: Path, inputs: list[Path], apply: bool) -> tuple[int, int]:
    source = workspace / "script-pc98" / "MES"
    changes = []
    seen = set()
    for path in inputs:
        bundle = read_json(path)
        for file in bundle["files"]:
            if file["source_file"] in seen:
                raise ValueError(f"duplicate source file: {file['source_file']}")
            seen.add(file["source_file"])
        changes.extend(validate_bundle(bundle, source))
    if apply:
        for path, lang in changes:
            write_json(path, lang)
    return len(changes), sum(
        sum(bool(entry.get("translation")) for entry in lang["entries"])
        for _, lang in changes
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--workspace", required=True, type=Path)
    exp.add_argument("--output", type=Path)
    exp.add_argument("--count", type=int, default=50)
    exp.add_argument("--force", action="store_true")
    imp = sub.add_parser("import")
    imp.add_argument("--workspace", required=True, type=Path)
    imp.add_argument("bundles", nargs="+", type=Path)
    imp.add_argument("--apply", action="store_true", help="write validated translations to lang JSON")
    args = parser.parse_args()
    if args.command == "export":
        workspace = args.workspace.resolve()
        output = args.output.resolve() if args.output else workspace / "translation_bundles"
        files, entries = export(workspace, output, args.count, args.force)
        print(f"exported {entries} entries from {files} lang files to {args.count} bundles: {output}")
    else:
        files, translated = import_bundles(args.workspace.resolve(), args.bundles, args.apply)
        print(f"{'updated' if args.apply else 'would update'} {files} lang files; translated entries in those files: {translated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
