# P3-ZION-QUALIFICATION

Depot factice dedie aux essais Q1-Q3 du cadre P3 v1.0, sans code ni donnees P1.

## Ticket JSON validator (Q1/Q2)

Minimal Python 3 standard-library tool: read one UTF-8 JSON object from stdin,
validate a synthetic ticket, print a canonical success object or a diagnostic code.

### Usage

```bash
python3 validate.py < input.json
# or
echo '{"ticket_id":"Q-001","status":"todo"}' | python3 validate.py
```

### Contract

Input must be a JSON object with required keys `ticket_id` and `status`, and an
optional key `priority`:

| Field | Rule |
| --- | --- |
| `ticket_id` | ASCII string matching `Q-` + exactly three ASCII digits (`Q-000` … `Q-999`) |
| `status` | exactly `todo` or `done` (case-sensitive) |
| `priority` | optional; exact JSON integer `0`, `1`, or `2` only. JSON booleans `true` and `false` are rejected (`INVALID_PRIORITY`). |

When `priority` is absent, the success object is exactly the Q1 shape
(`ticket_id` then `status`). When present, keys are emitted in order
`ticket_id`, `status`, `priority`.

**Valid input**

- Exit `0`
- stdout: compact UTF-8/ASCII JSON with keys in the order above, separators (`","` / `":"`), exactly one trailing LF byte (`0x0A`); never CRLF
- stderr: empty

**Invalid input**

- Exit `2`
- stderr: one stable ASCII diagnostic code, then exactly one LF byte (`0x0A`); never CRLF
- stdout: empty (no success object, no traceback)

Decoder failures (malformed JSON, oversized numeric literals that raise `ValueError`, deep nesting `RecursionError`, non-standard `NaN`/`Infinity`) and incorrect field types all use exit `2` with a diagnostic — never an uncaught exception.

### Diagnostic codes

| Code | Meaning |
| --- | --- |
| `INVALID_UTF8` | stdin is not valid UTF-8 |
| `MALFORMED_JSON` | not valid JSON, decoder limits/errors, or non-standard constants (`NaN` / `Infinity` / `-Infinity`) |
| `DUPLICATE_KEY` | duplicate object keys (including equal values and escaped-equal keys) |
| `NOT_OBJECT` | top-level JSON value is not an object |
| `MISSING_FIELD` | `ticket_id` and/or `status` absent |
| `UNKNOWN_FIELD` | any key other than `ticket_id` / `status` / `priority` |
| `INVALID_TICKET_ID` | wrong type or value for `ticket_id` |
| `INVALID_STATUS` | wrong type or value for `status` |
| `INVALID_PRIORITY` | wrong type or value for `priority` (not an exact JSON integer in `{0,1,2}`; booleans rejected) |

### Tests

```bash
python3 run_tests.py
```

The runner discovers `test_*.py`, fails if zero tests are found, and fails on any test error. Assertions compare exact stdout/stderr bytes (including the single LF terminator) with no newline normalization.

### CI

GitHub Actions workflow `.github/workflows/p3-tests.yml` defines the required check/job `p3-tests` on `pull_request` (`opened`, `synchronize`, `reopened`, `edited`, `ready_for_review`) and optional `workflow_dispatch`, with `permissions: contents: read`.

The job runs on `windows-latest` with PowerShell so the suite exercises the exact-byte LF contract against Windows text-mode newline translation. Checkout uses a full-SHA-pinned `actions/checkout` with `persist-credentials: false`. Python from the runner PATH is used (no extra install step). The job runs `python run_tests.py` and propagates its exit code.

Repository variable `P3_TEST_MODE` is a synthetic qualification fault switch only (bound via step `env`, not interpolated into shell source):

- empty / normal: run the test suite as usual
- `force_failure`: after tests succeed on the same SHA, force a real nonzero job failure (branch-protection diagnostic fixture; not a product feature)

The App5177134 Codex verdict remains external to this workflow; there is no Actions substitute job for that verdict.
