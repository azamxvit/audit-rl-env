#!/usr/bin/env bash
# One-take screen-recording script (make demo-record). The presenter presses Enter to move on.
# 1) the official one-command check in Docker (offline, 2 CPU / 4 GB), 2) the 8-scene tour,
# 3) the policy report, 4) hand-off to the web UI. Run from the repository root.
set -uo pipefail
cd "$(dirname "$0")/.."

B=$'\033[1m'; D=$'\033[2m'; G=$'\033[32m'; R=$'\033[0m'
say()  { printf "\n${B}%s${R}\n" "$1"; }
note() { printf "${D}%s${R}\n" "$1"; }
cmd()  { printf "${G}\$ %s${R}\n" "$1"; }
next() { read -r -p "$(printf "${D}   [Enter] ->${R}")" _; }

clear
printf "${B}audit-rl-env${R} - воспроизводимая RL-среда для ИИ-аудитора (Genesis Hackathon, FinTech)\n"
note "Синтетическая бухгалтерия со скрытыми ошибками, контракт reset/step, matcher, терминальная награда."
note "Всё вымышлено, всё офлайн, ядро - Python 3.11 stdlib."
next

say "1. Вся проверка - одна команда, в контейнере без сети, в лимитах кейса"
cmd "docker run --rm --network none --cpus 2 --memory 4g audit-env"
if docker info >/dev/null 2>&1 && docker image inspect audit-env >/dev/null 2>&1; then
  docker run --rm --network none --cpus 2 --memory 4g audit-env 2>&1 \
    | tee /tmp/audit-env-verify.log \
    | grep --line-buffered -E "^==>|^<==|^verify:|fuzz:|data verification:"
  note "(полный вывод: /tmp/audit-env-verify.log)"
else
  note "Docker не запущен или образ не собран - то же самое локально:"
  cmd "make verify"
  make -s verify 2>&1 | grep --line-buffered -E "^==>|^<==|^verify:|fuzz:|data verification:"
fi
next

say "2. Среда в восьми сценах (всё считается вживую)"
cmd "make demo STEP=1"
(cd backend && PYTHONPATH=src python3 scripts/demo_tour.py --step)

say "3. Диагностика политик: P, R, F1, возврат, шаги (dev, закрытый режим)"
cmd "cat backend/runs/report.md"
awk '/^## dev/{f=1} f&&/^\| (policy|random|simple|flag|oracle|learned)/{print} /^Recall by issue type/{if(f) exit}' backend/runs/report.md
echo
cmd "head backend/runs/learned_eval.md"
sed -n '5,8p' backend/runs/learned_eval.md
next

say "4. Сыграть за аудитора: веб-интерфейс поверх того же контракта"
if curl -fs http://127.0.0.1:8000/api/episodes >/dev/null 2>&1; then
  note "make play уже запущен - открываю http://127.0.0.1:8000"
  open http://127.0.0.1:8000 2>/dev/null || true
else
  note "запустите в соседней вкладке: make play  ->  http://127.0.0.1:8000"
fi
printf "\n${B}Репозиторий:${R} github.com/azamxvit/audit-rl-env   ${B}Документация:${R} README.md, DESIGN.md\n"
