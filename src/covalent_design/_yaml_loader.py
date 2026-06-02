"""Minimal YAML config loader for smoke configs.

Supports a small subset of YAML: comments (#), scalar values (str, int,
float, bool, null), and nested dicts via indentation.
"""

from __future__ import annotations


def load_yaml_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return _parse(text)


def _parse(text: str) -> dict:
    result: dict = {}
    stack: list[tuple[dict, int]] = [(result, -1)]

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n\r")
        if "#" in line:
            line = line[: line.index("#")]
        if not line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        content = line.strip()
        if ":" not in content:
            continue

        key, _, value_str = content.partition(":")
        key = key.strip()
        value_str = value_str.strip()

        while len(stack) > 1 and stack[-1][1] >= indent:
            stack.pop()

        parent_dict = stack[-1][0]

        if value_str == "":
            nested: dict = {}
            parent_dict[key] = nested
            stack.append((nested, indent))
        else:
            parent_dict[key] = _parse_scalar(value_str)

    return result


def _parse_scalar(s: str):
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.lower() == "null" or s.lower() == "~":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s
