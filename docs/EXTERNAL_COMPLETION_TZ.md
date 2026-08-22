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

## Задача A — получить Apple runtime evidence

**Статус 22.08.2026:** выполнено локально на macOS 26.0 / Xcode 26.3,
iPhone 16 Pro Simulator / iOS 18.5: 76 unit tests и 5 UI tests прошли с 0
ошибок. Повтор на независимом runner остаётся полезным, но больше не блокирует
external technical QA.

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

## Задача B — reconstituted technical five-file bundle

**Статус:** выполнено локально владельцем; не делегировать слабой модели.

Нужны именно исходные файлы в private path
`research/r02/local/valparaiso_central/`:

- `current.binding.json`
- `osm_snapshot.json`
- `audio/m01_solo_founder_30min.aiff`
- `audio/m01_solo_founder_30min.m4a`
- `audio/m01_solo_founder_30min.manifest.json`

Оригинальные binding/snapshot/AIFF больше недоступны. Поэтому создан отдельный
локальный ignored fixture `valparaiso_central_reconstituted_20260821`:

- accepted M4A сохранён без изменения и должен совпадать с закреплённым SHA;
- mission projection из установленного приложения дала пять route points и OSM
  identity для внутренне согласованных replacement JSON;
- AIFF декодирован из accepted M4A, поэтому не является потерянным original
  source audio;
- fixture и handoff manifest маркируются
  `RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED`;
- все human/public-start/workout approvals остаются `false`.

Это позволяет техническую установку и smoke тест, но **не** восстанавливает
историческую полевую валидацию и не даёт права на participant/field run.

### Уже проверенные локальные источники — не повторять

- В текущем Mac найдены и сохранены только M4A+manifest в старом Simulator
  app; трёх остальных файлов там нет.
- Инвентарь `DevMigrationBackup/serverforvovka-20260814T223704Z` содержит
  `srv/LinguaLearn/english/run_game/research/r02/local/valparaiso_central/`,
  но сам каталог и `audio/` в момент backup были пустыми.
- Зашифрованные `dev-final`, `preliminary` и `ps38-supplement` migration
  archives уже были потоково проинспектированы владельцем: ни одного из пяти
  canonical R02 filenames в них нет.

Слабой модели **нельзя** получать, читать или использовать age identity,
зашифрованные backup’ы, SSH private keys, Apple credentials или private files.
Её допустимая задача — только Task A (Apple runtime на отдельном Mac) и
публичные synthetic checks. Она не должна перегенерировать этот fixture либо
снимать его `NOT_FIELD_APPROVED` status.

После восстановления:

```bash
make r02-handoff-create R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make r02-handoff-verify R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make verify-tester-package R02_FIXTURE=research/r02/local/valparaiso_central_reconstituted_20260821 HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

**Acceptance:** M4A SHA-256 строго равен
`17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`; все
команды выше проходят на финальном чистом SHA; `RELEASE_MANIFEST.json` содержит
fixture class `RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED`, передан
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
