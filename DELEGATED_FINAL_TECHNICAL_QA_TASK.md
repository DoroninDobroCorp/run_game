# Выполни финальную техническую подготовку проекта к передаче тестеру

Работай автономно и доведи все доступные технические задачи до завершения.
Репозиторий: `DoroninDobroCorp/run_game`, рабочая ветка:
`codex/tester-readiness`. Разрешено исправлять код, конфигурацию CI, тесты и
документацию, запускать проверки, делать понятные атомарные коммиты и пушить их
в эту ветку. Не останавливайся после анализа: реализуй и проверь исправления.

## Единственная цель

Подготовить технический build candidate для внешнего QA так, чтобы честно были
закрыты все доступные автоматические gates и оставшиеся ручные блокеры были
сведены к физическому iPhone/signing и founder-only field review.

`BUILD SUCCEEDED` не является результатом runtime-теста. Успех Swift runtime
или UI suite — это ненулевое число реально выполненных тест-методов и exit 0.

## Уже готово — не ломать и не переделывать без причины

- Python/static/privacy/synthetic checks проходят.
- Есть portable SSH Python CI: `tools/r02_remote_python_ci.sh`.
- GitHub Actions сейчас заблокирован billing, это не code failure.
- Создан local-only fixture
  `research/r02/local/valparaiso_central_reconstituted_20260821`. Он содержит
  accepted M4A и технически согласованные replacement assets, но имеет статус
  `RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED`.
- Fixture не хранится в Git и может отсутствовать в твоём checkout. Не пытайся
  создать его заново, не коммить private resources и не требуй их для
  synthetic/runtime CI.
- На исходном Mac Simulator умеет загрузить устройство, но `xcodebuild test`
  ранее зависал с нулём выполненных tests. Не считать это PASS.

## Что нужно сделать

### 1. Закрыть Swift runtime evidence

На доступном Mac с Xcode и iOS Simulator выполни из чистого checkout:

```bash
/usr/bin/python3 -m pip install -r requirements-dev.txt
make verify-clean-room IOS_DEVELOPMENT_TEAM=""
make ios-synthetic-unit-test IOS_DEVELOPMENT_TEAM=""
make ios-synthetic-ui-test IOS_DEVELOPMENT_TEAM=""
```

Если test runner зависает или не стартует:

1. Сохрани точный лог и проверь `xcrun simctl list devices available`.
2. Можно безопасно restart CoreSimulator и создать **новое временное**
   Simulator device. Не стирай существующие пользовательские Simulator devices,
   не удаляй `~/Library/Developer/CoreSimulator` целиком и не удаляй данные
   проекта/пользователя.
3. Исправь воспроизводимую конфигурационную или кодовую проблему, если найдёшь.
4. Повтори unit и UI suites отдельно.

Acceptance: оба запуска реально выполняют тесты и завершаются exit 0. Приложи
в итоговом отчёте OS, Xcode, iOS runtime, destination, команды, число
passed/failed methods и путь к `.xcresult` при наличии.

### 2. Усилить независимую CI-проверку, если это доступно

GitHub Actions billing lock не пытайся обходить секретами или платёжными
операциями. Если доступен Linux/macOS SSH host, запусти там:

```bash
tools/r02_remote_python_ci.sh "$PWD"
```

Сохрани лог как `PASS_REMOTE_PYTHON_ONLY`. Это закрывает только Python/static/
privacy lane и не заменяет шаг 1.

Если доступен self-hosted macOS runner или легитимный CI-провайдер уже в scope,
можно настроить эквивалент текущего workflow. Не создавай платные аккаунты,
не меняй billing и не публикуй private fixture.

### 3. Финальная техническая регрессия

После своих изменений обязательно выполни:

```bash
make quality py-compile r02-audit-privacy verify-synthetic
make verify-clean-room IOS_DEVELOPMENT_TEAM=""
git diff --check
git status --short
```

Если local reconstituted fixture доступен, дополнительно выполни только с
явно заданным путём к нему:

```bash
fixture_path=research/r02/local/valparaiso_central_reconstituted_20260821
handoff_path="$fixture_path/RELEASE_MANIFEST.<HEAD_SHORT>.json"
make verify-tester-package R02_FIXTURE="$fixture_path" HANDOFF_MANIFEST="$handoff_path" IOS_DEVELOPMENT_TEAM=""
```

Не создавай replacement fixture при его отсутствии и не меняй его approvals.

### 4. Коммиты и передача результата

Сделай атомарные коммиты с понятными сообщениями и запушь `codex/tester-readiness`.
Не переписывай историю, не используй force-push, `git reset --hard`, массовое
удаление файлов или destructive clean.

В финальном сообщении дай только проверяемый отчёт:

1. commit SHA и что изменено;
2. все команды и PASS/FAIL;
3. для Swift: реально выполненные test methods, а не только compile;
4. точные оставшиеся блокеры, если они есть;
5. однозначный статус: `READY_FOR_EXTERNAL_TECHNICAL_QA` либо `BLOCKED`.

## Абсолютные запреты

- Не коммить и не отправляй private fixture, M4A/AIFF, координаты, GPX,
  screenshots с маршрутами, `.env`, токены, SSH/Apple keys или certificates.
- Не представляй reconstituted fixture как исторический original source или
  как полевое approval evidence.
- Не ставь `public_start`, `human_route_approved`, `workout_approved`,
  `human_approved` либо slot approvals в `true`.
- Не выполняй реальный маршрут, тренировку, founder field review или 24-hour
  recall. Это только задача технической подготовки QA.
- Не утверждай готовность physical iPhone smoke без физического устройства,
  signing и фактической установки.
