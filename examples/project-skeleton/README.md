# Скелет проекта

Минимальный пример, на котором чекер возвращает 0:

```
RAMKA.md                      # этап 1
research/INDEX.json           # этап 2: источники с sha256, версией и датой
registry/requirements.jsonl   # этап 3: требования с адресом в коде и записью в логе
src/app.py                    # адрес требования REQ-0001
logs/run.log                  # доказательство для REQ-0001 и REQ-0002
tests/test_app.py             # замороженный набор
acceptance/frozen.sha256      # хэши замороженных файлов
```

Проверка:

```bash
python3 ../acceptance/check_stage.py --root .
```

Что ломает приёмку:

- убрать `code_address` у требования → код 1 (K1)
- поправить `tests/test_app.py` → код 1 (K4)
- удалить `RAMKA.md` → код 2
- подменить чекер, положив его `sha256` в `acceptance/checker.sha256` → код 3
