"""Encode CD MES/MEC resources, then rebuild the original CD containers."""

import argparse
from pathlib import Path

from gspecific.ballade.encode_mes import DEFAULT_FONT_TABLE, encode_file
from .common import Paths, read_json, selected, write_json
from .containers import repack
from .runtime import deploy


DEFAULT_COMPACT_REMAP = Path(__file__).resolve().parents[1] / "maria_compact_font_mapping_top67.json"
DEFAULT_FILES = []  # Empty: all CD MES/MEC resources.


def encode_cd(workspace: Path, names=None, *, font_table=DEFAULT_FONT_TABLE,
              compact_remap=DEFAULT_COMPACT_REMAP, dry_run=False, repack_cd=True):
    paths = Paths(workspace.resolve())
    manifest = read_json(paths.unpacked / "container-manifest.json")
    resources = [Path(entry["unpacked_path"])
                 for container in manifest["containers"] for entry in container["entries"]
                 if Path(entry["name"]).suffix.upper() in {".MES", ".MEC"}]
    selected_resources = [relative for relative in resources if selected(relative, names)]
    if not selected_resources:
        raise ValueError("no matching CD MES/MEC resources")
    results = []
    for relative in selected_resources:
        source = paths.unpacked / relative
        directory = paths.scripts / relative.parent
        info = directory / f"{relative.name}_info.json"
        lang = directory / f"{relative.name}_lang.json"
        output = paths.korean_unpacked / relative
        fallback = []
        try:
            count, size = encode_file(source, info, lang, None if dry_run else output,
                                      font_table, compact_remap=compact_remap,
                                      mec_original_fallbacks=fallback)
            results.append({"file": relative.as_posix(), "status": "validated" if dry_run else "encoded",
                            "replacements": count, "encoded_size": size,
                            "mec_original_fallbacks": fallback})
            print(f"OK {relative}: {count} replacements, {size} bytes"
                  + (f"; {len(fallback)} MEC records kept original" if fallback else ""))
        except (OSError, ValueError, KeyError) as error:
            results.append({"file": relative.as_posix(), "status": "failed", "error": str(error)})
            print(f"FAIL {relative}: {error}")
    if not dry_run and repack_cd:
        repack(paths.original, paths.korean_unpacked, paths.korean, manifest)
        deploy(paths.root)
    report = {"format": "ballade-cd-encode-report-v1", "source": str(paths.original),
              "selected": len(selected_resources), "failed": sum(r["status"] == "failed" for r in results),
              "files": results}
    if not dry_run:
        write_json(paths.korean / "encode_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--files", nargs="+", help="MES/MEC basenames or container-relative paths")
    parser.add_argument("--font-table", type=Path, default=DEFAULT_FONT_TABLE)
    parser.add_argument("--compact-remap", type=Path, default=DEFAULT_COMPACT_REMAP)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-repack", action="store_true")
    args = parser.parse_args()
    report = encode_cd(args.workspace, args.files if args.files is not None else DEFAULT_FILES,
                       font_table=args.font_table, compact_remap=args.compact_remap,
                       dry_run=args.dry_run, repack_cd=not args.no_repack)
    print(f"validated: {report['selected']}; failed: {report['failed']}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
