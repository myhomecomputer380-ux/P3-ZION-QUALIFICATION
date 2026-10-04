#!/usr/bin/env python3
"""Discover and run tests; fail on zero tests or any failure."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT), pattern="test_*.py")
    count = suite.countTestCases()
    if count == 0:
        sys.stderr.buffer.write(b"DISCOVERY_ERROR: zero tests discovered\n")
        sys.stderr.buffer.flush()
        return 1

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
