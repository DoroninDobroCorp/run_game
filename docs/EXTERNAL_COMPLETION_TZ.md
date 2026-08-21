# ТЗ: закрыть оставшиеся release-gates перед передачей тестеру

## Контекст и жёсткие правила

Репозиторий: `DoroninDobroCorp/run_game`, ветка-кандидат:
`codex/tester-readiness`. Это инженерный кандидат R02, не разрешение на
полевой маршрут. Нельзя коммитить или загружать публично private fixture,
координаты/GPX, сертификаты, ключи либо личные данные. Нельзя ставить human
approvals в `true` без founder field-review.

Кодовая база уже проходит synthetic Python/static/privacy gates и компилирует
Swift test targets. Нужно закрыть только перечисленные ниже доказательные
ворота. Любой результат должен содержать полный SHA коммита, команду, OS/Xcode
и полный лог; `COMPILED` нельзя выдавать за `TESTED`.

## Задача A — получить независимое Apple runtime evidence

**Исполнитель:** Mac с Xcode 26.3+ и рабочим CoreSimulator либо self-hosted
macOS runner/Xcode Cloud. Linux SSH для этой задачи не подходит.

1. Сделать чистый checkout точного release SHA.
2. Установить pinned Python development requirements.
3. Запустить `make verify-clean-room IOS_DEVELOPMENT_TEAM=""`.
4. Запустить отдельно `make ios-synthetic-unit-test` и
   `make ios-synthetic-ui-test`.
5. Приложить `.xcresult` либо machine-readable summary, где видно число
   реально выполненных и прошедших test methods. Нулевое выполнение — FAIL,
   даже если build успешен.

**Acceptance:** обе runtime suites реально завершены с exit 0, нет private
resources в bundle/логе, зафиксированы Mac OS, Xcode, iOS runtime и SHA.

## Задача B — вернуть authoritative private five-file bundle

**Исполнитель:** владелец исходного защищённого хранилища/резервной копии.

Нужны именно исходные файлы в private path
`research/r02/local/valparaiso_central/`:

- `current.binding.json`
- `osm_snapshot.json`
- `audio/m01_solo_founder_30min.aiff`
- `audio/m01_solo_founder_30min.m4a`
- `audio/m01_solo_founder_30min.manifest.json`

Не реконструировать binding/snapshot/AIFF по встроенному приложению: это
создало бы новые неподтверждённые данные. Найденные локально M4A+manifest можно
сохранить только инструментом `r02-recover-cached-assets`; его статус
`UNVERIFIED_PARTIAL_RECOVERY`, это не fixture и не release source.

После восстановления:

```bash
make r02-handoff-create HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make r02-handoff-verify HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make verify-pretest
make verify-tester-package HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

**Acceptance:** M4A SHA-256 строго равен
`17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`; все
команды выше проходят на финальном чистом SHA; `RELEASE_MANIFEST.json` передан
отдельно через шифрованный канал, private files не попали в Git.

## Задача C — physical iPhone smoke

**Исполнитель:** QA с физическим iPhone, Apple signing и тестовым bundle ID.

Следовать буквально `HUMAN_FIRST_IPHONE_SMOKE_TEST.md`. До начала зафиксировать
device/model/iOS, QA bundle ID, commit SHA и manifest SHA. Проверить install,
first launch, orientation/dynamic type/VoiceOver smoke, map preview, refusal
без разрешений, GPS/background recovery, lock-screen audio and interruptions,
relaunch/persistence recovery. Не выполнять маршрут и не менять founder gates.

**Acceptance:** все обязательные шаги `PASS`, либо отдельный баг с severity,
первым failing step и privacy-safe evidence. Raw GPX и private coordinates в
отчёт не прикладывать.

## Задача D — founder-only field gates (после технического QA)

**Исполнитель:** только founder/уполномоченный field reviewer.

Сделать daylight walk-through, 30-minute listening, run и 24-hour recall по
порядку, описанному в `R02_FOUNDER_IPHONE_TEST_GUIDE.md`. Это отдельный этап и
не может быть делегирован обычному тестеру или модели.

**Acceptance:** подписанная human review evidence; только после этого могут
изменяться соответствующие approval flags.
