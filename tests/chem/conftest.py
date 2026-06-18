from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line("markers", "heavy: requires optional heavy dependencies")
