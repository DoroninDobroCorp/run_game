# Журнал выполнения Run Game (EXECUTION_STATUS)

**Последнее обновление:** 11 августа 2026 года
**Текущая фаза:** Stage `R02` `IN_PROGRESS` (substatus `READY_FOR_DEVICE_SMOKE`, pre-first-test hardening завершён)
**Bundled Master Audio SHA-256:** `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`
**Текущая ветка:** `executor/pre-first-test-last-mile-7a11842`

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
| **R02** | `IN_PROGRESS` (`READY_FOR_DEVICE_SMOKE`) | `R01` | Pre-First-Test Max Hardening завершён. Созданы `docs/PRE_FIRST_TEST_READINESS.md` (18 readiness lanes), `tools/r02_doctor.py`, `tools/r02_validate_evidence.py`, `tools/r02_audio_qa.py`, `tools/r03_analyze.py` и `research/r04/decision_template.md`. Пройден `make verify-pretest`. Master audio SHA-256 (`17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`). Активная founder fixture — центральный Вальпараисо (Plaza de la Victoria ➔ Arco Británico ➔ Parque Italia ➔ Plaza O'Higgins). Вся синтетическая и симуляционная часть готова. | 11.08.2026 | Physical-device smoke ➔ дневной walk-through/derived report ➔ human route approval ➔ полный lock-screen audio check ➔ GPS-gated solo founder run ➔ immediate JSON/queued 24h recall. |
| **R03** | `NOT_STARTED`| `R02` | Созданы `research/r03/preregistration.v0.1.json`, `tools/r03_analyze.py` и `tests/test_r03_analyze.py` для офлайн-анализа синтетических A/B данных. | 11.08.2026 | Ожидает завершения физического этапа R02. |
| **R04** | `NOT_STARTED`| `R02` | Создан `research/r04/decision_template.md` (decision-ready шаблон с описанием аудитории, оффера, stop-loss и метрик конверсии). | 11.08.2026 | Ожидает основательского решения по запуску тестов спроса (может идти параллельно с R03). |

*(Этапы P01–P22 находятся в статусе `NOT_STARTED` и ожидают прохождения ворот G0).*

---

## 5. Command Evidence

Сводный результат независимого автоматизированного прогона для принятого технического baseline (`commit 610849e`):

* `make verify-pretest`:
  - `tools/r02_doctor.py`: `PASS` (9 проверок, 0 WARN по uncommitted изменениям при чистом рабочем дереве).
  - `tools/r02_audit_privacy.py`: `PASS` (4/4 проверки приватности, 0 утечек координат/секретов).
  - `tools/r02_preflight.py`: `READY_FOR_DEVICE_SMOKE` (12/12 проверок пройдены).
  - `tools/r02_audio_qa.py`: `PASS` (1800.0s exact AAC master, peak -1.6dB, SHA `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22` совпадает).
  - `/usr/bin/python3 -m unittest discover -s tests`: `PASS` (229 тестов пройдено, 0 ошибок).
  - `xcodebuild ... RunGameFounderTests`: `PASS` (66 юнита-тестов Swift пройдено).
  - `xcodebuild ... RunGameFounderUITests`: `PASS` (3 UI-теста пройдено на iPhone 16 Pro iOS 18.5 Simulator).

Все 18 полос готовности задокументированы в `docs/PRE_FIRST_TEST_READINESS.md`.

---

## 6. Open Blockers
После успешного offline preflight (`make verify-pretest`) нет инженерных блокеров для начала physical device smoke. Активными остаются исключительно человеческие блокеры (human gates):

1. **Human Route Approval (`binding.human_route_approved`):** Требуется физический дневной обход маршрута основателем в Вальпараисо.
2. **Workout Approval (`binding.workout_approved`):** Требуется физическая проверка интервалов бега/ходьбы и покрытия.
3. **M1-A Human Approval (`binding.human_approved`):** Требуется явное подтверждение основателя после обхода.
4. **Public Start Confirmation (`binding.public_start`):** Требуется проверка публичной доступности точки старта.
5. **Full Audio Lock-Screen Review:** Требуется полное 30-минутное прослушивание M4A мастера на физическом iPhone при заблокированном экране.

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
* **11.08.2026 (R02):** Завершён пре-тестовый харднинг (R02 Max Hardening). Подготовлены 18 полос готовности (`docs/PRE_FIRST_TEST_READINESS.md`), проверены 229 Python-тестов, 72 Swift unit-теста и 5 Swift UI-тестов, включая ASan/TSan (`make verify-pretest`). Статус переведен в `READY_FOR_DEVICE_SMOKE`.
