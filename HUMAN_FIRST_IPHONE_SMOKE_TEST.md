# Run Game — передача человеку для первого iPhone smoke-test

Этот файл нужно прочитать **до установки приложения и до выхода на маршрут**.
Он описывает только первый диагностический тест на физическом iPhone. Полный
дневной обход, домашнее 30-минутное прослушивание и M1-A выполняются позже по
[подробному founder guide](docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md).

## Текущий допуск

- Статус: `R02 IN_PROGRESS / READY_FOR_DEVICE_SMOKE`.
- Активная фикстура: **Valparaíso Central**.
- Принятый технический baseline: `610849e63dc016f6194f490ee2c1ac57854b373d`.
- Master audio SHA-256:
  `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`.
- Это founder-only research instrument, не публичный продукт и не медицинская
  или тренировочная рекомендация.

`READY_FOR_DEVICE_SMOKE` не означает, что маршрут безопасен, workout одобрен
или M1-A разрешён. Human blockers в выводе preflight до реального обхода —
ожидаемое состояние.

## 1. Получить проект на другом Mac

Сначала проверьте, нет ли уже существующей папки `run_game`. Если репозиторий
уже развёрнут, не создавайте второй clone: откройте его и выполните команды
обновления.

Для нового компьютера:

```bash
git clone https://github.com/DoroninDobroCorp/run_game.git
cd run_game
git switch --track origin/executor/pre-first-test-last-mile-7a11842
git pull --ff-only
```

Для уже существующего checkout:

```bash
cd /absolute/path/to/run_game
git fetch origin
git switch executor/pre-first-test-last-mile-7a11842
git pull --ff-only
```

Проверьте, что дерево чистое и текущий commit является baseline или его
документационным потомком:

```bash
git status --short --branch
git log -1 --oneline
git merge-base --is-ancestor 610849e63dc016f6194f490ee2c1ac57854b373d HEAD
```

Последняя команда должна завершиться с exit code `0`.

## 2. Отдельно перенести локальные артефакты

Папка `research/r02/local/` намеренно не хранится в Git. С исходного Mac
скопируйте целиком:

```text
research/r02/local/valparaiso_central/
```

В ней должны находиться как минимум:

```text
current.binding.json
osm_snapshot.json
audio/m01_solo_founder_30min.aiff
audio/m01_solo_founder_30min.m4a
audio/m01_solo_founder_30min.manifest.json
```

Не коммитьте эту папку и не отправляйте её публично. Папка
`santiago_cumming/`, если она также скопирована, остаётся неактивным архивом и
не должна подменять Valparaíso.

## 3. Проверить Mac до установки

Из корня проекта:

```bash
make PYTHON=/usr/bin/python3 verify-pretest
```

Продолжать можно только при exit code `0`. В выводе `r02_preflight` должен быть
статус `READY_FOR_DEVICE_SMOKE`, а SHA master должен совпасть со значением
выше. Список `human_blockers_to_m1_a` пока не является ошибкой.

При любом красном тесте остановитесь. Сохраните команду, exit code и полный
текст первой ошибки; не пытайтесь обходить validator или вручную ставить human
approval.

## 4. Установить на физический iPhone

1. Подключите разблокированный iPhone кабелем и подтвердите доверие Mac.
2. Откройте `ios/RunGameFounder/RunGameFounder.xcodeproj` в Xcode.
3. Выберите подключённый iPhone как destination, не Simulator.
4. При необходимости выберите свой Personal Team в `Signing & Capabilities`.
5. Нажмите **Build & Run**.
6. Если iPhone запросит Developer Mode, включите его, перезагрузите устройство
   и снова выполните Build & Run.
7. Для не-чистой установки в приложении нажмите «Сбросить локальную
   готовность».

После чистого запуска ожидается device readiness `1/3`. M1-A должен оставаться
заблокированным.

## 5. Выполнить только короткий домашний smoke

Делайте этот этап в безопасном месте. Не выходите на проезжую часть и не
пытайтесь двигаться ради GPS.

1. Откройте «Проверить маршрут» и убедитесь, что Apple Maps строит все четыре
   сегмента между пятью точками. Неполный маршрут — ошибка.
2. Не ставьте route approval и safety-галочки дома.
3. Запустите короткую диагностическую GPX-запись. Разрешите `While Using` и
   **Precise Location**.
4. Заблокируйте экран на 30–60 секунд, вернитесь в приложение и проверьте, что
   accepted samples обновляются. Завершите запись как `smoke/aborted`, не как
   route evidence.
5. Начните вторую диагностическую запись, дождитесь accepted точки/checkpoint,
   принудительно закройте приложение и откройте снова. На dashboard должен
   появиться recovery `.partial.gpx`.
6. Откройте «Прослушать дома», запустите звук и убедитесь, что слышны первый
   workout NAV и первая реплика.
7. Один раз проверьте Pause/Play с lock screen. Перемотка должна быть
   недоступна.
8. Остановите короткую проверку. Не выдавайте её за полное 30-минутное audio
   approval.

## 6. Немедленно остановиться, если

- приложение падает или зависает;
- master не проходит SHA-проверку или не воспроизводится;
- карта показывает не все четыре сегмента;
- Precise Location недоступна или samples не появляются;
- после принудительного закрытия нет recovery `.partial.gpx`;
- lock-screen Pause/Play не работает или доступна перемотка;
- приложение позволяет запустить M1-A без human gates;
- приложение показывает corruption/persistence error banner.

Не удаляйте приложение и диагностические файлы до фиксации проблемы.

## 7. Что передать после smoke-test

Не прикладывайте raw GPX к GitHub, мессенджеру или LLM. Передайте только:

```text
Commit/HEAD:
Mac + macOS:
iPhone + iOS:
Install/build: PASS | FAIL
Map 4/4 segments: PASS | FAIL
Precise GPS samples: PASS | FAIL
Background 30–60 sec: PASS | FAIL
Forced-close partial recovery: PASS | FAIL
Audio start: PASS | FAIL
Lock-screen Pause/Play: PASS | FAIL
Seeking absent: PASS | FAIL
Unexpected M1-A unlock: YES | NO
First error text:
Screenshots without coordinates/private data:
```

Если все пункты прошли, следующим отдельным действием будет дневной
walk-through из части D подробного guide. Не объединяйте домашний smoke,
дневной обход и первый сюжетный run в одну попытку.
