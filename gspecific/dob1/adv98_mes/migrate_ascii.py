"""Preview DOB1 ASCII extraction changes and preserve matching translations."""

import argparse
from pathlib import Path

from modules.tools.migrate_ascii import run_migration
from .decode_mes import decode_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source_mes", "info_json", "lang_json", "output_dir"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    return run_migration("dob1", decode_document, args.source_mes, args.info_json,
                         args.lang_json, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
