# audit-rl-env — воспроизводимая RL-среда для ИИ-аудитора

Генератор синтетической бухгалтерии вымышленной компании со скрытыми ошибками и Gym-подобная среда `reset/step`. В неё входят узкие инструменты расследования, matcher и терминальная награда. Ядро написано на чистом Python 3.11 stdlib: без сети, без GPU и без внешних зависимостей (`pytest` нужен только для тестов). Устройство и принятые решения описаны в [DESIGN.md](DESIGN.md).

## Одна команда проверки

```bash
make verify
```

или в контейнере без сети:

```bash
docker build -t audit-env . && docker run --network none audit-env
```

Команда делает четыре шага, все офлайн, около 5 секунд на ноутбуке:

1. генерирует 10 train- и 10 dev-эпизодов из версионированных конфигов `configs/` в `episodes/`;
2. прогоняет тесты (`tests/`): контракт, лимиты, неверный ввод, анти-утечка, matcher и атаки на награду, детерминизм, метаморфные пары;
3. независимо проверяет данные (`scripts/verify.py`): воспроизводимость байт-в-байт, бухгалтерские равенства до и после инъекции, «полный аудит открытых записей == эталон», достаточность каждого набора доказательств, парная проверка «перестановка + смена ID»;
4. прогоняет 4 базовые политики. Траектории пишутся в `runs/<split>/<policy>/trajectories.jsonl`, метрики P/R/F1, возврат, шаги и время — в `runs/report.md`.

Без `make`: `PYTHONPATH=src python3 scripts/verify_all.py`. Демо скриптовой политики: `make demo`.

## Использование среды

```python
from audit_env.env import AuditEnv

env = AuditEnv(mode="train")                      # "eval": оценщик в отдельном процессе
obs, info = env.reset(seed=7, config=None)        # config: dict генератора или {"episode_dir": "..."}
episode_id = obs["manifest"]["episode_id"]
obs, reward, terminated, truncated, info = env.step(
    {"tool": "list_records", "args": {"table": "ledger", "limit": 50}})
obs, reward, terminated, truncated, info = env.step(
    {"tool": "submit", "args": {"episode_id": episode_id, "findings": [...]}})
```

| инструмент | аргументы | что возвращает |
|---|---|---|
| `list_records` | `table` (`ledger` \| `invoices` \| `payments` \| `fx`), `cursor` (непрозрачный, стабильный), `limit` ≤ 50 | страница записей и `next_cursor` |
| `get_record` | `table`, `id` | одна запись |
| `get_document` | `doc_id` | счёт или платёж |
| `calculator` | `expression` | арифметика над десятичными числами (AST whitelist, `Decimal`) |
| `submit` | `episode_id`, `findings[]` | завершает эпизод (`terminated=true`) |

Бюджет — 100 шагов, `submit` входит в бюджет. Ошибочное действие тоже расходует шаг. При исчерпании шагов или 60 с эпизод завершается с `truncated=true` и оценивается как пустой ответ. Награда = `clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)`. В режиме `train` политика получает её после завершения эпизода. В режиме `eval` награда и диагностика остаются в журнале оценщика.

## Состав репозитория

```
src/audit_env/      money, calculator, world (скрытая история), generator, errors/ (4 типа + сценарии + отвлекающие),
                    checker (независимая проверка), store, env, matcher, reward, grader, transform, trajectories, policies/
configs/            версионированные конфиги генератора (train/, dev/) и splits.json (config, seed)
episodes/           10 train + 10 dev: <ep>/public/* (агенту), <ep>/private/{truth,provenance}.json (оценщику)
scripts/            verify_all, generate_episodes, verify, run_baselines, transform_episode, demo
runs/               траектории, журнал оценщика, report.md/json (результат make verify)
tests/              ~160 тестов
```

Все компании, люди, счета и деньги вымышлены.

## Лицензия

MIT, см. [LICENSE](LICENSE).
