# P3-ZION-QUALIFICATION

Depot factice dedie aux essais Q1-Q3 du cadre P3 v1.0, sans code ni donnees P1.

## Ticket JSON validator (Q1)

Minimal Python 3 standard-library tool: read one UTF-8 JSON object from stdin,
validate a synthetic ticket, print a canonical success object or a diagnostic code.

### Usage

```bash
python3 validate.py < input.json
# or
echo '{"ticket_id":"Q-001","status":"todo"}' | python3 validate.py
```

### Contract

Input must be a JSON object with exactly two keys:

| Field | Rule |
| --- | --- |
| `ticket_id` | ASCII string matching `Q-` + exactly three ASCII digits (`Q-000` … `Q-999`) |
| `status` | exactly `todo` or `done` (case-sensitive) |

**Valid input**

- Exit `0`
- stdout: one JSON object with keys in order `ticket_id` then `status`, compact separators (`","` / `":"`), single trailing newline
- stderr: empty

**Invalid input**

- Exit `2`
- stderr: one diagnostic code below, then a newline
- stdout: empty (no success object)

### Diagnostic codes

| Code | Meaning |
| --- | --- |
| `INVALID_UTF8` | stdin is not valid UTF-8 |
| `MALFORMED_JSON` | not valid JSON, or non-standard constants (`NaN` / `Infinity` / `-Infinity`) |
| `DUPLICATE_KEY` | duplicate object keys (including equal values) |
| `NOT_OBJECT` | top-level JSON value is not an object |
| `MISSING_FIELD` | `ticket_id` and/or `status` absent |
| `UNKNOWN_FIELD` | any key other than `ticket_id` / `status` |
| `INVALID_TICKET_ID` | wrong type or value for `ticket_id` |
| `INVALID_STATUS` | wrong type or value for `status` |

### Tests

```bash
python3 run_tests.py
```

The runner discovers `test_*.py`, fails if zero tests are found, and fails on any test error.

### CI

GitHub Actions workflow `.github/workflows/p3-tests.yml` defines the check/job `p3-tests` on `pull_request` (`opened`, `synchronize`, `reopened`, `edited`, `ready_for_review`) and optional `workflow_dispatch`.

Repository variable `P3_TEST_MODE` is a synthetic qualification fault switch only:

- empty / normal: run the test suite as usual
- `force_failure`: after tests succeed on the same SHA, force a real nonzero job failure (branch-protection diagnostic fixture; not a product feature)
