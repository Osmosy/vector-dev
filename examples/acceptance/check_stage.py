#!/usr/bin/env python3
"""Чекер этапа: приёмка по трём вопросам с машиночитаемым выводом.

Коды выхода:
  0 — принято
  1 — блокирующие находки
  2 — плохой вход (нет RAMKA.md или реестра требований)
  3 — отказ запускать (подменён чекер или манифест замороженных файлов)

Ожидаемая структура проекта:
  RAMKA.md
  registry/requirements.jsonl   # {"req_id","stage","code_address","log_evidence"}
  acceptance/frozen.sha256      # "<sha256>  <путь>" для замороженных тестов и чекеров
  acceptance/checker.sha256     # необязательный: sha256 самого чекера (для кода 3)

Только stdlib. Проверка ничего не меняет — она только отчитывается.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(root: Path) -> dict[str, str]:
    manifest = root / "acceptance" / "frozen.sha256"
    pairs: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition("  ")
        if digest and name:
            pairs[name.strip()] = digest.strip()
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="корень проекта")
    parser.add_argument("--stage", help="принимать только этот этап")
    parser.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    # вход: без рамки и реестра принимать нечего
    if not (root / "RAMKA.md").is_file():
        return report(args, 2, ["нет RAMKA.md — этап 1 не пройден"], {})
    registry = root / "registry" / "requirements.jsonl"
    if not registry.is_file():
        return report(args, 2, [f"нет {registry.relative_to(root)} — реестр требований отсутствует"], {})

    # отказ запускать: чекер подменён, если есть эталонный хэш
    checker_hash = root / "acceptance" / "checker.sha256"
    if checker_hash.is_file():
        expected = checker_hash.read_text(encoding="utf-8").split()[0]
        if sha256(Path(__file__).resolve()) != expected:
            return report(args, 3, ["sha256 чекера не совпадает с эталоном — проверка подменена"], {})

    requirements = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.stage:
        requirements = [r for r in requirements if str(r.get("stage")) == str(args.stage)]

    problems: list[str] = []
    no_address = [r["req_id"] for r in requirements if not str(r.get("code_address") or "").strip()]
    no_evidence = [r["req_id"] for r in requirements if not str(r.get("log_evidence") or "").strip()]
    if no_address:
        problems.append(f"K1: {len(no_address)} требований без адреса в коде — {', '.join(no_address[:5])}")
    if no_evidence:
        problems.append(f"K2: {len(no_evidence)} требований без записи в логе — {', '.join(no_evidence[:5])}")

    # адрес должен существовать: ссылка на несуществующий файл — это не адрес
    missing_files = sorted({str(r["code_address"]).split(":")[0] for r in requirements
                            if str(r.get("code_address") or "").strip()
                            and not (root / str(r["code_address"]).split(":")[0]).exists()})
    if missing_files:
        problems.append(f"адрес указывает в пустоту: {', '.join(missing_files[:5])}")

    manifest = root / "acceptance" / "frozen.sha256"
    if not manifest.is_file():
        problems.append("нет acceptance/frozen.sha256 — замороженный набор не объявлен (K4)")
        changed: list[str] = []
    else:
        changed = [name for name, digest in read_manifest(root).items()
                   if not (root / name).is_file() or sha256(root / name) != digest]
        if changed:
            problems.append(f"K4: изменены замороженные файлы — {', '.join(sorted(changed)[:5])}")

    stats = {
        "требований": len(requirements),
        "без адреса": len(no_address),
        "без доказательства": len(no_evidence),
        "замороженных": len(read_manifest(root)) if manifest.is_file() else 0,
        "изменённых": len(changed),
    }
    return report(args, 1 if problems else 0, problems, stats)


def report(args: argparse.Namespace, code: int, problems: list[str], stats: dict) -> int:
    if args.json:
        print(json.dumps({"exit": code, "problems": problems, "stats": stats}, ensure_ascii=False))
    else:
        for problem in problems:
            print(f"находка: {problem}")
        if not problems:
            print("принято: находок нет")
        if stats:
            print("; ".join(f"{k}: {v}" for k, v in stats.items()))
    return code


if __name__ == "__main__":
    sys.exit(main())
