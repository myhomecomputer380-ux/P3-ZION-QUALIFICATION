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


def parse_and_validate(raw: bytes) -> dict[str, str]:
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
    except TypeError as exc:
        # Defensive: unexpected decoder callback failures.
        raise ValidationError("MALFORMED_JSON") from exc

    if not isinstance(data, dict):
        raise ValidationError("NOT_OBJECT")

    keys = set(data.keys())
    unknown = keys - REQUIRED_KEYS
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

    return {"ticket_id": ticket_id, "status": status}


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        result = parse_and_validate(raw)
    except ValidationError as exc:
        sys.stderr.write(exc.code + "\n")
        return 2

    # Deterministic key order: ticket_id then status; compact separators.
    sys.stdout.write(
        json.dumps(
            {"ticket_id": result["ticket_id"], "status": result["status"]},
            ensure_ascii=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
