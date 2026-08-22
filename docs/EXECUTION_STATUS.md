# Журнал выполнения Run Game (EXECUTION_STATUS)

**Последнее обновление:** 16 августа 2026 года

**Текущая фаза:** Stage `R02` `IN_PROGRESS` (`ENGINEERING_RC / TECHNICAL_HANDOFF_AND_DEVICE_PENDING`)

**Accepted Master Audio SHA-256:** `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`

**Текущая ветка:** `codex/tester-readiness`

---

## 1. Current Product Thesis
> **Твой город становится игровым уровнем: приложение строит тренировочный маршрут через реальные места вокруг дома/старта и превращает их в сцены истории, которая могла произойти только здесь.**

Основные правила:
* Никакой живой генерации LLM во время бега. Вся миссия компилируется до старта в офлайн-бандл (`RouteBundle`).
* Тренировочная сетка (beginner Couch to 5K) имеет абсолютный приоритет и не меняется под сценарий. Сюжет адаптируется под структуру тренировки.
* Приватность: у founder slice нет project backend или analytics; raw GPX по
  умолчанию остаётся локально и не передаётся LLM. Apple Maps routing использует
  онлайн-сервис Apple и отправляет необходимые ему map/route requests.

---

## 2. Founder Decisions
* **География продукта:** Home-territory-based. Один пользователь развивает одну активную домашнюю территорию; travel и cross-city continuity не являются фичами MVP.
* **География founder research:** Traveler-based. Текущий город основателя —
  сменный полевой fixture без попадания города в канон/story state. Активная R02
  fixture — центральный Вальпараисо; Santiago неактивен, а Бар остаётся frozen
  R01 fixture.
* **Стартовый канон:** Выбрана оригинальная вселенная «Нулевой слой», Напарник Леа и центральный поворот «маршруты игрока не спасали, а создавали её». До production engine используется минимальный трёхмиссионный authoring graph; полностью производится пока только M1.
* **Stop-loss:** Проект развивается в режиме хобби для личного использования. Бюджет — личные ИИ-подписки (до $200/мес), бесплатные/дешевые лимиты API.
* **Разрешенные провайдеры:** GraphHopper (маршруты, бесплатный тариф), Overpass API (OSM, бесплатно), Wikipedia API (бесплатно), персональные API-ключи LLM (OpenAI/Anthropic/Gemini) через `.env`.
* **Контроль безопасности:** production-намерение остаётся двухуровневым:
  автоматическая проверка плюс ручной аппрув. Текущий founder shell реализует
  только offline integrity checks и ручные route/audio/pre-run gates; ни один
  автоматический статус не является safety или workout approval.
* **Native research exception:** локальный SwiftUI founder-only slice разрешён
  как инструмент R02. Он не открывает production gates и не разрешает
  TestFlight, внешних участников, backend или расширение product scope.

---

## 3. Gate Register
* **G0_DOCS:** `GO` (15 июля 2026 г., согласованы стратегия, план P00 и решения основателя).
* **G0_GEO_PROOF:** `PENDING` (Ожидает результатов этапа R03).
* **G0_DEMAND:** `PENDING` (Ожидает результатов этапа R04).
* **G1_COMPILER:** `PENDING` (Ожидает результатов этапа P09).
* **G2_COVERAGE:** `PENDING` (Ожидает результатов этапа P10).
* **G3_RUNTIME_RELIABILITY:** `PENDING` (Ожидает результатов этапа P20A).
* **G4_BEHAVIORAL_RETENTION:** `PENDING` (Ожидает результатов этапа P20B).
* **G5_COMMERCIAL:** `PENDING` (Ожидает результатов этапа P21).
* **G6_PAID_MVP:** `PENDING` (Ожидает результатов этапа P22).

---

## 4. Stage Table

