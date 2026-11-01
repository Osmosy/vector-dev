#!/usr/bin/env python3
"""Самопроверка чекера спецификаций: семь сценариев на временных копиях.

Смысл в том, что «всё зелёное» проверяется не верой: каждый сценарий ломает ровно одно
свойство спеки и ожидает конкретный код выхода и конкретную находку.

Коды выхода: 0 — все сценарии как ожидалось, 1 — есть расхождения.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check_spec.py"

SPEC = """# Спецификация: демо

**Ветка**: `001-demo` | **Создана**: 2026-11-02 | **Статус**: Draft

## Источники

| Адрес | Что это | Версия | sha256 | Дата |
|---|---|---|---|---|
| `research/note.md` | заметка | 1.0 | {h} | 2026-11-02 |

## Сценарии

### US-1 — демо (приоритет P1)

Что-то происходит.

## Требования

### REQ-0001 — первое требование

- **Приоритет**: P1
- **Источник**: `research/note.md:4`
- **Проверка**: `python3 acceptance/check.py --case one`
- **Вне зоны**: нет

### REQ-0002 — второе требование

- **Приоритет**: P2
- **Источник**: `research/note.md:9`
- **Проверка**: дано состояние, когда действие, тогда результат

## Вне зоны

- ничего

## Открытые вопросы

- [x] решено

## Что не проверено

- всё, что дальше
""".format(h="a" * 64)

PLAN = """# План: демо

## Карта требований

| REQ | Компонент | Контракт | Этап | Вентиль |
|---|---|---|---|---|
| REQ-0001 | модуль A | схема A | 1 | Г1 |
| REQ-0002 | модуль B | схема B | 2 | Г2 |
"""

TASKS = """# Задачи: демо

## Этап 1

- [ ] T-01 [REQ-0001] сделать A → проверка: `python3 acceptance/check.py`
- [ ] T-02 [REQ-0002] сделать B → проверка: `python3 acceptance/check.py`
"""

TASK_2 = "- [ ] T-02 [REQ-0002] сделать B → проверка: `python3 acceptance/check.py`\n"
CHECK_1 = "- **Проверка**: `python3 acceptance/check.py --case one`\n"
SOURCE_ROW = "| `research/note.md` | заметка | 1.0 | "


def build(root: Path, spec: str = SPEC, plan: str = PLAN, tasks: str = TASKS) -> Path:
    base = root / "specs" / "001-demo"
    base.mkdir(parents=True)
    (base / "spec.md").write_text(spec, encoding="utf-8")
    (base / "plan.md").write_text(plan, encoding="utf-8")
    (base / "tasks.md").write_text(tasks, encoding="utf-8")
    return root


def scenario(name: str, root: Path) -> None:
    if name == "чистая спека":
        build(root)
    elif name == "REQ без проверки":
        build(root, spec=SPEC.replace(CHECK_1, ""))
    elif name == "REQ не попал в задачи":
        build(root, tasks=TASKS.replace(TASK_2, ""))
    elif name == "задача на несуществующее REQ":
        build(root, tasks=TASKS + "- [ ] T-03 [REQ-0099] сделать C → проверка: `x`\n")
    elif name == "незаполненный шаблон":
        build(root, spec=SPEC.replace(SOURCE_ROW, "| [FEATURE NAME] | заметка | 1.0 | "))
    elif name == "нет spec.md":
        pass  # пустой каталог
    elif name == "подменённый чекер":
        build(root)
        (root / "acceptance").mkdir()
        (root / "acceptance" / "checker.sha256").write_text("0" * 64 + "  check_spec.py\n", encoding="utf-8")
    else:
        raise SystemExit(f"неизвестный сценарий {name}")


CASES = [
    ("чистая спека", 0, ""),
    ("REQ без проверки", 1, "без поля «Проверка»"),
    ("REQ не попал в задачи", 1, "не попал ни в одну задачу"),
    ("задача на несуществующее REQ", 1, "несуществующие требования"),
    ("незаполненный шаблон", 1, "плейсхолдеры"),
    ("нет spec.md", 2, "нет каталога"),
    ("подменённый чекер", 3, "подменена"),
]


def main() -> int:
    failures = 0
    for name, want_code, want_text in CASES:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            scenario(name, root)
            r = subprocess.run([sys.executable, str(CHECKER), "--root", str(root), "--json"],
                               capture_output=True, text=True)
        out = r.stdout + r.stderr
        ok = r.returncode == want_code and (not want_text or want_text in out)
        print(f"{'ok  ' if ok else 'FAIL'} {name}: код {r.returncode} (ждали {want_code})")
        if not ok:
            failures += 1
            print("      вывод:", out.strip().replace("\n", " ")[:300])

    print(f"сценариев {len(CASES)}, расхождений {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
