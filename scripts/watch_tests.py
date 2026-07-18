#!/usr/bin/env python3
"""
Watch the repository for file changes and run pytest automatically.

Usage: python scripts/watch_tests.py
"""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestRunner:
    def __init__(self):
        self._timer = None
        self._lock = threading.Lock()

    def schedule(self, delay: float = 0.4):
        with self._lock:
            if self._timer and self._timer.is_alive():
                self._timer.cancel()
            self._timer = threading.Timer(delay, self.run_tests)
            self._timer.daemon = True
            self._timer.start()

    def run_tests(self):
        print("\n[watch_tests] Detected changes — running tests...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        env["DATABASE_URL"] = env.get("DATABASE_URL", "sqlite:///:memory:")

        proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], env=env)
        print(f"[watch_tests] pytest exit code: {proc.returncode}")


def main():
    patterns = ["*.py", "*.html", "*.md", "*.yml", "*.yaml", "*.json"]
    ignore_patterns = ["*/.git/*", "*/__pycache__/*", "*/.venv/*"]

    runner = TestRunner()

    handler = PatternMatchingEventHandler(
        patterns=patterns,
        ignore_patterns=ignore_patterns,
        ignore_directories=False,
        case_sensitive=False,
    )

    def on_change(event):
        print(f"[watch_tests] {event.event_type}: {event.src_path}")
        runner.schedule()

    handler.on_created = on_change
    handler.on_modified = on_change
    handler.on_moved = on_change
    handler.on_deleted = on_change

    observer = Observer()
    observer.schedule(handler, str(PROJECT_ROOT), recursive=True)
    observer.start()

    print("[watch_tests] Watching for changes. Press Ctrl+C to stop.")
    try:
        # initial run
        runner.run_tests()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[watch_tests] Stopping observer...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
