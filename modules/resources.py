"""Paths to data distributed with the MES package."""

from pathlib import Path


def default_font_table() -> Path:
    return Path(__file__).resolve().parent / "data" / "font_table-kor-jin.json"
