"""Shared ADV98 MES decoding steps used by game adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .ascii import resolve_ascii_and_gaiji
from .mes_document import make_editable_records
from .mes_lexer import decode_mes as decode_lexical_mes, make_readable_records
from .tokens import make_token


def consume_selector_parameters(
    tokens: list[dict[str, Any]], data: bytes,
    controls: frozenset[str] = frozenset({"CONTROL_10", "CONTROL_12", "CONTROL_14"}),
) -> list[dict[str, Any]]:
    """Keep selector operands separate from visible text when a game uses them."""
    result: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if (
            token["type"] == "control"
            and token["value"] in controls
            and index + 3 < len(tokens)
            and tokens[index + 1]["value"] == "CONTROL_00"
            and tokens[index + 2]["type"] == "text"
            and tokens[index + 2]["size"] == 1
            and tokens[index + 3]["type"] == "text"
            and tokens[index + 3]["bytes"] == [0x81, 0x6D]
        ):
            start = token["offset"]
            result.append(make_token(
                start, 3, data[start:start + 3], "control", token["value"],
                parameters=list(data[start + 1:start + 3]),
            ))
            index += 3
            continue
        result.append(token)
        index += 1
    return result


def decode_mes(
    data: bytes,
    *,
    structured_ascii: bool = False,
    parameter_controls: tuple[int, ...] = (0x08, 0x0C, 0x0D, 0x19),
    transform_tokens: Callable[[list[dict[str, Any]], bytes], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    tokens = decode_lexical_mes(
        data, parameter_controls=parameter_controls, ascii_output=structured_ascii,
    )
    if transform_tokens is not None:
        tokens = transform_tokens(tokens, data)
    return resolve_ascii_and_gaiji(data, tokens)


def make_records(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return make_editable_records(tokens, make_readable_records)
