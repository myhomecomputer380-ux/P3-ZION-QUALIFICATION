#!/usr/bin/env python3
"""CLI and contract tests for validate.py."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import validate

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
        self.assertFalse(proc.stdout.endswith(b"\r\n"))
        self.assertTrue(proc.stdout.endswith(b"\n"))

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

    def test_priority_absent_keeps_q1_shape(self) -> None:
        proc = run_cli('{"ticket_id":"Q-001","status":"todo"}')
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(proc.stdout, b'{"ticket_id":"Q-001","status":"todo"}\n')

    def test_priority_integers(self) -> None:
        for priority in (0, 1, 2):
            with self.subTest(priority=priority):
                payload = (
                    f'{{"ticket_id":"Q-001","status":"todo","priority":{priority}}}'
                )
                proc = run_cli(payload)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stderr, b"")
                self.assertEqual(
                    proc.stdout,
                    (
                        f'{{"ticket_id":"Q-001","status":"todo","priority":{priority}}}'
                        + "\n"
                    ).encode(),
                )

    def test_priority_key_order_normalized(self) -> None:
        proc = run_cli('{"priority":2,"status":"done","ticket_id":"Q-007"}')
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(
            proc.stdout,
            b'{"ticket_id":"Q-007","status":"done","priority":2}\n',
        )


class RejectionTests(unittest.TestCase):
    def assert_rejects(self, payload: bytes | str, code: str) -> None:
        proc = run_cli(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        expected = (code + "\n").encode("ascii")
        self.assertEqual(proc.stderr, expected)
        self.assertFalse(proc.stderr.endswith(b"\r\n"))
        self.assertTrue(proc.stderr.endswith(b"\n"))

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

    def test_escaped_duplicate_keys(self) -> None:
        # \u0074icket_id decodes to ticket_id — must still be DUPLICATE_KEY.
        self.assert_rejects(
            '{"ticket_id":"Q-001","\\u0074icket_id":"Q-002","status":"todo"}',
            "DUPLICATE_KEY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","stat\\u0075s":"done"}',
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

    def test_invalid_priority_values(self) -> None:
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","priority":3}',
            "INVALID_PRIORITY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","priority":-1}',
            "INVALID_PRIORITY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","priority":"1"}',
            "INVALID_PRIORITY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","priority":1.0}',
            "INVALID_PRIORITY",
        )
        self.assert_rejects(
            '{"ticket_id":"Q-001","status":"todo","priority":null}',
            "INVALID_PRIORITY",
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
        self.assert_rejects(b"\xff\xfe{", "INVALID_UTF8")
        self.assert_rejects(
            b'{"ticket_id":"Q-001","status":"todo"\xff}',
            "INVALID_UTF8",
        )

    def test_oversized_json_integer_stable_reject(self) -> None:
        # Exact Codex blocker case: 5000-digit integer must not escape as
        # ValueError/traceback (exit 1); must be exit 2 + diagnostic + empty stdout.
        payload = ('{"ticket_id":' + "1" * 5000 + ',"status":"todo"}').encode("ascii")
        proc = run_cli(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(proc.stderr, b"MALFORMED_JSON\n")
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertNotIn(b"ValueError", proc.stderr)

    def test_deeply_nested_json_stable_reject(self) -> None:
        # Deep decoder RecursionError must map to stable exit 2, not traceback.
        payload = ("[" * 100000 + "]" * 100000).encode("ascii")
        proc = run_cli(payload)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertEqual(proc.stderr, b"MALFORMED_JSON\n")
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertNotIn(b"RecursionError", proc.stderr)


class ExactByteNewlineTests(unittest.TestCase):
    """Regression: text-mode write translates LF→CRLF on Windows.

    Simulates that translation on any platform by wrapping stdout/stderr in
    TextIOWrapper(newline='\\r\\n'). Writing via .buffer must keep a single LF.
    These assertions fail on the original sys.stdout.write / sys.stderr.write
    implementation without normalizing actual CLI subprocess output.
    """

    def _run_main_with_crlf_text_wrappers(
        self, stdin_bytes: bytes
    ) -> tuple[int, bytes, bytes]:
        in_raw = io.BytesIO(stdin_bytes)
        out_raw = io.BytesIO()
        err_raw = io.BytesIO()
        stdin = io.TextIOWrapper(in_raw, encoding="utf-8", newline="")
        stdout = io.TextIOWrapper(
            out_raw, encoding="utf-8", newline="\r\n", write_through=True
        )
        stderr = io.TextIOWrapper(
            err_raw, encoding="utf-8", newline="\r\n", write_through=True
        )
        with (
            mock.patch.object(validate.sys, "stdin", stdin),
            mock.patch.object(validate.sys, "stdout", stdout),
            mock.patch.object(validate.sys, "stderr", stderr),
        ):
            code = validate.main()
        stdout.flush()
        stderr.flush()
        return code, out_raw.getvalue(), err_raw.getvalue()

    def test_success_exact_lf_under_crlf_text_mode(self) -> None:
        code, out, err = self._run_main_with_crlf_text_wrappers(
            b'{"ticket_id":"Q-001","status":"todo"}'
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, b"")
        self.assertEqual(out, b'{"ticket_id":"Q-001","status":"todo"}\n')
        self.assertNotIn(b"\r", out)

    def test_rejection_exact_lf_under_crlf_text_mode(self) -> None:
        code, out, err = self._run_main_with_crlf_text_wrappers(b"{")
        self.assertEqual(code, 2)
        self.assertEqual(out, b"")
        self.assertEqual(err, b"MALFORMED_JSON\n")
        self.assertNotIn(b"\r", err)


class RunTestsRunnerTests(unittest.TestCase):
    def test_zero_discovery_exits_nonzero(self) -> None:
        import run_tests

        empty = unittest.TestSuite()
        err = io.BytesIO()
        fake_stderr = mock.Mock()
        fake_stderr.buffer = err
        with (
            mock.patch.object(unittest.TestLoader, "discover", return_value=empty),
            mock.patch.object(run_tests.sys, "stderr", fake_stderr),
        ):
            self.assertEqual(run_tests.main(), 1)
        self.assertEqual(err.getvalue(), b"DISCOVERY_ERROR: zero tests discovered\n")

    def test_runner_nonzero_on_test_failure(self) -> None:
        import run_tests

        class Boom(unittest.TestCase):
            def test_boom(self) -> None:
                self.fail("synthetic failure")

        suite = unittest.TestSuite([Boom("test_boom")])
        with (
            mock.patch.object(unittest.TestLoader, "discover", return_value=suite),
            mock.patch("sys.stderr", new=io.StringIO()),
            mock.patch("sys.stdout", new=io.StringIO()),
        ):
            self.assertEqual(run_tests.main(), 1)


if __name__ == "__main__":
    unittest.main()
