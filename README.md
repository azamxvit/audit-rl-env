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

Команда делает пять шагов, все офлайн, около 25 секунд на ноутбуке:

1. генерирует 10 train- и 10 dev-эпизодов из версионированных конфигов `backend/configs/` в `backend/episodes/`;
2. прогоняет тесты (`backend/tests/`): контракт, лимиты, неверный ввод, анти-утечка, matcher и атаки на награду, детерминизм, метаморфные пары;
3. независимо проверяет данные (`backend/scripts/verify.py`): воспроизводимость байт-в-байт, бухгалтерские равенства до и после инъекции, «полный аудит открытых записей == эталон», достаточность каждого набора доказательств, парная проверка «перестановка + смена ID»;
4. прогоняет 4 базовые политики и нашу обученную `learned_auditor` (отдельной строкой). Траектории пишутся в `backend/runs/<split>/<policy>/trajectories.jsonl`, метрики P/R/F1, возврат, шаги и время — в `backend/runs/report.md`.
5. оценивает обученного аудитора на 80 отложенных эпизодах и строит кривую обучения (`backend/runs/learned_eval.md`).

Без `make`: `cd backend && PYTHONPATH=src python3 scripts/verify_all.py`. Демо скриптовой политики: `make demo`.

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

| инструмент     | аргументы                                                                                                 | что возвращает                                                |
| -------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `list_records` | `table` (`ledger` \| `invoices` \| `payments` \| `fx`), `cursor` (непрозрачный, стабильный), `limit` ≤ 50 | страница записей и `next_cursor`                              |
| `get_record`   | `table`, `id`                                                                                             | одна запись                                                   |
| `get_document` | `doc_id`                                                                                                  | счёт или платёж                                               |
| `calculator`   | `expression`                                                                                              | арифметика над десятичными числами (AST whitelist, `Decimal`) |
| `submit`       | `episode_id`, `findings[]`                                                                                | завершает эпизод (`terminated=true`)                          |

Бюджет — 100 шагов, `submit` входит в бюджет. Ошибочное действие тоже расходует шаг. При исчерпании шагов или 60 с эпизод завершается с `truncated=true` и оценивается как пустой ответ. Награда = `clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1)`. В режиме `train` политика получает её после завершения эпизода. В режиме `eval` награда и диагностика остаются в журнале оценщика.

## Сыграть за аудитора (веб-интерфейс AuditDesk)

```bash
make play
```

Откроется сервер на stdlib по адресу http://127.0.0.1:8000. Он раздаёт уже собранный `frontend/dist`, так что Node не нужен. В интерфейсе тот же бюджет 100 шагов и те же инструменты, что у агента. Бесплатно: фильтр по уже загруженным строкам, просмотр загруженных записей, политика и черновик выводов. После отправки открывается разбор по эталону; он доступен только для открытых train/dev эпизодов.

Пересобрать фронт (нужны Node 18+ и сеть для `npm ci`): `make frontend`. Режим разработки: `cd frontend && npm run dev`, Vite проксирует `/api` на `:8000`.

## Обученный аудитор

Кроме четырёх эталонных политик в репозитории есть наша обученная политика `learned_auditor`. Она сама читает таблицы через инструменты среды, строит кандидатов и их признаки из открытых записей и решает обученным детектором (логистическая регрессия на чистом stdlib), что отправить в `submit`.

```bash
make train-learned   # переобучить (~5 с, CPU, детерминированно) -> backend/src/audit_env/learning/learned_auditor.json
make eval-learned    # 80 отложенных эпизодов через AuditEnv + кривая обучения -> backend/runs/learned_eval.md
```

На отложенных эпизодах (dev-конфиги, новые seed) у неё micro-F1 0.999 и средний возврат 0.965; у `simple_reconciler` 0.557 и 0.309. Устройство, кривая обучения и ограничения описаны в [DESIGN.md §12](DESIGN.md#12-обученный-аудитор-learning-policieslearnedpy). Это диагностика: по кейсу обучение весов баллов не даёт.

## Разработка: форматирование и тесты

```bash
make format         # ruff (Python) + Prettier (TS/CSS/JSON/Markdown, порядок классов Tailwind)
make lint           # то же без изменений файлов: ruff check, ruff format --check, prettier --check
make frontend-test  # Vitest + Testing Library: утилиты, хуки, компоненты, интеграция App с фейковым API
make e2e            # Playwright + axe: сборка dist, реальный сервер, сквозной сценарий и проверки доступности
```

Python-инструменты ставятся из `backend/requirements-dev.txt` (pytest и ruff с фиксированными версиями). Для фронта нужен `npm ci` в `frontend/`, а для e2e один раз `npx playwright install chromium`.

Фронт написан на Tailwind CSS 4 без собственных CSS-классов и без `@apply`. Токены цвета, теней и шрифтов заданы в `@theme` в `frontend/src/index.css`, а переиспользуемые стили живут в компонентах `frontend/src/ui/` (`Button`, `Badge`, `Card`, `DataTable`, `Dialog`, `Drawer`, поля формы). Разметка семантическая: `aside`/`nav`/`header`/`main`, `role="search"`, `aria-current`, секции с заголовками, `dl` для пар ключ–значение, таблицы с `caption` и `th scope`, `fieldset`/`legend`, модальный диалог, live-region для уведомлений.

Импорты идут через алиас `@/` и barrel-файлы `index.ts` в каждой папке: `import { Button, Card } from "@/ui"`, а также `@/components`, `@/screens`, `@/hooks`, `@/lib`, `@/types` и `@/api`. Внутри одной папки модули импортируют друг друга по относительному пути, чтобы не было циклов через barrel.

## Состав репозитория

```
backend/            Python: src/audit_env (среда + HTTP-сервер), tests/ (~160 тестов), scripts/, configs/, episodes/, runs/
  src/audit_env/    money, calculator, world, generator, errors/ (4 типа + сценарии + отвлекающие), checker, store, env,
                    matcher, reward, grader, transform, trajectories, policies/
  configs/          версионированные конфиги генератора (train/, dev/) и splits.json (config, seed)
  episodes/         10 train + 10 dev: <ep>/public/* (агенту), <ep>/private/{truth,provenance}.json (оценщику)
  scripts/          verify_all, generate_episodes, verify, run_baselines, transform_episode, demo
  runs/             траектории, журнал оценщика, report.md/json (результат make verify)
frontend/           React + TS + Vite (Auditor Playground); собранный dist/ в репозитории
docs/               case.pdf, спецификации и планы
```

Все компании, люди, счета и деньги вымышлены.

## Лицензия

MIT, см. [LICENSE](LICENSE).
