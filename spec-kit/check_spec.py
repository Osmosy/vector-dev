#!/usr/bin/env python3
"""Чекер спецификации: приёмка документов spec → plan → tasks до первой строки кода.

Отвечает на вопросы, которые в наших правилах называются вентилями Г3 и Г4:

  Q1 у каждого требования уникальный код вида REQ-0001?
  Q2 у каждого требования есть источник (адрес) и приоритет?
  Q3 у каждого требования есть фальсифицируемая проверка (не «работает хорошо»)?
  Q4 каждое требование попало в план?
  Q5 каждое требование попало хотя бы в одну задачу?
  Q6 нет задач, ссылающихся на несуществующее требование?
  Q7 не осталось незаполненных плейсхолдеров шаблона?
  Q8 источники в таблице имеют sha256 и дату?

Коды выхода:
  0 — принято
  1 — блокирующие находки
  2 — плохой вход (нет spec.md / plan.md / tasks.md)
  3 — отказ запускать (подменён чекер)

Только stdlib. Проверка ничего не меняет — только отчитывается.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REQ_ID = re.compile(r"\bREQ-\d{4}\b")
TASK_LINE = re.compile(r"^\s*[-*]\s*\[[ xX]\]\s*T-\d+", re.M)
PLACEHOLDERS = [
    "[FEATURE NAME]", "[DATE]", "[PROJECT_NAME]", "<название>", "<описание>",
    "<адрес>", "<команда>", "TODO", "TBD", "{CORE_TEMPLATE}",
]
VAGUE = ["работает хорошо", "как ожидается", "стабильно", "быстро", "удобно", "качественно"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sections(text: str, title: str) -> str:
    """Тело раздела с заголовком `title` (до следующего заголовка того же уровня)."""
    m = re.search(rf"^#+\s*{re.escape(title)}.*$", text, re.M | re.I)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^#{1,3}\s", text[start:], re.M)
    return text[start:start + nxt.start()] if nxt else text[start:]


def requirements(text: str) -> dict[str, dict[str, str]]:
    """Блоки требований: `### REQ-0001 …` и строки `- Ключ: значение` внутри."""
    found: dict[str, dict[str, str]] = {}
    blocks = re.split(r"^###\s+", text, flags=re.M)
    for block in blocks:
        head = block.splitlines()[0] if block.strip() else ""
        m = REQ_ID.match(head.strip())
        if not m:
            continue
        fields: dict[str, str] = {}
        for line in block.splitlines()[1:]:
            fm = re.match(r"\s*[-*]\s*([^:]+):\s*(.*)$", line)
            if fm:
                key = re.sub(r"[*_`]", "", fm.group(1)).strip().lower()
                fields[key] = fm.group(2).strip()
        found[m.group(0)] = fields
    return found


def source_rows(text: str) -> list[list[str]]:
    body = sections(text, "Источники")
    rows: list[list[str]] = []
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if cells[0].lower().startswith(("адрес", "источник")):
            continue
        rows.append(cells)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Приёмка спецификации до кода.")
    parser.add_argument("--root", default=".", help="корень проекта")
    parser.add_argument("--specs", default="specs", help="каталог со спеками (по умолчанию specs)")
    parser.add_argument("--feature", help="конкретная спека (каталог внутри specs)")
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    specs_dir = root / args.specs

    def done(code: int, problems: list[str], counts: dict) -> int:
        if args.json:
            print(json.dumps({"ok": code == 0, "code": code, "problems": problems, **counts},
                             ensure_ascii=False, indent=1))
        else:
            for p in problems:
                print(f"НАХОДКА: {p}")
            print(f"итог: код {code}, находок {len(problems)}")
        return code

    # --- 3: подменённый чекер ---------------------------------------------
    ref = root / "acceptance" / "checker.sha256"
    if ref.is_file():
        expected = ref.read_text(encoding="utf-8").split()[0]
        if sha256(Path(__file__).resolve()) != expected:
            return done(3, ["sha256 чекера не совпадает с эталоном — проверка подменена"], {})

    # --- 2: плохой вход ----------------------------------------------------
    if not specs_dir.is_dir():
        return done(2, [f"нет каталога {specs_dir.relative_to(root)}/ — сначала /speckit-specify"], {})
    features = [args.feature] if args.feature else sorted(
        p.name for p in specs_dir.iterdir() if p.is_dir() and (p / "spec.md").is_file())
    if not features:
        return done(2, ["в specs/ нет ни одной спеки с spec.md"], {})

    problems: list[str] = []
    all_reqs: dict[str, int] = {}

    for feature in features:
        base = specs_dir / feature
        spec_path, plan_path, tasks_path = base / "spec.md", base / "plan.md", base / "tasks.md"
        if not spec_path.is_file():
            problems.append(f"{feature}: нет spec.md")
            continue
        spec = read(spec_path)
        if not plan_path.is_file():
            problems.append(f"{feature}: нет plan.md — план не выводился из спеки")
        if not tasks_path.is_file():
            problems.append(f"{feature}: нет tasks.md — задачи не выводились из плана")
        plan = read(plan_path) if plan_path.is_file() else ""
        tasks = read(tasks_path) if tasks_path.is_file() else ""

        # Q7: незаполненные плейсхолдеры
        for name, text in (("spec.md", spec), ("plan.md", plan), ("tasks.md", tasks)):
            left = [ph for ph in PLACEHOLDERS if ph in text]
            if left:
                problems.append(f"{feature}/{name}: не заполнены плейсхолдеры шаблона: "
                                f"{', '.join(left[:4])}")

        reqs = requirements(spec)
        if not reqs:
            problems.append(f"{feature}/spec.md: нет ни одного требования вида «### REQ-0001 …»")
        all_reqs[feature] = len(reqs)

        headings = re.findall(r"^###\s+(REQ-\d{4})", spec, re.M)
        duplicates = sorted({h for h in headings if headings.count(h) > 1})
        if duplicates:
            problems.append(f"{feature}/spec.md: повторяются коды требований: {', '.join(duplicates)}")

        for req_id, fields in reqs.items():
            # Q2: источник и приоритет
            if not fields.get("источник"):
                problems.append(f"{feature}: {req_id} без поля «Источник» — требование из воздуха")
            if not fields.get("приоритет"):
                problems.append(f"{feature}: {req_id} без поля «Приоритет»")
            # Q3: проверка
            check = fields.get("проверка", "")
            if not check:
                problems.append(f"{feature}: {req_id} без поля «Проверка» — нечем принимать")
            elif any(v in check.lower() for v in VAGUE):
                problems.append(f"{feature}: {req_id}: проверка не фальсифицируема "
                                f"(«{check[:40]}») — нужна команда, число или Given/When/Then")
            # Q4/Q5: план и задачи
            if plan and req_id not in plan:
                problems.append(f"{feature}: {req_id} отсутствует в plan.md")
            if tasks and req_id not in tasks:
                problems.append(f"{feature}: {req_id} не попал ни в одну задачу tasks.md")

        # Q6: задачи на несуществующие требования
        task_reqs = set(REQ_ID.findall(tasks))
        orphan = sorted(task_reqs - set(reqs))
        if orphan:
            problems.append(f"{feature}: задачи ссылаются на несуществующие требования: "
                            f"{', '.join(orphan[:5])}")
        if tasks and not TASK_LINE.search(tasks):
            problems.append(f"{feature}/tasks.md: нет ни одной задачи формата «- [ ] T-01 [REQ-0001] …»")

        # Q8: источники с хэшем и датой
        rows = source_rows(spec)
        if not rows:
            problems.append(f"{feature}/spec.md: нет таблицы «Источники» — ground truth не зафиксирован")
        for row in rows:
            joined = " ".join(row)
            if not re.search(r"\b[0-9a-f]{64}\b", joined):
                problems.append(f"{feature}/spec.md: у источника «{row[0][:40]}» нет sha256")
            if not re.search(r"\b\d{4}-\d{2}-\d{2}\b", joined):
                problems.append(f"{feature}/spec.md: у источника «{row[0][:40]}» нет даты")

    counts = {"features": len(features), "requirements": sum(all_reqs.values())}
    return done(1 if problems else 0, problems, counts)


if __name__ == "__main__":
    sys.exit(main())