| ID | Статус | Prerequisites | Доказательства (Evidence) | Обновлено | Следующее действие |
| :-: | :-: | :--- | :--- | :-: | :--- |
| **P00** | `COMPLETE` | Нет | Созданы `DOCUMENT_AUDIT.md` и `EXECUTION_STATUS.md`. Проведен аудит `TerraIncognita`. | 15.07.2026 | Переход к R01. |
| **R01** | `COMPLETE` | `G0_DOCS=GO` | Создан `R01_FEASIBILITY_REPORT.md`, сохранён `r01_raw_results.json`: все 20 точек дали минимум два POI-кандидата. Это POI-density signal, а не доказательство production L2; заявленные script/cache/GPX/manual-route-QA assets в текущем repo отсутствуют. | 15.07.2026 | Бар сохранён как frozen fixture; каждый маршрут R02 проверяется заново. |
| **R02** | `IN_PROGRESS` (`ENGINEERING_RC`) | `R01` | Подготовлены clean-clone workflow, CI, privacy/history audit, переносимый signing, приватный handoff manifest и fail-closed durable queue recovery. На текущем checkout прошли 245 Python-тестов (6 fixture-dependent skips), static analysis, privacy audit, synthetic iOS build, 76 Swift unit tests и 5 UI tests. Оригинальная Valparaíso fixture потеряна; отдельный local technical-only replacement из retained app projection и accepted M4A проходит handoff/preflight/audio checks с выключенными approvals. | 22.08.2026 | Передать manifest-bound private package → physical-device smoke → founder-only field gates. |
| **R03** | `NOT_STARTED`| `R02` | Созданы `research/r03/preregistration.v0.1.json`, `tools/r03_analyze.py` и `tests/test_r03_analyze.py` для офлайн-анализа синтетических A/B данных. | 11.08.2026 | Ожидает завершения физического этапа R02. |
| **R04** | `NOT_STARTED`| `R02` | Создан `research/r04/decision_template.md` (decision-ready шаблон с описанием аудитории, оффера, stop-loss и метрик конверсии). | 11.08.2026 | Ожидает основательского решения по запуску тестов спроса (может идти параллельно с R03). |

*(Этапы P01–P22 находятся в статусе `NOT_STARTED` и ожидают прохождения ворот G0).*

---

## 5. Command Evidence

Доказательства для текущего engineering candidate:

