"""Record structural HD matches in Ballade CD translation JSON."""

import argparse
from collections import defaultdict
from pathlib import Path

from .common import Paths, read_json, write_json


def resolve_by_sequence(entries, hd_entries, hd_file):
    """Use the order between already matched entries only when it is unique."""
    positions = {entry["id"]: index for index, entry in enumerate(hd_entries)}
    anchors = [(index, positions[entry["hd_match"]["id"]])
               for index, entry in enumerate(entries) if "hd_match" in entry]
    anchors = [(-1, -1), *anchors, (len(entries), len(hd_entries))]
    resolved = 0
    for (cd_start, hd_start), (cd_end, hd_end) in zip(anchors, anchors[1:]):
        pending = [entry for entry in entries[cd_start + 1:cd_end]
                   if "hd_match_candidates" in entry]
        if not pending or hd_end <= hd_start:
            continue
        choices = [[candidate for candidate in entry["hd_match_candidates"]
                    if hd_start < positions[candidate] < hd_end]
                   for entry in pending]
        solutions = []

        def search(index, previous, chosen):
            if len(solutions) > 1:
                return
            if index == len(pending):
                solutions.append(chosen)
                return
            for candidate in choices[index]:
                if positions[candidate] > previous:
                    search(index + 1, positions[candidate], chosen + [candidate])

        search(0, hd_start, [])
        if len(solutions) != 1:
            continue
        for entry, candidate in zip(pending, solutions[0]):
            del entry["hd_match_candidates"]
            entry["hd_match"] = {
                "file": hd_file,
                "id": candidate,
                "basis": "original+raw_hex+sequence",
            }
            resolved += 1
    return resolved


def annotate(workspace: Path):
    paths = Paths(workspace.resolve())
    hd_root = paths.root / "script-pc98" / "MES"
    totals = {"files": 0, "matched": 0, "ambiguous": 0, "unmatched": 0}
    for cd_path in sorted(paths.scripts.rglob("*_lang.json")):
        name = cd_path.name[:-10]
        hd_path = hd_root / cd_path.name
        hd_info_path = hd_root / (name + "_info.json")
        cd_info_path = cd_path.with_name(name + "_info.json")
        if not hd_path.is_file() or not hd_info_path.is_file():
            continue
        hd = read_json(hd_path)
        cd = read_json(cd_path)
        hd_info = read_json(hd_info_path)
        cd_info = read_json(cd_info_path)
        hd_records = {record["offset"]: record for record in hd_info["records"]
                      if record.get("type") == "text"}
        cd_records = {record["offset"]: record for record in cd_info["records"]
                      if record.get("type") == "text"}
        donors = defaultdict(list)
        for entry in hd["entries"]:
            record = hd_records.get(entry["offset"])
            if record:
                donors[(entry["original"], record["raw_hex"])].append(entry)
        previous = [(entry.get("hd_match"), entry.get("hd_match_candidates"))
                    for entry in cd["entries"]]
        for entry in cd["entries"]:
            entry.pop("hd_match", None)
            entry.pop("hd_match_candidates", None)
            record = cd_records.get(entry["offset"])
            candidates = donors.get((entry["original"], record["raw_hex"]), []) if record else []
            exact_offset = [candidate for candidate in candidates
                            if candidate["offset"] == entry["offset"]]
            source = (exact_offset or candidates)
            if len(source) == 1:
                candidate = source[0]
                entry["hd_match"] = {
                    "file": hd_path.relative_to(paths.root).as_posix(),
                    "id": candidate["id"],
                    "basis": ("offset+original+raw_hex" if exact_offset
                              else "original+raw_hex"),
                }
                totals["matched"] += 1
            elif len(source) > 1:
                entry["hd_match_candidates"] = [candidate["id"] for candidate in source]
                totals["ambiguous"] += 1
            else:
                totals["unmatched"] += 1
        resolved = resolve_by_sequence(cd["entries"], hd["entries"],
                                       hd_path.relative_to(paths.root).as_posix())
        totals["matched"] += resolved
        totals["ambiguous"] -= resolved
        changed = previous != [(entry.get("hd_match"), entry.get("hd_match_candidates"))
                               for entry in cd["entries"]]
        if changed:
            write_json(cd_path, cd)
        totals["files"] += 1
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(annotate(args.workspace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
