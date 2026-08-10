# Журнал выполнения Run Game (EXECUTION_STATUS)

**Последнее обновление:** 10 августа 2026 года
**Текущая фаза:** Research Phase (`R02` — `IN_PROGRESS`, narrative foundation реализована)

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
| **R02** | `IN_PROGRESS`| `R01` | Созданы `R02_NARRATIVE_PROOF.md`, scorecard трёх миров, выбран «Нулевой слой», M1–M3 graph (32 nodes, 38 edges, 8 paths), M1 A/B beat draft и stdlib validator. Активная founder fixture — центральный Вальпараисо: Plaza de la Victoria ➔ Arco Británico ➔ Parque Italia ➔ Plaza O'Higgins. Есть fixed-time 1800s master, offline bundle/preflight tooling, privacy-safe GPX analyzer и локальный founder-only SwiftUI research slice. 27 `NAV` cues являются workout transitions, не turn-by-turn; geo/fallback не запускаются по runtime location. Текущий local binding сохраняет route/workout/human approvals `false`. Консолидированные automated counts для текущего shared worktree будут записаны только после отдельного фактического прогона; physical-device/audio/walk/run evidence отсутствует. | 10.08.2026 | Offline preflight ➔ physical-device smoke ➔ дневной walk-through/derived report ➔ human route approval ➔ полный lock-screen audio check ➔ GPS-gated solo founder run ➔ immediate JSON/queued 24h recall ➔ R02C parity. |
| **R03** | `NOT_STARTED`| `R02` | Нет. | 15.07.2026 | Ожидает выполнения R02. |
| **R04** | `NOT_STARTED`| `R02` | Нет. | 15.07.2026 | Ожидает выполнения R02 (может идти параллельно с R03). |

*(Этапы P01–P22 находятся в статусе `NOT_STARTED` и ожидают прохождения ворот G0).*

---

## 5. Command Evidence

Исторические engineering checkpoints до текущего hardening включали story
validation, Valparaíso OSM identity check, master SHA/duration verification,
iOS resource preparation и simulator build/tests. Эти записи не являются
physical field evidence и не доказывают текущий shared worktree после новых
изменений.

Финальные команды и counts текущего consolidated run будут внесены сюда только
после их фактического запуска. Entry point его offline-части — `make verify`;
simulator build/tests фиксируются отдельно. Отдельный bundle gate —
`make r02-preflight`. После реального walk-through raw GPX анализируется локально через
`make r02-analyze-gpx GPX=/absolute/local/path/to/walkthrough.gpx`; в LLM по
умолчанию передаётся только privacy-safe derived JSON.

---

## 6. Open Blockers
После успешного offline preflight нет известного инженерного блокера для начала
device smoke. Для завершения R02 всё ещё отсутствуют:

- physical-device install/background audio/GPS/partial-recovery evidence;
- дневной walk-through, derived route/timing analysis и ручной route/workout
  approval;
- полное lock-screen прослушивание фактического audio SHA;
- GPS-gated founder run, immediate debrief и отдельный queued 24-hour unaided
  recall JSON;
- R02C A/B parity evidence и закрытие критичных defects.

Точная fitness-сетка остаётся личной narrative fixture до review профильного
специалиста. Неудачный preflight, плохой маршрут, непригодные cue deltas или
device/audio incident являются stop condition, а не поводом выдать approval.

---

## 7. Decision Log
* **15.07.2026 (P00):** Принято решение использовать код `TerraIncognita` (а именно парсеры OSM/Overpass и логику коридорной маршрутизации) как основу для адаптеров `PoiProvider` и `RouteProvider` в Run Game.
* **15.07.2026 (P00):** Переориентирован фокус проекта на персональное использование (хобби) с минимизацией серверных костов и распараллеливанием тестов спроса (R04) и опыта (R03).
* **15.07.2026 (R01):** Бар использован как первый research fixture. Все 20 стартов дали минимум два POI-кандидата (исторически это было названо «100% L2»); текущий технический L2 дополнительно требует route candidates, scorer и bundle, поэтому R01 трактуется только как POI-density signal.
* **16.07.2026 (R02):** Разделены `home-territory product behavior` и `traveler-based founder research`. Бар перестал быть обязательной географией R02–R03; смена города не стала продуктовой или сюжетной механикой.
* **16.07.2026 (R02):** Принято story-first решение: authoring graph обязателен сейчас, production runtime graph engine откладывается. Сравнены Dracula-inspired, future-frequency и erased-trace concepts; provisional winner — оригинальный «Нулевой слой» (93/100). Это редакционная гипотеза, не field evidence.
* **16.07.2026 (R02):** Зафиксированы Леа, M1–M3 micro-arc, три enum-state, четыре setup clues и reveal «игрок своими маршрутами создал Леа». Реализованы детерминированная линеаризация, A/B contract и запрет participant export до human approval.
* **07.08.2026 (R02):** Разрешён локальный founder-only SwiftUI slice как
  research exception для повторяемых M1 device/audio/GPS итераций. Production
  investment gates и запрет внешних участников не изменены.
* **10.08.2026 (R02):** Активной полевой фикстурой закреплён центральный
  Вальпараисо; Santiago переведён в неактивный локальный архив. Fixed-time
  master не считается geo-triggered runtime: первый walk-through и retiming
  review обязательны до founder run. Raw GPX по умолчанию остаётся локально;
  для разбора используется derived report без координат и точного старта.
