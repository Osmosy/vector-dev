#!/usr/bin/env python3
"""Самопроверка чекера: все четыре кода выхода должны срабатывать.

Скопировать скелет во временный каталог, испортить по одному месту, прогнать чекер и сверить
код. Проверка ничего не меняет в репозитории: работает только на копиях.

Запуск: python3 examples/acceptance/selfcheck.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = Path(__file__).resolve().parent / "check_stage.py"
SKELETON = ROOT / "examples" / "project-skeleton"


def run(root: Path) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, str(CHECKER), "--root", str(root), "--json"],
                          capture_output=True, text=True)
    try:
        body = json.loads(done.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        body = {"problems": [f"чекер не вернул JSON: {done.stderr.strip()[:200]}"], "stats": {}}
    return done.returncode, body


def drop_address(copy: Path) -> None:
    path = copy / "registry" / "requirements.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["code_address"] = ""
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def touch_frozen(copy: Path) -> None:
    test = copy / "tests" / "test_app.py"
    test.write_text(test.read_text(encoding="utf-8") + "\n# правка замороженного теста\n", encoding="utf-8")


def drop_ramka(copy: Path) -> None:
    (copy / "RAMKA.md").unlink()


def fake_checker_hash(copy: Path) -> None:
    (copy / "acceptance" / "checker.sha256").write_text("0" * 64 + "  checker\n", encoding="utf-8")


SCENARIOS = [
    ("чисто", None, 0),
    ("требование без адреса в коде", drop_address, 1),
    ("изменён замороженный тест", touch_frozen, 1),
    ("нет RAMKA.md", drop_ramka, 2),
    ("подменённый чекер", fake_checker_hash, 3),
]


def main() -> int:
    failures = 0
    for name, mutate, expected in SCENARIOS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "project"
            shutil.copytree(SKELETON, copy)
            if mutate:
                mutate(copy)
            code, body = run(copy)
        ok = code == expected
        failures += 0 if ok else 1
        mark = "ок" if ok else "ПРОВАЛ"
        detail = "" if ok else f" — ждали {expected}, получили {code}: {body.get('problems')}"
        print(f"{mark}: {name} → {code}{detail}")
    print(f"сценариев: {len(SCENARIOS)}, провалов: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