* `make quality py-compile`: `PASS` — `ruff`, `mypy`, Python bytecode compile.
* `/usr/bin/python3 -m unittest discover -s tests`: `PASS` — 245 тестов, 0 ошибок, 6 пропусков только для отсутствующего приватного master/fixture.
* `tools/r02_audit_privacy.py`: `PASS` — 5/5 проверок, включая reachable Git patch history; public R01 OSM coordinates явно отделены от private R02 scope.
* `make ios-synthetic-build IOS_DEVELOPMENT_TEAM=""`: `PASS` на Xcode 26.3 / iOS 26.2 Simulator.
* `make ios-synthetic-unit-test IOS_DEVELOPMENT_TEAM=""`: `PASS` — 76 тестов выполнено, 0 ошибок, iPhone 16 Pro Simulator / iOS 18.5.
* `make ios-synthetic-ui-test IOS_DEVELOPMENT_TEAM=""`: `PASS` — 5 тестов выполнено, 0 ошибок, iPhone 16 Pro Simulator / iOS 18.5.
* XCTest evidence: macOS 26.0 / Xcode 26.3; свежий Simulator полностью завершил `bootstatus` перед запуском. `.xcresult` хранится локально в `ios/RunGameFounder/DerivedData/Logs/Test/`.
* `make verify-pretest`: `BLOCKED`, ожидаемо — приватных Valparaíso source assets нет на этой машине.
* GitHub Actions: `BLOCKED_ACCOUNT_BILLING` — [run #1](https://github.com/DoroninDobroCorp/run_game/actions/runs/31917107276) создал два job, но GitHub не запустил ни один из-за billing lock аккаунта.

---

## 6. Open Blockers
До передачи на physical device остаются инженерные и человеческие блокеры:

1. **Technical handoff transfer:** пересоздать `RELEASE_MANIFEST.json` для финального release commit, передать manifest и private technical-only fixture по зашифрованному каналу. Historical private source bundle не восстановлен.
2. **Signing/device:** выбрать Apple Team, установить ровно manifest-bound commit и выполнить внешний QA smoke.

3. **GitHub Actions billing:** владелец организации должен снять billing lock и повторно запустить workflow; текущий failed badge не является test failure, потому что runner не выдавался.

4. **Human Route Approval (`binding.human_route_approved`):** только основатель после реального дневного обхода.
5. **Workout/M1/Public Start approvals:** только основатель; внешний QA-тестер не должен их выставлять.
6. **Full Audio Lock-Screen Review:** полное 30-минутное прослушивание принятого M4A на физическом iPhone.

---

## 7. Decision Log
* **15.07.2026 (P00):** Принято решение использовать код `TerraIncognita` (а именно парсеры OSM/Overpass и логику коридорной маршрутизации) как основу для адаптеров `PoiProvider` и `RouteProvider` в Run Game.
* **15.07.2026 (P00):** Переориентирован фокус проекта на персональное использование (хобби) с минимизацией серверных костов и распараллеливанием тестов спроса (R04) и опыта (R03).
* **15.07.2026 (R01):** Бар использован как первый research fixture. Все 20 стартов дали минимум два POI-кандидата (исторически это было названо «100% L2»); текущий технический L2 дополнительно требует route candidates, scorer и bundle, поэтому R01 трактуется только как POI-density signal.
* **16.07.2026 (R02):** Разделены `home-territory product behavior` and `traveler-based founder research`. Бар перестал быть обязательной географией R02–R03; смена города не стала продуктовой или сюжетной механикой.
* **16.07.2026 (R02):** Принято story-first решение: authoring graph обязателен сейчас, production runtime graph engine откладывается. Сравнены Dracula-inspired, future-frequency и erased-trace concepts; provisional winner — оригинальный «Нулевой слой» (93/100). Это редакционная гипотеза, не field evidence.
* **16.07.2026 (R02):** Зафиксированы Леа, M1–M3 micro-arc, три enum-state, четыре setup clues и reveal «игрок своими маршрутами создал Леа». Реализованы детерминированная линеаризация, A/B contract и запрет participant export до human approval.
* **07.08.2026 (R02):** Разрешён локальный founder-only SwiftUI slice как research exception для повторяемых M1 device/audio/GPS итераций. Production investment gates и запрет внешних участников не изменены.
* **10.08.2026 (R02):** Активной полевой фикстурой закреплён центральный Вальпараисо; Santiago переведён в неактивный локальный архив. Fixed-time master не считается geo-triggered runtime: первый walk-through и retiming review обязательны до founder run. Raw GPX по умолчанию остаётся локально; для разбора используется derived report без координат и точного старта.
* **11.08.2026 (R02):** Исторический baseline заявил `READY_FOR_DEVICE_SMOKE`; последующий полный аудит обнаружил, что локальные приватные assets отсутствуют, а текущий Xcode runner не даёт воспроизводимого runtime PASS. Заявление заменено evidence-based статусом.
* **21.08.2026 (R02):** Оригинальные private binding/snapshot/AIFF признаны утраченными после проверки local migration backups. Из retained installed-app projection и verified accepted M4A создан отдельный `RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED`; до передачи остаются его final handoff checks, независимый Swift runtime и physical-device gates.
* **22.08.2026 (R02):** После полного first boot нового iOS 18.5 Simulator локально выполнены 76/76 unit tests и 5/5 UI tests с exit 0. Reconstituted technical fixture прошёл manifest, doctor, privacy, preflight, audio QA и build gates; остаются private transfer, signing/physical-device smoke и founder-only field approvals.
