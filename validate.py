#!/usr/bin/env python3
"""Validate a ticket JSON object from stdin (UTF-8)."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

TICKET_ID_RE = re.compile(r"^Q-[0-9]{3}$")
ALLOWED_STATUSES = frozenset({"todo", "done"})
REQUIRED_KEYS = frozenset({"ticket_id", "status"})
OPTIONAL_KEYS = frozenset({"priority"})
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
ALLOWED_PRIORITIES = frozenset({0, 1, 2})


class ValidationError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _reject_constant(value: str) -> Any:
    raise ValidationError("MALFORMED_JSON")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise ValidationError("DUPLICATE_KEY")
        seen.add(key)
    return dict(pairs)


def _write_stdout(data: bytes) -> None:
    """Write exact bytes to stdout (bypass text-mode newline translation)."""
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _write_stderr(data: bytes) -> None:
    """Write exact bytes to stderr (bypass text-mode newline translation)."""
    sys.stderr.buffer.write(data)
    sys.stderr.buffer.flush()


def parse_and_validate(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("INVALID_UTF8") from exc

    try:
        data = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_pairs,
        )
    except ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise ValidationError("MALFORMED_JSON") from exc
    except ValueError as exc:
        # Includes Python int-digit limits (e.g. 5000-digit literals) and
        # other decoder ValueErrors that are not JSONDecodeError subclasses
        # in all versions; JSONDecodeError itself is a ValueError subclass.
        raise ValidationError("MALFORMED_JSON") from exc
    except RecursionError as exc:
        # Deeply nested structures can overflow the decoder.
        raise ValidationError("MALFORMED_JSON") from exc
    except TypeError as exc:
        # Defensive: unexpected decoder callback failures.
        raise ValidationError("MALFORMED_JSON") from exc

    if not isinstance(data, dict):
        raise ValidationError("NOT_OBJECT")

    keys = set(data.keys())
    unknown = keys - ALLOWED_KEYS
    if unknown:
        raise ValidationError("UNKNOWN_FIELD")
    missing = REQUIRED_KEYS - keys
    if missing:
        raise ValidationError("MISSING_FIELD")

    ticket_id = data["ticket_id"]
    if not isinstance(ticket_id, str):
        raise ValidationError("INVALID_TICKET_ID")
    if not ticket_id.isascii() or TICKET_ID_RE.fullmatch(ticket_id) is None:
        raise ValidationError("INVALID_TICKET_ID")

    status = data["status"]
    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        raise ValidationError("INVALID_STATUS")

    result: dict[str, Any] = {"ticket_id": ticket_id, "status": status}

    if "priority" in data:
        priority = data["priority"]
        # Exact JSON integer only: bool subclasses int, so exclude with type().
        if type(priority) is not int or priority not in ALLOWED_PRIORITIES:
            raise ValidationError("INVALID_PRIORITY")
        result["priority"] = priority

    return result


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        result = parse_and_validate(raw)
    except ValidationError as exc:
        _write_stderr((exc.code + "\n").encode("ascii"))
        return 2

    # Deterministic key order: ticket_id, status, then priority when present;
    # compact separators. Exact trailing LF byte (0x0A); never CRLF via
    # text-mode translation.
    ordered: dict[str, Any] = {
        "ticket_id": result["ticket_id"],
        "status": result["status"],
    }
    if "priority" in result:
        ordered["priority"] = result["priority"]
    payload = (
        json.dumps(
            ordered,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    _write_stdout(payload.encode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
