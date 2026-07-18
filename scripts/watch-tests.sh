#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=. DATABASE_URL=sqlite:///:memory: python3 scripts/watch_tests.py
