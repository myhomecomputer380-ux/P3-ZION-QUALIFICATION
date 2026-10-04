#!/usr/bin/env python3
"""CLI and contract tests for validate.py."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE = ROOT / "validate.py"


def run_cli(payload: bytes | str) -> subprocess.CompletedProcess[bytes]:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return subprocess.run(
        [sys.executable, str(VALIDATE)],
        input=payload,
        capture_output=True,
    )


class ValidInputTests(unittest.TestCase):
    def test_valid_todo(self) -> None:
        proc = run_cli('{"ticket_id":"Q-001","status":"todo"}')
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(proc.stdout, b'{"ticket_id":"Q-001","status":"todo"}\n')

    def test_valid_done(self) -> None:
        proc = run_cli('{"status":"done","ticket_id":"Q-042"}')
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(proc.stdout, b'{"ticket_id":"Q-042","status":"done"}\n')

    def test_boundary_ticket_ids(self) -> None:
        for ticket_id in ("Q-000", "Q-999"):
            with self.subTest(ticket_id=ticket_id):
                payload = json.dumps(
                    {"ticket_id": ticket_id, "status": "todo"},
                    separators=(",", ":"),
                )
                proc = run_cli(payload)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stderr, b"")
                self.assertEqual(
                    proc.stdout,
                    f'{{"ticket_id":"{ticket_id}","status":"todo"}}\n'.encode(),
                )


class RejectionTests(unittest.TestCase):
    def assert_rejects(self, payload: bytes | str, code: str) -> None:
        proc = run_cli(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(proc.stderr, (code + "\n").encode())

    def test_malformed_json(self) -> None:
        self.assert_rejects("{", "MALFORMED_JSON")
        self.assert_rejects("", "MALFORMED_JSON")
        self.assert_rejects("null", "NOT_OBJECT")

    def test_reject_nan_infinity(self) -> None:
        self.assert_rejects("NaN", "MALFORMED_JSON")
        self.assert_rejects("Infinity", "MALFORMED_JSON")
        self.assert_rejects("-Infinity", "MALFORMED_JSON")
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":NaN}',
            "MALFORMED_JSON",
        )

    def test_duplicate_keys(self) -> None:
        self.assert_rejects(
            '{"ticket_id":"Q-001","ticket_id":"Q-001","status":"todo"}',
            "DUPLICATE_KEY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","status":"todo"}',
            "DUPLICATE_KEY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","status":"done"}',
            "DUPLICATE_KEY",
        )

    def test_missing_field(self) -> None:
        self.assert_rejects('{"ticket_id":"Q-001"}', "MISSING_FIELD")
        self.assert_rejects('{"status":"todo"}', "MISSING_FIELD")
        self.assert_rejects("{}", "MISSING_FIELD")

    def test_unknown_field(self) -> None:
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","extra":1}',
            "UNKNOWN_FIELD",
        )

    def test_wrong_top_level_type(self) -> None:
        self.assert_rejects('["Q-001","todo"]', "NOT_OBJECT")
        self.assert_rejects('"Q-001"', "NOT_OBJECT")
        self.assert_rejects("1", "NOT_OBJECT")
        self.assert_rejects("true", "NOT_OBJECT")

    def test_wrong_field_types(self) -> None:
        self.assert_rejects(
            '{"ticket_id":1,"status":"todo"}',
            "INVALID_TICKET_ID",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":true}',
            "INVALID_STATUS",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":0}',
            "INVALID_STATUS",
        )

    def test_forbidden_status_values(self) -> None:
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"Todo"}',
            "INVALID_STATUS",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"DONE"}',
            "INVALID_STATUS",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"pending"}',
            "INVALID_STATUS",
        )

    def test_invalid_ticket_id_shapes(self) -> None:
        for ticket_id in ("Q-00", "Q-0000", "Q-00A", "q-001", "Q001", "Q-1"):
            with self.subTest(ticket_id=ticket_id):
                self.assert_rejects(
                    json.dumps({"ticket_id": ticket_id, "status": "todo"}),
                    "INVALID_TICKET_ID",
                )

    def test_unicode_digits_rejected(self) -> None:
        # Arabic-Indic digits must not satisfy the ASCII digit contract.
        self.assert_rejects(
            '{"ticket_id":"Q-\u0660\u0660\u0661","status":"todo"}',
            "INVALID_TICKET_ID",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-\uff10\uff10\uff11","status":"todo"}',
            "INVALID_TICKET_ID",
        )

    def test_invalid_utf8(self) -> None:
        self.assert_rejects(b"\xff\xfe{" , "INVALID_UTF8")
        self.assert_rejects(b'{"ticket_id":"Q-001","status":"todo"\xff}', "INVALID_UTF8")


if __name__ == "__main__":
    unittest.main()
