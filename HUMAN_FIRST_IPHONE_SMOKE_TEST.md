# Run Game — первый iPhone smoke-test после передачи

Этот протокол предназначен для внешнего QA-тестера. Он проверяет установку,
карту, GPS/recovery и звук в безопасном месте. Он **не разрешает** тестеру
одобрять маршрут, workout, public start, M1-A или выходить на полевой маршрут.

Текущий проект: `R02 IN_PROGRESS / ENGINEERING_RC`. Допуск к устройству
появляется только после выдачи владельцем `RELEASE_MANIFEST.json`, пяти
приватных файлов и успешного выполнения всех команд ниже.

## 1. Получить точный код и приватный пакет

Владелец передаёт:

- полный 40-символьный `release_commit`;
- `RELEASE_MANIFEST.json`;
- по зашифрованному приватному каналу папку
  `research/r02/local/valparaiso_central/` с `current.binding.json`,
  `osm_snapshot.json`, AIFF, M4A и audio manifest;
- ожидаемый M4A SHA-256
  `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`.

```bash
git clone https://github.com/DoroninDobroCorp/run_game.git
cd run_game
git fetch --all --tags
git switch --detach <release_commit>
git status --short
```

`git status --short` должен быть пустым до копирования ignored private bundle.
Не используйте «последнюю ветку» вместо commit из манифеста.

## 2. Проверить пакет до сборки

```bash
/usr/bin/python3 -m pip install -r requirements-dev.txt
make r02-handoff-verify HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
make verify-clean-room IOS_DEVELOPMENT_TEAM=""
make verify-tester-package HANDOFF_MANIFEST=/secure/path/RELEASE_MANIFEST.json
```

Любой non-zero exit — `STOP`. Не подменяйте приватный bundle синтетическим:
в synthetic UI явно написано `SYNTHETIC TEST BUNDLE — НЕ ДЛЯ МАРШРУТА`.

Для полного maintainer gate владелец отдельно должен получить зелёный
`make verify-pretest` и CI. До этого установка тестеру считается
`BLOCKED`, даже если обычный app build успешен.

## 3. Signing и установка

Подключите разблокированный iPhone, подтвердите доверие и выберите уникальный
bundle ID и свой Apple Team:

```bash
make ios-prepare \
  IOS_BUNDLE_ID=com.example.rungame.founder.qa \
  IOS_DEVELOPMENT_TEAM=<APPLE_TEAM_ID>
open ios/RunGameFounder/RunGameFounder.xcodeproj
```

В Xcode выберите физический iPhone, не Simulator, и выполните Build & Run.
При запросе включите Developer Mode. На повторной установке нажмите в
приложении «Сбросить локальную готовность».

После чистого запуска M1-A должен быть заблокирован. Если приложение показывает
synthetic warning или разрешает M1-A без human gates — немедленный `STOP`.

## 4. Безопасный домашний smoke

Не двигайтесь ради GPS и не выходите на дорогу.

1. В «Проверить маршрут» Apple Maps должен построить все четыре сегмента.
2. Не ставьте route/workout/safety approvals.
3. Запустите диагностическую GPX-запись с `While Using` и Precise Location,
   заблокируйте экран на 30–60 секунд, вернитесь и завершите как
   `smoke/aborted`.
4. Начните вторую запись, дождитесь accepted point/checkpoint, принудительно
   закройте приложение и откройте снова. Должен появиться recovery
   `.partial.gpx`.
5. В «Прослушать дома» проверьте старт аудио и один Pause/Play с lock screen.
   Seeking должен отсутствовать. Это не 30-минутный audio approval.
6. Проверьте, что persistence/corruption error не исчезает молча и предлагает
   сохранить quarantine bytes или явно подтвердить reset.

## 5. Немедленный STOP

- crash/hang, пустой экран или неполная карта;
- SHA/preflight mismatch или synthetic bundle;
- нет Precise Location/samples/recovery;
- не работает lock-screen Pause/Play или доступен seeking;
- M1-A разблокирован без founder gates;
- потеря pending debrief/recall после relaunch;
- любое молчаливое исчезновение persistence error.

Не удаляйте приложение до снятия диагностики. Raw GPX и private fixture нельзя
прикладывать к issue, GitHub, мессенджеру или LLM.

## 6. Отчёт тестера

```text
Release commit (40 chars):
Manifest verify: PASS | FAIL
Clean-room gate: PASS | FAIL
Tester-package gate: PASS | FAIL
Mac/macOS/Xcode:
iPhone/iOS:
Install: PASS | FAIL
Fresh launch + M1 locked: PASS | FAIL
Map 4/4: PASS | FAIL
GPS/background/recovery: PASS | FAIL
Audio/lock-screen/no-seeking: PASS | FAIL
Queue persistence/relaunch: PASS | FAIL
First failing step + exact error:
Privacy-safe screenshots/video:
```

После PASS внешний тестер возвращает отчёт владельцу. Дневной обход, route
approval, полное прослушивание и founder run выполняются отдельно только по
[`docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md`](docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md).
