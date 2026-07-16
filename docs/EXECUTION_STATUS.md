# Журнал выполнения Run Game (EXECUTION_STATUS)

**Последнее обновление:** 16 июля 2026 года
**Текущая фаза:** Research Phase (`R02` — `IN_PROGRESS`, narrative foundation реализована)

---

## 1. Current Product Thesis
> **Твой город становится игровым уровнем: приложение строит тренировочный маршрут через реальные места вокруг дома/старта и превращает их в сцены истории, которая могла произойти только здесь.**

Основные правила:
* Никакой живой генерации LLM во время бега. Вся миссия компилируется до старта в офлайн-бандл (`RouteBundle`).
* Тренировочная сетка (beginner Couch to 5K) имеет абсолютный приоритет и не меняется под сценарий. Сюжет адаптируется под структуру тренировки.
* Приватность: точный дом и GPS-треки не передаются на сервер и не светятся в LLM.

---

## 2. Founder Decisions
* **География продукта:** Home-territory-based. Один пользователь развивает одну активную домашнюю территорию; travel и cross-city continuity не являются фичами MVP.
* **География founder research:** Traveler-based. Текущий город основателя — сменный полевой fixture без попадания города в канон/story state. Бар — только frozen R01 fixture и не ограничивает R02–R03.
* **Стартовый канон:** Выбрана оригинальная вселенная «Нулевой слой», Напарник Леа и центральный поворот «маршруты игрока не спасали, а создавали её». До production engine используется минимальный трёхмиссионный authoring graph; полностью производится пока только M1.
* **Stop-loss:** Проект развивается в режиме хобби для личного использования. Бюджет — личные ИИ-подписки (до $200/мес), бесплатные/дешевые лимиты API.
* **Разрешенные провайдеры:** GraphHopper (маршруты, бесплатный тариф), Overpass API (OSM, бесплатно), Wikipedia API (бесплатно), персональные API-ключи LLM (OpenAI/Anthropic/Gemini) через `.env`.
* **Контроль безопасности:** Двухуровневый. Автоматический ИИ-фильтр (Smart AI Safety Validator) + ручной аппрув основателя перед каждым выходом.

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
| **R02** | `IN_PROGRESS`| `R01` | Созданы `R02_NARRATIVE_PROOF.md`, scorecard трёх миров, выбран «Нулевой слой», machine-readable M1–M3 graph (32 nodes, 38 edges, 8 paths), полный M1 A/B beat draft, privacy-safe binding/run fixtures, stdlib validator и 14 passing tests. | 16.07.2026 | В текущем городе вручную утвердить public loop и 3 geo slots, собрать temp audio и пройти M1-A founder dry run. |
| **R03** | `NOT_STARTED`| `R02` | Нет. | 15.07.2026 | Ожидает выполнения R02. |
| **R04** | `NOT_STARTED`| `R02` | Нет. | 15.07.2026 | Ожидает выполнения R02 (может идти параллельно с R03). |

*(Этапы P01–P22 находятся в статусе `NOT_STARTED` и ожидают прохождения ворот G0).*

---

## 5. Command Evidence
Ниже фиксируются запущенные в процессе разработки команды проверки:
1. `git status` — чистый статус репозитория перед добавлением документов.
2. `git clone https://github.com/DoroninDobroCorp/TerraIncognita.git` — успешный импорт и аудит существующего кода карт/маршрутов основателя.
3. `python3 scratch/r01_feasibility_bar.py` — успешный запуск скрипта гео-аудита и сбор кэша Overpass по г. Бар, Черногория.
4. `python3 tools/r02_story.py validate` — graph, M1 beats, scorecard и draft binding прошли semantic validation; graph содержит 8 путей.
5. `python3 -m unittest discover -s tests -p 'test_*.py' -v` — 14/14 narrative process tests прошли.

---

## 6. Open Blockers
Нет критических блокеров для продолжения R02. Для завершения этапа отсутствуют реальные human-approved route binding, временное аудио, founder dry run и A/B parity evidence. Точная fitness-сетка остаётся narrative fixture до review профильного специалиста.

---

## 7. Decision Log
* **15.07.2026 (P00):** Принято решение использовать код `TerraIncognita` (а именно парсеры OSM/Overpass и логику коридорной маршрутизации) как основу для адаптеров `PoiProvider` и `RouteProvider` в Run Game.
* **15.07.2026 (P00):** Переориентирован фокус проекта на персональное использование (хобби) с минимизацией серверных костов и распараллеливанием тестов спроса (R04) и опыта (R03).
* **15.07.2026 (R01):** Бар использован как первый research fixture. Все 20 стартов дали минимум два POI-кандидата (исторически это было названо «100% L2»); текущий технический L2 дополнительно требует route candidates, scorer и bundle, поэтому R01 трактуется только как POI-density signal.
* **16.07.2026 (R02):** Разделены `home-territory product behavior` и `traveler-based founder research`. Бар перестал быть обязательной географией R02–R03; смена города не стала продуктовой или сюжетной механикой.
* **16.07.2026 (R02):** Принято story-first решение: authoring graph обязателен сейчас, production runtime graph engine откладывается. Сравнены Dracula-inspired, future-frequency и erased-trace concepts; provisional winner — оригинальный «Нулевой слой» (93/100). Это редакционная гипотеза, не field evidence.
* **16.07.2026 (R02):** Зафиксированы Леа, M1–M3 micro-arc, три enum-state, четыре setup clues и reveal «игрок своими маршрутами создал Леа». Реализованы детерминированная линеаризация, A/B contract и запрет participant export до human approval.
