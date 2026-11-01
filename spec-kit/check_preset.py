#!/usr/bin/env python3
"""Проверка пресета без внешних зависимостей: id, число шаблонов, наличие файлов.

Коды: 0 — пресет цел, 1 — находки, 2 — нет preset.yml.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "preset"
EXPECTED_ID = "vector-dev"
EXPECTED_TEMPLATES = 5


def main() -> int:
    manifest = ROOT / "preset.yml"
    if not manifest.is_file():
        print(f"нет {manifest}", file=sys.stderr)
        return 2
    text = manifest.read_text(encoding="utf-8")
    problems: list[str] = []

    m = re.search(r'^\s*id:\s*"([^"]+)"', text, re.M)
    if not m or m.group(1) != EXPECTED_ID:
        problems.append(f"id пресета не «{EXPECTED_ID}»: {m.group(1) if m else 'нет'}")

    files = re.findall(r'^\s*file:\s*"([^"]+)"', text, re.M)
    if len(files) != EXPECTED_TEMPLATES:
        problems.append(f"ждали {EXPECTED_TEMPLATES} шаблонов, в манифесте {len(files)}")
    missing = [f for f in files if not (ROOT / f).is_file()]
    if missing:
        problems.append(f"нет файлов шаблонов: {', '.join(missing)}")
    for name in files:
        if (ROOT / name).is_file() and not (ROOT / name).read_text(encoding="utf-8").strip():
            problems.append(f"пустой шаблон: {name}")

    for p in problems:
        print(f"НАХОДКА: {p}")
    print(f"шаблонов {len(files)}, находок {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
