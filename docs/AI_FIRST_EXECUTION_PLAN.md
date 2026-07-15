# Run Game — AI-first execution plan

**Версия:** 1.1
**Дата:** 15 июля 2026 года
**Назначение:** последовательность автономных, paste-ready задач для новых Codex-чатов, которые не видели предыдущую переписку.

## Что строится

Текущее продуктовое ядро:

> **Твой город становится игровым уровнем: приложение строит beginner run/walk маршрут через реальные места вокруг старта и превращает их в сцены авторской истории, которая могла произойти только здесь.**

Пользователь один раз задаёт старт, а перед сессией подтверждает тренировку текущего дня или переносит её. Утверждённая beginner-программа задаёт fitness timeline. Детерминированные компоненты отвечают за POI, маршрут, ограничения, scoring и runtime. Автор отвечает за канон и опорные сцены. ИИ разрешено лишь связывать проверенные географические данные с разрешёнными сценами; он не прокладывает путь, не выдумывает POI или факты, не меняет fitness timeline и не является live-зависимостью во время пробежки.

Цель плана — передать максимум реализации новым AI-чатам, не потеряв границы продукта, доказательность ворот и возможность остановить коммерчески нецелесообразный проект. Этот файл сам по себе не разрешает разработку: каждый следующий промпт запускается владельцем проекта отдельно.

## Как пользоваться планом

1. Запускай **один промпт в одном новом Codex-чате** и вставляй его целиком.
2. Иди строго по зависимостям ниже. Не запускай параллельно этапы, которые меняют общие доменные контракты. Research-прототип до `G0` намеренно не является production foundation.
3. Первый чат создаёт `docs/EXECUTION_STATUS.md`. Все следующие чаты обязаны читать его и менять только строку/журнал своего этапа и соответствующего gate.
4. Новый чат не должен верить названию этапа: он сначала проверяет репозиторий, предыдущие deliverables и фактические тесты.
5. Если prerequisite или реальный внешний результат отсутствует, чат не изображает успех. Он фиксирует `BLOCKED` либо `NO-GO`, оставляет воспроизводимые доказательства и останавливается.
6. Provider credentials, Apple signing, набор участников и публикация — внешние зависимости. Их отсутствие разрешает fixtures, dry-run и подготовку, но не разрешает объявлять соответствующий gate пройденным.
7. Коммит не является доказательством. Доказательство — файлы, воспроизводимые команды, тесты, отчёты, реальные field data и явно записанный gate decision.
8. После каждого этапа прочитай итог агента и `docs/EXECUTION_STATUS.md`. Только затем переходи к следующему промпту.

## Инварианты для всех этапов

- `docs/README.md` — обязательная точка входа и источник порядка приоритета документов.
- При конфликте действуют `GEO_NARRATIVE_PRODUCT_STRATEGY.md`, затем `GEO_NARRATIVE_TECHNICAL_SPEC.md`, затем этот план. Исторические документы не переопределяют geo-narrative решение.
- Начальная география русскоязычной когорты пока должна считаться отдельным founder decision. Нельзя подбирать географию после просмотра результатов coverage audit.
- Код основателя по картам может отсутствовать. Любая интеграция идёт через адаптеры (`PoiProvider`, `RouteProvider`, позднее `MapSurface`/эквивалент), без выдумывания его внутренней архитектуры и без переписывания несвязанного кода.
- Все единицы измерения и координатный порядок типизированы; случайное смешение метров/километров, секунд/минут и `lat/lon`/`lon/lat` недопустимо.
- Unit/integration tests не зависят от live Overpass, GraphHopper, Wikimedia, LLM, TTS или сети. Live smoke tests — отдельные opt-in команды.
- Публичные OSM tiles, Overpass, Nominatim и Wikidata SPARQL не становятся production runtime-backend.
- Hard filters и маршрутная пригодность детерминированы и объяснимы. Единого непрозрачного `AI safety/route score` нет.
- Точный дом, raw GPS trace и health data не попадают в обычную аналитику или LLM.
- Основная миссия после компиляции должна исполняться без сети. Live LLM никогда не блокирует навигацию или тренировку.
- До реального однокомпонентного geo-story field gate и deposit/preorder gate запрещены production contracts/pipeline и iOS. Apple Watch, Android, multiplayer, свободный NPC dialogue, погода, computer vision, 27 миссий и marketplace запрещены до Paid MVP.
- Есть три разные проверки, которые нельзя сливать: **одна Wizard-of-Oz миссия проверяет ценность места**, **шесть сессий проверяют реальное возвращение к тренировке**, **Paid MVP проверяет willingness to pay и экономику**.
- Главная поведенческая метрика продукта — фактический старт следующей запланированной тренировки. Ответ «эта миссия потеряла бы смысл в другом районе» и recall мест — manipulation checks географического компонента, а не North Star.

## Формат `EXECUTION_STATUS.md`

Первый этап создаёт журнал как минимум с такими секциями:

```text
Current product thesis
Founder decisions
Gate register
Stage table: ID | status | prerequisites | evidence | last updated | next action
Command evidence
Open blockers
Decision log
```

Допустимые статусы этапа: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `COMPLETE`.
Допустимые решения gate: `PENDING`, `GO`, `NO-GO`, `PIVOT_REQUIRED`.

`COMPLETE` означает, что acceptance criteria этапа подтверждены текущим состоянием репозитория. `GO` выставляется только там, где перечисленные доказательства действительно существуют.

## Зависимости и инвестиционные ворота

| Порядок | ID | Этап | Prerequisite | Что открывает |
|---:|---|---|---|---|
| 0 | P00 | Документальный аудит | нет | `G0_DOCS` |
| 1 | R01 | Lightweight audit 20–30 стартов | `G0_DOCS=GO` + выбранная test geography | research feasibility |
| 2 | R02 | Одномиссионный Wizard-of-Oz generator | R01 | готовый geo component proof |
| 3 | R03 | Component A/B в поле | R02 | `G0_GEO_PROOF` |
| 4 | R04 | Refundable deposit/preorder smoke test | R02 | `G0_DEMAND` |
| 5 | P01 | Production domain contracts | `G0_GEO_PROOF=GO` и `G0_DEMAND=GO` | база headless-системы |
| 6 | P02 | Production coverage harness | P01 | единый измерительный контур |
| 7 | P03 | POI ingestion и adapters | P01–P02 | реальные landmark candidates |
| 8 | P04 | Routing adapter | P01–P02 | route candidates и reconnect |
| 9 | P05 | Candidate scorer | P03–P04 | объяснимый выбор маршрута |
| 10 | P06 | Story schema | P01 | валидируемый авторский контракт |
| 11 | P07 | Deterministic scene assignment | P05–P06 | география назначена сценам |
| 12 | P08 | AI story binder + validators | P06–P07 | ограниченная AI-локализация |
| 13 | P09 | Mission Compiler + RouteBundle | P02–P08 | `G1_COMPILER` |
| 14 | P10 | Аудит 300 стартов | `G1_COMPILER=GO` | `G2_COVERAGE` перед broad promise |
| 15 | P13 | iOS shell | `G2_COVERAGE=GO` | мобильный vertical slice |
| 16 | P14 | Deterministic iOS runtime | P13 | исполнимая миссия |
| 17 | P15 | GPS/navigation/audio | P14 | location-aware проход |
| 18 | P16 | Offline bundle/map | P14–P15 | прохождение без сети |
| 19 | P17 | Recovery/reroute | P15–P16 | устойчивость к сбоям |
| 20 | P18 | Privacy-safe analytics | P14–P17 | измеримый MVP |
| 21 | P19 | Шестисессионный content pack | P09, P14–P18 | behavioral alpha content |
| 22 | P20 | Internal TestFlight readiness | P13–P19 | internal build |
| 23 | P20A | Runtime reliability field gate | P20 | `G3_RUNTIME_RELIABILITY` |
| 24 | P20B | Шестисессионная behavioral alpha | `G3_RUNTIME_RELIABILITY=GO` | `G4_BEHAVIORAL_RETENTION` |
| 25 | P21 | Commercial readiness audit | реальные R03, R04, P10, P20A–P20B | `G5_COMMERCIAL` |
| 26 | P22 | Ограниченный Paid MVP | `G5_COMMERCIAL=GO` | реальная платная проверка |

Полный 300-start audit намеренно стоит **после** дешёвого proof ценности места, но **до** широкого географического обещания. Шестисессионная retention alpha начинается только после отдельного runtime reliability gate: плохой GPS/audio runtime нельзя спутать с отсутствием narrative pull.

Идентификаторы `P11` и `P12` намеренно выведены из плана после переноса Wizard-of-Oz и field A/B в дешёвую research-фазу `R01–R04`. Отсутствующих промптов искать не нужно.

---

## P00 — документальный аудит и журнал выполнения

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, затем все документы, которые он помечает актуальными и авторитетными, минимум docs/GEO_NARRATIVE_PRODUCT_STRATEGY.md, docs/GEO_NARRATIVE_TECHNICAL_SPEC.md и docs/AI_FIRST_EXECUTION_PLAN.md. Исторические документы используй только для поиска конфликтов. Проверь git status --short, структуру через rg --files, существующие manifests, тесты и незакоммиченные изменения. Репозиторий — источник истины. Сохраняй несвязанные и пользовательские изменения. Если founder map code отсутствует, используй только adapters PoiProvider/RouteProvider/MapSurface; не создавай его вымышленную внутреннюю реализацию. Проверяй утверждения об API только по официальной документации и фиксируй дату/ссылку. Не расширяй scope. Выполни уместные проверки и тесты. В конце обязательно создай/обнови docs/EXECUTION_STATUS.md с доказательствами, командами, blockers и следующим допустимым этапом.

Задача: провести документальный аудит до начала кода.

Сделай:
1. Построй таблицу приоритета и назначения всех файлов docs.
2. Найди противоречия между актуальным geo-narrative решением и историческими планами; не усредняй их.
3. Выдели недостающие founder decisions: прежде всего географию первой русскоязычной когорты, stop-loss, допустимых providers и владельца полевого safety review.
4. Преврати все gates и kill criteria текущих спецификаций в единый register с требуемыми доказательствами.
5. Зафиксируй, какие части founder map implementation реально присутствуют, отсутствуют или неизвестны. Ничего за него не выдумывай.
6. Создай docs/DOCUMENT_AUDIT.md и начальный docs/EXECUTION_STATUS.md. Исправляй docs/README.md только если его индекс объективно сломан, без переписывания стратегии.

Не делай: код приложения, compiler, provider integrations, выбор рынка за основателя, новые продуктовые фичи.

Deliverables:
- docs/DOCUMENT_AUDIT.md;
- docs/EXECUTION_STATUS.md;
- при необходимости минимальная коррекция ссылок docs/README.md.

Acceptance criteria:
- для каждого авторитетного документа указан статус и приоритет;
- каждый конфликт имеет решение по действующему приоритету либо явный blocker;
- каждый gate имеет owner, evidence и правило GO/NO-GO;
- география 300-start audit не подменена догадкой;
- G0_DOCS=GO только если выбрана либо явно запрошена test geography и нет блокирующей неоднозначности для R01; иначе P00=BLOCKED и указан один конкретный вопрос владельцу;
- git diff не содержит продуктового или программного scope вне аудита.

В финале перечисли изменённые файлы, выполненные команды, решение G0_DOCS и единственный следующий допустимый prompt R01.
```

## R01 — lightweight feasibility audit на 20–30 стартах

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и все помеченные там актуальные документы, минимум GEO_NARRATIVE_PRODUCT_STRATEGY, GEO_NARRATIVE_TECHNICAL_SPEC, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P00=COMPLETE и G0_DOCS=GO. Затем инспектируй git status --short, rg --files, manifests, tests и существующий founder map code. Сохраняй несвязанные изменения. Если founder map code отсутствует, используй тонкие research adapters/fixtures; не проектируй production platform. Все внешние API и usage policies проверяй по официальным docs. Не расширяй scope. Запусти уместные проверки и обнови только R01 в docs/EXECUTION_STATUS.md.

Задача: максимально дёшево проверить географическую осуществимость в 20–30 заранее выбранных стартах одной launch/test geography до production contracts.

До данных зафиксируй:
- выбранную владельцем test geography и способ набора русскоязычных iPhone testers;
- 20–30 публичных стартов: плотный центр, обычный жилой район, окраина, малый город/пригород и заведомо сложные точки;
- beginner week-1 distance/time budget;
- seed, dataset checksum, manual QA checklist и правила успеха/отказа.

Разрешена лёгкая research-реализация: cached OverpassResearch/Wikipedia lookup, hosted routing trial, существующий founder prototype или небольшой script. Всё должно находиться за простыми adapters, чтобы не стать случайной production архитектурой. Для каждого старта сохрани raw/eligible POI, route, distance error, known access violations, landmark/scene possibilities, latency/cost и L2/L1/failure. Каждый выбранный route/POI проверь вручную по доступным данным; реальные полевые точки для R02 выбирает человек.

Не делай: production DB/contracts, 300-start audit, маркетинговое «работает везде», iOS, LLM prose, оптимизацию thresholds после результата.

Deliverables:
- frozen research starts dataset и checksum;
- lightweight harness/scripts/adapters с cache;
- per-start records и честный research report;
- shortlist минимум 3 разных полевых routes либо NO-GO;
- recorded limitations и provider policies.

Acceptance criteria:
- все 20–30 стартов сохранены, включая failures;
- результаты воспроизводимы из cache без повторных публичных запросов;
- ни один private/foot=no known segment не считается пригодным;
- manual QA отделена от автоматических эвристик;
- отчёт прямо отвечает, достаточно ли материала для одной Wizard-of-Oz миссии, но не делает вывод о global coverage;
- R01 COMPLETE только с реальными research data; иначе BLOCKED/NO-GO.

В финале дай denominators, failure taxonomy, shortlist, cost и единственный следующий R02 либо stop/pivot.
```

## R02 — одномиссионный Wizard-of-Oz generator

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь R01=COMPLETE. Инспектируй git status --short, rg --files, manifests/tests и research assets; сохраняй несвязанные изменения. Карты и маршруты идут через research adapters либо founder adapter; при отсутствии founder code не строй production замену. Проверяй GPX/GeoJSON/provider/TTS contracts по official docs. Не расширяй scope и не начинай iOS. Добавь tests, запусти их и обнови R02.

Задача: сделать один author-reviewed mission template и Wizard-of-Oz generator для component proof.

Generator из `start + approved workout id текущего дня` должен выпускать:
- human-reviewed route preview, GeoJSON/GPX и ordered POIs;
- provenance/confidence и reasons по каждому месту;
- один авторский story template с 2–3 POI-slots, дополнительными временными beats и полными fallbacks;
- localized script/cue sheet, workout timeline и maneuver exclusions;
- заранее подготовленные audio/TTS assets либо ясный operator playback plan;
- participant bundle без точного дома;
- обязательный human approve/reject до export;
- две экспериментальные версии одного опыта: A с настоящим geo-grounding и B с тем же route, training, длиной и production value, но без связи реальных мест с драматургией;
- возможность сгенерировать следующую запланированную тренировку тем же единственным template, чтобы позднее измерить реальный next-workout start без производства сезона.

Не делай: production compiler, 6 миссий, live LLM, recruitment, iOS.

Acceptance criteria:
- A/B отличаются только place-grounding;
- route, POIs и scripts вручную проверены минимум для dense, ordinary residential и small/sparse routes;
- participant export невозможен без human_approved=true;
- AI/TTS failure имеет authored fallback;
- exact start/end скрыты из share/research artifacts;
- один полный dry run проходит по cue sheet;
- R02 COMPLETE только после закрытия critical review defects.

В финале дай generator command/process, approved routes, A/B parity evidence и следующие R03/R04.
```

## R03 — одномиссионный component A/B в поле

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь R02=COMPLETE. Инспектируй git status --short, rg --files, research assets/tests и сохраняй несвязанные изменения. Карты/маршруты остаются за adapters; если founder map code отсутствует, используй research adapters/fixtures, не выдумывая его internals. Не связывайся с участниками, не публикуй формы и не проводи внешние действия без явного разрешения владельца. Не фабрикуй результаты. Не расширяй scope. Запусти analysis tests на явно synthetic data и обнови R03/G0_GEO_PROOF.

Задача: preregister и провести дешёвый field component A/B одной миссии.

Conditions:
- A: route+training+story с локальными местами как необходимыми сценами;
- B: тот же route, training, timing, voice quality и story beats, но реальные места не несут драматургической функции.

Главный ранний behavioral outcome — **фактический старт следующей заранее запланированной тренировки** в установленном окне, а не оценка «понравилось». Для этого каждому участнику до первой миссии назначается следующая тренировка, сгенерированная тем же single-template prototype. Place-specificity question, recall ≥2 мест и тезис «потеряло бы смысл в другом районе» являются manipulation checks: они доказывают, что A действительно создала географический компонент, но сами не доказывают retention.

До первого участника зафиксируй sample rationale, randomization, primary window/threshold, manipulation checks, exclusions, stopping rule, incident/abort flow, consent/privacy и analysis plan. Public starts предпочтительнее дома. Создай randomizer, anonymized schema, survey/event forms, analysis script и blank report.

Если реальных данных нет, оставь R03=BLOCKED/READY_FOR_FIELD и точно перечисли human actions. Если есть, заморозь raw checksum и анализируй только preregistered plan.

Acceptance criteria для G0_GEO_PROOF=GO:
- реальные, не synthetic runs;
- A/B parity подтверждена;
- manipulation checks показывают, что geo-grounding реально заметен;
- next-scheduled-workout start не хуже control и даёт заранее определённый practically meaningful сигнал, либо qualitative proof достаточно только для ограниченного production investment по preregistered правилу;
- нет unresolved critical route/content incidents;
- denominators/exclusions раскрыты.

В финале дай status реальных данных, behavioral outcome, manipulation checks, incidents, решение G0_GEO_PROOF и следующий R04 либо stop/pivot.
```

## R04 — refundable deposit/preorder gate

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь R02 COMPLETE и изучи доступные R03 evidence. Инспектируй repo, git status --short, rg --files и existing concept assets; сохраняй несвязанные изменения. Если founder map code отсутствует, оставь все map integrations за существующими adapters/fixtures; для smoke test он не нужен и не должен переписываться. Текущие payment/refund/privacy/advertising правила проверяй по official sources. Не публикуй страницу, не принимай деньги и не отправляй сообщения без явного разрешения владельца. Не расширяй scope. Проверь landing/forms/funnel instrumentation уместными tests/validations. Обнови R04/G0_DEMAND.

Задача: подготовить и, только при явной авторизации, провести ранний честный smoke test с реальным refundable deposit/preorder, используя фактическую демонстрацию R02, а не обещание несуществующих функций.

Зафиксируй до трафика:
- конкретную аудиторию/географию/канал;
- один price/deposit offer и refund terms;
- traffic/spend/time stop-loss;
- primary metric: completed real deposit/preorder на qualified visitor;
- minimum GO threshold и NO-GO rule;
- distinction между email signup и деньгами;
- privacy, support и ручной refund process.

Создай минимальные assets/landing/analytics только в рамках существующего repo stack; если сайта нет, подготовь implementation-ready spec и copy, не создавая новый unrelated web product. Synthetic clicks/orders запрещены в итоговых denominators.

Acceptance criteria для G0_DEMAND=GO:
- реальные qualified visitors и реальные refundable deposits/preorders;
- сумма/условия/возврат раскрыты;
- bot/internal traffic исключён по preregistered правилам;
- spend stop-loss соблюдён;
- результат сравнивается с заранее заданным threshold;
- при отсутствии разрешения/трафика gate остаётся PENDING, не GO.

В финале сообщи funnel denominators, реальные деньги/обязательства, spend, refunds, решение G0_DEMAND и следующий P01 только если одновременно G0_GEO_PROOF=GO.
```

## P01 — production доменные контракты headless-ядра

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и все помеченные там актуальные документы, минимум GEO_NARRATIVE_PRODUCT_STRATEGY, GEO_NARRATIVE_TECHNICAL_SPEC, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь, что R03 зафиксировал G0_GEO_PROOF=GO на реальных field data, а R04 — G0_DEMAND=GO на реальных refundable deposits/preorders; иначе остановись без production-кода. Затем инспектируй репозиторий через git status --short, rg --files, manifests и тесты. Сохраняй несвязанные изменения. Если founder map code отсутствует, используй только адаптерные интерфейсы PoiProvider/RouteProvider/MapSurface и fixtures; не создавай фиктивную внутреннюю реализацию основателя. Проверяй внешние контракты по официальным docs. Не расширяй scope. Добавь тесты, запусти их и обнови только относящиеся к P01 части docs/EXECUTION_STATUS.md.

Задача: после доказанных G0 gates создать минимальные production-grade, provider-independent доменные контракты для headless geo-story compiler. Research shortcuts R01–R02 нельзя переносить молча: замени их либо оберни явным adapter. Следуй существующему стеку; если кода ещё нет, выбери самый маленький поддерживаемый headless stack, обоснуй выбор коротким ADR и не начинай iOS.

Контракты должны покрывать:
- GeoPoint/GeoEnvelope/RouteCorridor с явным coordinate order;
- meters, seconds, pace/speed и DistanceBudget без неявных единиц;
- TrainingPlan и workout timeline;
- Landmark, provenance, archetypes, access/sensitivity flags, approved facts и confidence;
- Route, edge/path attributes, maneuvers и matched trace;
- Candidate, rejection reason и ScoreBreakdown;
- provider protocols PoiProvider и RouteProvider;
- стабильную сериализацию, schema version и typed error taxonomy;
- FixturePoiProvider и FixtureRouteProvider.

Не делай: реальные HTTP integrations, scoring policy, LLM, iOS, database deployment.

Deliverables:
- доменный package в принятой структуре repo;
- публичные schemas/types и provider protocols;
- fixtures;
- ADR выбора stack/units/coordinate order;
- unit tests.

Acceptance criteria:
- lat/lon и lon/lat нельзя случайно поменять без явного conversion;
- meters/seconds нельзя смешать с km/min без conversion;
- сериализация round-trips без потери version/provenance;
- fixture providers детерминированы seed-ом;
- provider-specific JSON не протекает в domain layer;
- все тесты проходят одной документированной командой;
- P01 отмечен COMPLETE только с command evidence.

В финале укажи API-контракты, тестовые команды, изменённые файлы и следующий P02.
```

## P02 — production coverage harness до реальных providers

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md и все актуальные документы из его индекса, включая GEO_NARRATIVE_PRODUCT_STRATEGY, GEO_NARRATIVE_TECHNICAL_SPEC, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P01=COMPLETE. Инспектируй repo через git status --short, rg --files, manifests и tests; сохраняй несвязанные изменения. Отсутствующий founder map code подключается только через adapters PoiProvider/RouteProvider/MapSurface; fixtures являются нормальным fallback. Проверяй API по официальным источникам. Не расширяй scope. Добавь и запусти тесты. Обнови только P02 и связанные evidence в EXECUTION_STATUS.

Задача: построить детерминированный coverage harness, который позже одинаково измерит fixtures, research adapters и production adapters.

Harness должен:
- принимать versioned CSV/JSONL стартов без точных домашних адресов;
- принимать workout/distance budget, seed и injected providers;
- сохранять per-start machine-readable результат и aggregate summary;
- считать raw POI, POI после hard filters, archetypes, route candidates, best score, target error, penalties, L2/L1/failure, compile latency и source confidence;
- сохранять typed rejection reasons;
- поддерживать resume, cache и повторяемый seed;
- по умолчанию работать полностью offline на fixtures;
- иметь opt-in live mode, который никогда не запускается в обычных tests;
- генерировать JSON/JSONL и читаемый Markdown report;
- заранее показывать thresholds из технической спецификации, но не менять их по результатам.

Не делай: реальные 300 стартов, live provider calls в CI, iOS, story generation.

Deliverables:
- CLI/library coverage harness;
- маленький synthetic start dataset: dense, sparse, insufficient, malformed;
- golden reports;
- tests на determinism, resume, rejection reasons и aggregation;
- краткая инструкция запуска.

Acceptance criteria:
- два запуска с одинаковым seed дают byte-stable canonical results, исключая явно обозначенное timing field;
- failed start не рушит batch;
- summary численно сверяется с per-start records;
- ни одна метрика не зависит от LLM;
- live mode требует явного flag/env и не вызывается tests;
- P02 COMPLETE подтверждён command evidence.

В финале перечисли артефакты, команды, ограничения harness и следующий P03.
```

## P03 — POI ingestion, normalization и adapters

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и актуальные документы, минимум обе GEO_NARRATIVE спецификации, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P01–P02 COMPLETE. Инспектируй git status --short, rg --files, manifests/tests и существующий картографический код. Сохраняй несвязанные изменения. Founder map code, если он отсутствует или неполон, подключай только через PoiProvider adapter; не переписывай и не блокируй весь этап. Любые OSM/Wikimedia контракты сверяй с официальной документацией и лицензиями. Не расширяй scope. Все network tests замени fixtures/recordings с удалёнными координатами. Запусти tests и обнови P03 в EXECUTION_STATUS.

Задача: реализовать воспроизводимый pipeline Landmark Index и POI adapters.

Нужно:
1. Нормализовать OSM elements в Landmark с source provenance, tags, geometry, archetypes, access/sensitivity flags и confidence.
2. Реализовать dedup OSM node/way/relation и связей wikidata/wikipedia.
3. Реализовать hard filters текущей спецификации и typed rejection reasons.
4. Добавить OverpassResearchProvider только для audit/prototype: User-Agent, timeout, retry/backoff, cache, rate-limit handling; явно запретить production runtime.
5. Добавить server-cached Wikipedia GeoSearch/enrichment adapter; не использовать WDQS как runtime dependency.
6. Добавить production-facing PostgisPoiProvider contract, schema/migration и repository implementation либо строго ограниченный scaffold, если инфраструктуры ещё нет.
7. Добавить FounderPoiProviderAdapter seam без предположений о коде основателя.
8. Хранить license/source links и approved facts отдельно от сырых текстов.

Не делай: scraping мира, публичный Nominatim autocomplete, AI-факты, route generation, UI.

Deliverables:
- ingestion/normalization code;
- research, fixture, PostGIS и founder adapter boundaries;
- DB schema/migration, если стек это поддерживает;
- sanitized source fixtures;
- tests на normalization, dedup, filters, provenance, cache/error behavior;
- operational note о data refresh и лицензиях.

Acceptance criteria:
- ни один filtered private/foot=no/sensitive объект не возвращается как eligible;
- unknown не превращается в safe/accessible;
- duplicate source objects дают один canonical Landmark с provenance;
- Wikipedia text не копируется без source/license metadata;
- public services не являются production default;
- coverage harness умеет прогонять fixture provider;
- P03 COMPLETE только при зелёных tests.

В финале сообщи mapping tags→archetypes, provider boundaries, команды и следующий P04.
```

## P04 — routing adapter и route evidence

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md и актуальные документы, включая обе GEO_NARRATIVE спецификации, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P01–P02 COMPLETE. Инспектируй git status --short, rg --files, manifests/tests и наличие founder routing code. Сохраняй несвязанные изменения. Если founder code отсутствует, реализуй RouteProvider adapter seam и fixtures; не изобретай/не переписывай его internals. Текущий GraphHopper API, pricing/credits и ограничения проверь только по официальной документации, зафиксируй дату. Live calls не входят в обычные tests. Не расширяй scope. Запусти tests и обнови P04 в EXECUTION_STATUS.

Задача: реализовать MVP RouteProvider поверх hosted GraphHopper с provider-neutral domain output.

Поддержи:
- roundTrips(start, budget, seed, heading, pedestrian profile);
- viaPoints(start, ordered waypoints, profile);
- reconnect(current, next target optional, start zone, remaining budget);
- mapMatch как отдельную capability или явный NotSupported;
- timeout, bounded retry/backoff, cancellation и typed provider errors;
- request credit estimate/telemetry без координат в логах;
- response validation, route provenance/data version;
- sanitized fixture recordings;
- FounderRouteProviderAdapter seam;
- optional live smoke command за env flag.

Не делай: собственный routing cluster, Valhalla migration, on-device routing, route pleasantness в adapter, background iOS navigation.

Deliverables:
- GraphHopper adapter;
- fixture/fake provider;
- founder adapter seam;
- response parser/validator;
- tests на request construction, coordinate order, errors, retries, malformed/no-route responses и credit estimate;
- provider decision note.

Acceptance criteria:
- один provider request не может утечь в domain-specific call sites;
- точные координаты отсутствуют в обычных logs/test snapshots;
- round-trip distance трактуется как приблизительная, не гарантия;
- no-route/rate-limit/timeout дают разные typed outcomes;
- tests проходят без ключа и сети;
- live smoke, если выполнен, записан отдельно и не содержит secret;
- P04 COMPLETE подтверждён командами.

В финале перечисли supported capabilities, официальный источник, tests и следующий P05.
```

## P05 — объяснимый Candidate Generator и scorer

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и все актуальные документы из индекса, особенно GEO_NARRATIVE_TECHNICAL_SPEC, AI_FIRST_EXECUTION_PLAN и EXECUTION_STATUS. Проверь P03–P04 COMPLETE. Инспектируй repo, git status --short, rg --files, manifests и tests. Сохраняй несвязанные изменения. Founder map/routing code подключается только через имеющиеся adapters; при отсутствии используй fixtures. Не используй LLM для hard filters или итогового route score. Не расширяй scope. Добавь тесты, запусти их и обнови P05 в EXECUTION_STATUS.

Задача: реализовать Candidate Generator и прозрачный Route+POI scorer.

Алгоритм должен:
- получать reachable POI set и генерировать несколько seed/heading round-trip candidates;
- строить route corridor и along-route positions;
- проверять реальную достижимость/подход к landmark;
- исключать hard violations до scoring;
- считать именованный ScoreBreakdown: distance error, repeated edge, major crossings, elevation, unknown surface/access, maneuver density, POI detour, landmark quality/diversity, narrative role fit, pedestrian/park/waterfront, novelty и fallback bonus;
- иметь стабильный tie-break;
- выдавать L2, fallback L1, coverage_insufficient и объяснение;
- не называть маршрут safe;
- сохранять все candidates и rejection reasons для audit.

Не делай: story prose, AI ranking, UI, live GPS.

Deliverables:
- candidate generation service;
- scoring policy/config с version;
- machine-readable explanation;
- fixtures dense/sparse/coast/disconnected/private/repeated-edge;
- unit/property/golden tests;
- подключение к coverage harness.

Acceptance criteria:
- hard violation невозможно компенсировать высоким soft score;
- изменение одного score component видно в breakdown;
- одинаковый input/seed/config даёт одинаковый winner;
- L2→L1→failure происходит только по записанным правилам;
- edge overlap и target error проверены synthetic cases;
- ни один output не содержит AI safety assertion;
- P05 COMPLETE подтверждён tests.

В финале покажи пример breakdown, команды и следующий P06.
```

## P06 — versioned story schema и authoring contract

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md и актуальные документы, минимум GEO_NARRATIVE_PRODUCT_STRATEGY, GEO_NARRATIVE_TECHNICAL_SPEC, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P01 COMPLETE. Инспектируй git status --short, rg --files, manifests и tests; сохраняй несвязанные изменения. Если founder map code отсутствует, географию подавай только через доменные Landmark/Route adapters; не создавай его вымышленную реализацию. Не расширяй scope до сюжетной песочницы или 27 миссий. Добавь tests и обнови P06 в EXECUTION_STATUS.

Задача: создать строгий versioned Story Template schema, пригодный автору и compiler.

Schema должен описывать:
- template id/version, language, duration range и canon version;
- authored anchor scenes и immutable canonical intent;
- geographic slots, allowed/preferred archetypes, required fields и confidence;
- workout windows, max spoken duration и maneuver exclusions;
- placeholders, forbidden claims/topics и sensitivity policy;
- fallback scene для каждого обязательного slot;
- voice role, audio priority и localization limits;
- story state inputs/effects с idempotency key;
- source/fact requirements;
- migration/version rejection rules.

Создай один минимальный русский mission template только как schema fixture, не как финальную шестимиссионную кампанию.

Не делай: LLM binder, route assignment, озвучку, iOS.

Deliverables:
- machine-readable schema и typed model;
- schema documentation для автора;
- valid/invalid examples;
- tests на required fallback, forbidden unknown fields, versioning, fact requirements и state effects.

Acceptance criteria:
- template без fallback для обязательного slot невалиден;
- canon/state effects нельзя добавить через свободный AI text field;
- длительности и workout windows проверяются;
- unsupported schema version fail-closed;
- fixture проходит round-trip serialization;
- P06 COMPLETE подтверждён tests.

В финале перечисли contract decisions, tests и следующий P07.
```

## P07 — deterministic scene assignment solver

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P05–P06 COMPLETE. Инспектируй repo, git status --short, rg --files, manifests/tests. Сохраняй несвязанные изменения. Используй только domain/adapters для отсутствующего founder map code. LLM не может отменять constraints. Не расширяй scope. Запусти tests и обнови P07 в EXECUTION_STATUS.

Задача: реализовать детерминированный solver `story slots → landmark + along-route scene window`.

Solver должен учитывать:
- allowed archetypes/required fields/confidence;
- порядок landmarks вдоль route;
- workout windows и продолжительность сцены;
- distance separation и отсутствие повторного использования POI без явного разрешения;
- maneuver exclusion zones;
- sensitivity policy;
- обязательные/optional slots;
- fallback scenes;
- stable optimization/tie-break;
- объяснение назначения и список незаполненных slots.

Не делай: генерацию текста, TTS, runtime GPS.

Deliverables:
- assignment solver;
- AssignmentPlan schema с score/explanation/fallback;
- dense, sparse, conflicting и impossible fixtures;
- unit/property/golden tests.

Acceptance criteria:
- solver не назначает несовместимый archetype;
- scene window не пересекает запрещённый maneuver window;
- impossible required slot использует валидный fallback либо typed failure;
- output детерминирован;
- каждое назначение имеет machine-readable reasons;
- P07 COMPLETE подтверждён tests.

В финале покажи один assignment plan, tests и следующий P08.
```

## P08 — AI Story Binder и fail-closed validators

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P06–P07 COMPLETE. Инспектируй repo, git status --short, rg --files, manifests/tests и существующие AI adapters. Сохраняй несвязанные изменения. Founder map code не трогай; binder получает только структурированные Landmark/Assignment данные. Актуальные SDK/API проверяй по официальным provider docs. Если provider/ключ отсутствует, реализуй интерфейс и FakeBinder; не подменяй отсутствие live test успехом. Не расширяй scope до live NPC. Запусти tests и обнови P08 в EXECUTION_STATUS.

Задача: реализовать ограниченный AI Story Binder плюс полный детерминированный validation/fallback path.

Binder input не содержит точной стартовой координаты/дома и включает только canonical intent, approved landmark fields/facts, allowed placeholders, max duration и forbidden claims. Output — versioned LocalizedScene JSON, не свободный текст.

Нужно:
- provider-neutral AI adapter и deterministic FakeBinder;
- versioned system/developer prompt assets;
- strict structured output/schema parsing;
- cache/idempotency по sanitized input+prompt+model version;
- validators: landmark/fact ids существуют, имя не изменено, unsupported factual claim запрещён, нет адреса/экрана/опасной навигационной команды, длина допустима, fallback существует, canon effects неизменны;
- retries только для format repair с жёстким лимитом;
- deterministic authored fallback при timeout/refusal/invalid output;
- adversarial fixtures: invented date, fake POI, changed name, prompt injection in OSM tag, unsafe turn, leaked home.

Не делай: live runtime dependency, voice dialogue, route selection, факты из model memory.

Deliverables:
- AI adapter + fake;
- prompt versions;
- LocalizedScene parser/validators;
- deterministic fallback;
- tests, включая adversarial cases;
- optional opt-in live smoke без secrets.

Acceptance criteria:
- миссия компилируется с отключённым AI через fallback;
- несуществующий fact id всегда rejected;
- model text не может менять route/workout/canon;
- prompt injection из source data остаётся данными;
- exact coordinates отсутствуют в recorded model input;
- tests не ходят в сеть;
- P08 COMPLETE подтверждён evidence.

В финале опиши fail-closed path, model boundary, tests и следующий P09.
```

## P09 — Mission Compiler и versioned RouteBundle

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P02–P08 COMPLETE. Инспектируй git status --short, rg --files, manifests/tests и текущие adapters; сохраняй несвязанные изменения. Отсутствующий founder map code остаётся за PoiProvider/RouteProvider/MapSurface seams. Не добавляй iOS и не расширяй scope. Проверяй внешние API только по official docs. Запусти полный headless test suite и обнови P09/G1_COMPILER в EXECUTION_STATUS.

Задача: собрать end-to-end Mission Compiler и immutable RouteBundle.

Compiler pipeline:
Training Planner → landmarks → route candidates → scorer → story template → assignment → binder/validators → asset manifest → RouteBundle.

RouteBundle должен включать schema version, ids, generation/expiry, route polyline/corridor/maneuvers, expected distance/duration range, workout timeline, landmarks/provenance, scenes/windows/fallbacks, audio asset manifest/checksums, optional offline map descriptor, story inputs/effects, policies и compiler versions.

Нужно:
- dependency injection для всех providers;
- CLI/API compile command;
- typed failures и coverage_insufficient;
- canonical serialization/checksums;
- no-network fixture compilation;
- artifact manifest, provenance и redacted logs;
- bundle validator, который подтверждает offline completeness до export;
- golden bundles для L2, L1 и failure;
- cost/latency instrumentation без location leakage.

Не делай: production audio acting, iOS runtime, 300-start live audit.

Acceptance criteria:
- fixture L2 компилируется одной командой и повторяется byte-stably при фиксированных versions/seed;
- bundle с missing fallback/checksum/schema rejected;
- отключение AI не ломает compilation;
- bundle не содержит home label/raw trace/provider secret;
- каждый scene/fact/landmark имеет provenance;
- full headless tests зелёные;
- G1_COMPILER=GO только после независимой проверки golden artifacts.

В финале перечисли compile command, artifacts, test evidence, решение G1 и следующий P10.
```

## P10 — pre-registered coverage audit на 300 стартах

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь G1_COMPILER=GO. Инспектируй repo, git status --short, rg --files, manifests/tests и provider configs. Сохраняй несвязанные изменения. Все map data идут через PoiProvider/RouteProvider adapters; отсутствующий founder code не заменяй догадками. API/policies проверяй по official docs. Не меняй thresholds после просмотра результатов. Не расширяй scope. Запусти tests/audit commands и обнови P10/G2_COVERAGE в EXECUTION_STATUS.

Задача: провести настоящий coverage audit на 300 заранее замороженных стартах: 100 крупных, 100 средних и 100 малых городов/районов, с центром, жилыми районами и окраинами, используя первую beginner training distance.

До первого live compile:
1. Убедись, что founder decision о целевой географии первой когорты записан в EXECUTION_STATUS. Если нет — не выбирай страну сам, создай sampling proposal и один конкретный decision request, пометь P10 BLOCKED.
2. Зафиксируй sampling frame, random seed, exclusion rules, dataset checksum и thresholds.
3. Не используй точные домашние адреса; только публичные/синтетически смещённые стартовые точки.

Порог-кандидат из спецификации, который нельзя менять post hoc:
- ≥80% стартов дают минимум два пригодных POI;
- ≥90% дают хотя бы один route в ±15% expected distance;
- каждый successful start имеет backup candidate;
- ≥95% выбранных names/visible attributes проходят заранее определённую manual sample verification;
- median compile <15s, p95 <30s;
- ноль известных private/foot=no segments после hard filters;
- каждая ошибка имеет typed reason.

Сохрани raw per-start records, aggregate report, strata breakdown, cost/latency, failure taxonomy и manual QA sample. Не удаляй неудачные точки и не reroll-ь выборку.

Не делай: iOS, marketing claim «работает везде», изменение scorer ради прохождения gate без новой versioned audit.

Deliverables:
- frozen start dataset + checksum/provenance;
- raw audit records;
- reproducible command/config/provider versions;
- aggregate и strata reports;
- manual QA protocol/results;
- GO/NO-GO/PIVOT recommendation.

Acceptance criteria:
- все 300 стартов присутствуют либо audit честно BLOCKED до live credentials/market decision;
- denominators и failures видны;
- повторный анализ raw records воспроизводит summary;
- никакие thresholds не изменены после данных;
- G2_COVERAGE=GO только при выполнении всех pre-registered criteria; иначе NO-GO/PIVOT_REQUIRED.

В финале сообщи denominators, thresholds, failures, cost, решение G2 и следующий допустимый P13. Не переходи к iOS при NO-GO.
```

## P13 — минимальный iOS shell после coverage GO

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Убедись, что G0_GEO_PROOF=GO, G0_DEMAND=GO и G2_COVERAGE=GO; иначе остановись и обнови status без кода. Инспектируй repo, git status --short, rg --files, Xcode projects/package manifests/tests и сохраняй несвязанные изменения. Founder map code подключай через MapSurface/PoiProvider/RouteProvider adapters; если его нет, используй test map surface и не строй замену целиком. Apple/MapLibre API проверяй по official docs. Не расширяй scope. Собери и протестируй, обнови P13.

Задача: создать iPhone-first Swift/SwiftUI shell, который открывает fixture RouteBundle, показывает pre-run summary/map abstraction и запускает fake mission session.

Нужно:
- минимальный Xcode project/target по repo conventions;
- RouteBundle decoding/validation boundary;
- dependency injection для compiler API, map surface, clock, location и audio;
- screens: start selection placeholder, compiling/loading, route preview, mission, completion/error;
- accessibility/dynamic type и RU localization foundation;
- no real background GPS/audio пока;
- fixture bundles из P09;
- unit/UI smoke tests и documented xcodebuild command.

Не делай: full navigation, offline tiles, analytics vendor, StoreKit, Apple Watch, Android, visual redesign.

Acceptance criteria:
- clean build на зафиксированной iOS/Xcode version;
- L2/L1/failure bundles отображаются корректно;
- malformed/unsupported bundle rejected до mission start;
- shell работает без founder map code через adapter;
- tests зелёные;
- P13 COMPLETE с build evidence.

В финале дай build/test commands, simulator evidence, изменённые files и следующий P14.
```

## P14 — deterministic iOS mission runtime

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md и актуальные docs, AI_FIRST_EXECUTION_PLAN и EXECUTION_STATUS. Проверь P13 COMPLETE. Инспектируй git status --short, rg --files, Xcode project/tests и сохраняй несвязанные изменения. Founder map code остаётся за adapters. Используй simulated clock/location/audio; не тащи GPS раньше следующего этапа. Не расширяй scope. Запусти unit/UI tests и обнови P14.

Задача: реализовать deterministic runtime state machine для выполнения RouteBundle.

Состояния должны покрывать start/pause/resume/finish, workout transitions, scene-window enter/exit, scene start/complete/skip/fallback, landmark visit, maneuver suppression и canonical effects exactly-once. Clock, location progress и audio являются injected inputs. Сохраняй checkpoint после событий, указанных в technical spec.

Не делай: реальный Core Location, network reroute, live LLM, analytics provider.

Deliverables:
- pure runtime engine;
- checkpoint store abstraction и local implementation;
- simulated trace runner;
- state/event schema;
- exhaustive transition/idempotency/restart tests.

Acceptance criteria:
- одна и та же trace даёт одинаковый event log;
- canonical effect нельзя применить дважды после crash/restart;
- workout timeline продолжается при scene fallback;
- maneuver suppression не теряет сцену;
- corrupted checkpoint fail-safe;
- P14 COMPLETE подтверждён tests.

В финале перечисли invariants, trace tests и следующий P15.
```

## P15 — Core Location, navigation и audio priority

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE docs, AI_FIRST_EXECUTION_PLAN и EXECUTION_STATUS. Проверь P14 COMPLETE. Инспектируй repo, git status --short, rg --files, Xcode capabilities/plists/tests; сохраняй несвязанные изменения. Founder map/navigation code используй только через adapters. Core Location, background session и AVAudioSession behavior сверяй с текущей официальной Apple документацией и фиксируй deployment target. Не расширяй scope. Тестируй recorded/simulated traces, затем обнови P15.

Задача: подключить реальный location/navigation/audio слой к deterministic runtime.

Нужно:
- Core Location adapter с fitness activity, accuracy filtering и consent flow;
- route-corridor/along-route progress, 80–150m configurable approach windows, multiple confirmations и hysteresis;
- maneuver engine, который имеет audio priority выше workout/story;
- AVAudioSession interruption/route-change handling;
- background capabilities только во время активной миссии;
- scene pause/resume около maneuvers;
- recorded GPX trace replay tests: noisy GPS, urban jump, missed turn, stationary, permission denied/reduced accuracy;
- battery/log instrumentation без raw-coordinate analytics.

Не делай: dynamic reroute, offline map download, HealthKit read, Always location без доказанной необходимости.

Acceptance criteria:
- сцена не запускается по одной шумной точке;
- critical maneuver не перекрывается story;
- permission denial имеет понятный fallback;
- lock/background simulation не ломает timeline в поддерживаемом сценарии;
- exact coordinates не попадают в product logs;
- tests/build зелёные;
- P15 COMPLETE с device/simulator limitations явно записанными.

В финале дай Apple docs/version, trace matrix, build evidence и следующий P16.
```

## P16 — offline RouteBundle, audio и map region

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN и EXECUTION_STATUS. Проверь P14–P15 COMPLETE. Инспектируй repo, git status --short, rg --files, provider terms/config и сохраняй несвязанные изменения. Map renderer/provider подключай через MapSurface/OfflineMapProvider adapter; founder code не переписывай. Проверь official tile/offline terms. tile.openstreetmap.org и иные запрещающие bulk/offline endpoints использовать нельзя. Не расширяй scope. Запусти tests и обнови P16.

Задача: сделать preflight download и гарантированное offline исполнение основной миссии.

Нужно:
- atomic RouteBundle download/store/version migration;
- checksum, size, expiry и asset completeness validation;
- audio prefetch/cache;
- OfflineMapProvider abstraction и permitted provider implementation либо fixture, если credentials отсутствуют;
- corridor-bounded map region, quota/error/cancel handling;
- explicit Ready Offline state до старта;
- network-disabled integration test;
- cleanup policy без удаления active/checkpointed bundle.

Не делай: offline routing graph, world map download, silent fallback на OSM community tiles.

Acceptance criteria:
- missing/corrupt asset блокирует start с recoverable error;
- подтверждённый bundle проходит всю fixture mission при network disabled;
- partial download не выглядит ready;
- provider terms/date записаны;
- storage cleanup безопасен;
- P16 COMPLETE только с offline test evidence; provider production readiness отдельно помечена, если есть лишь fake.

В финале перечисли offline contract, provider/legal status, tests и следующий P17.
```

## P17 — off-route, reroute и crash recovery

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные docs, AI_FIRST_EXECUTION_PLAN и EXECUTION_STATUS. Проверь P15–P16 COMPLETE. Инспектируй repo, git status --short, rg --files, runtime/routing adapters/tests; сохраняй несвязанные изменения. Founder routing code остаётся за RouteProvider. Навигация и recovery детерминированы; live LLM не блокирует их. Не расширяй scope. Запусти failure-matrix tests и обнови P17.

Задача: реализовать устойчивое off-route и восстановление.

Нужно:
- local off-route detector с accuracy-aware threshold, consecutive samples и hysteresis;
- online reconnect через RouteProvider: current→next reachable POI optional→start zone с remaining budget;
- правило skip/reassign только через заранее допустимый fallback;
- bounded retry/backoff и no-reroute storm;
- offline recovery: возврат к последней подтверждённой точке/видимый breadcrumb, без опасной прямой линии;
- app termination/relaunch restore из checkpoint;
- expired bundle/provider outage/audio interruption handling;
- deterministic system messages;
- chaos/trace tests.

Не делай: on-device routing, AI-generated emergency directions, обещание safe route.

Acceptance criteria:
- один GPS spike не вызывает reroute;
- provider outage не останавливает workout timeline;
- skipped POI не применяет canonical effect;
- crash/relaunch не повторяет scene/effect;
- offline fallback не рисует traversable straight line;
- retry count/cost bounded;
- P17 COMPLETE подтверждён failure matrix.

В финале покажи recovery state diagram/evidence и следующий P18.
```

## P18 — privacy-safe analytics и experiment instrumentation

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE docs, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P14–P17 COMPLETE. Инспектируй repo, git status --short, rg --files, privacy manifests/event schemas/tests; сохраняй несвязанные изменения. Founder map code не трогай. Apple privacy/HealthKit/location rules и analytics SDK docs проверяй официально. Если vendor не выбран, оставь AnalyticsSink adapter + local verifier. Не расширяй scope. Запусти privacy/tests и обнови P18.

Задача: внедрить минимальную аналитику, достаточную для продукта и безопасную для home/location.

События: compilation requested/outcome/tier/latency/cost bucket, mission start/pause/finish, workout transitions, scene windows/completion/fallback, landmark visit по opaque id, off-route/reroute, offline readiness, next-mission intent и consented survey link.

Правила:
- нет exact start/end/raw trace/street address/health samples;
- coarse geography только если заранее обоснована и consented;
- on-device queue, retry, deletion/export и retention;
- stable anonymous install/cohort id без fingerprinting;
- analytics disabled до consent там, где требуется;
- debug logs redacted;
- share card trims start/end;
- event schema versioned и проверяемый.

Не делай: ad attribution SDK, selling data, HealthKit ingestion, vanity metrics.

Acceptance criteria:
- automated privacy test не находит coordinates/address/raw trace в payloads/logs;
- offline queue идемпотентна;
- event counts воспроизводятся из simulated mission;
- deletion очищает queued/user-linked data;
- experiment A/B можно измерить без изменения runtime truth;
- P18 COMPLETE подтверждён tests и data inventory.

В финале перечисли collected/not-collected data, tests и следующий P19.
```

## P19 — шестисессионный русский content pack

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE docs, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P09 и P14–P18 COMPLETE. Инспектируй repo, git status --short, rg --files, story schemas/compiler/content tests и сохраняй несвязанные изменения. География приходит только через validated contracts/adapters. ИИ не является showrunner; generated prose считается draft до founder/editor approval. Не расширяй scope до 27 миссий, свободных NPC или второго языка. Запусти content/compiler tests и обнови P19.

Задача: произвести versioned русский content pack из шести beginner run/walk сессий как один законченный акт. Этот этап создаёт материал для behavioral alpha, но сам по себе ничего не доказывает об удержании.

Нужно:
- одна каноническая арка, постоянный герой и финал;
- шесть workout-aligned templates;
- 8–12 поддерживаемых geographic/spatial archetypes;
- обязательные fallbacks для sparse/L1;
- prerecorded-core/TTS-dispatcher script split;
- sensitivity/forbidden claims;
- canonical state effects и continuity checks;
- pronunciation notes для локальных имён;
- AI-assisted drafts только через P08 binder/validators;
- human editorial status per scene: draft/reviewed/approved;
- content lint, duration budget, no-look-at-screen и maneuver-window tests.

Не делай: выдавать AI draft за финальную актёрскую запись, исторические факты без approved sources, английскую локализацию.

Acceptance criteria:
- все 6 templates schema-valid и компилируются для golden dense/sparse routes;
- обязательные slots имеют fallbacks;
- continuity/state effects детерминированы;
- ни одна factual line не лишена approved fact id;
- длительность укладывается в workout windows;
- внешний cohort разрешён только для human-approved scenes/assets;
- P19 COMPLETE может означать code/content pipeline complete, но production audio readiness отмечается отдельно и честно.

В финале дай content inventory, approval state, test evidence и следующий P20.
```

## P20 — Internal TestFlight readiness

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: прочитай полностью docs/README.md, актуальные GEO_NARRATIVE docs, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P13–P19 COMPLETE и все unresolved production-readiness flags. Инспектируй repo, git status --short, rg --files, Xcode signing/config/CI/tests и сохраняй несвязанные изменения. Founder map code/provider remain behind adapters. Apple TestFlight/App Store requirements проверяй только по официальным docs. Не используй credentials и не загружай build без явного разрешения владельца. Не расширяй scope. Запусти полную release verification и обнови P20 в EXECUTION_STATUS.

Задача: подготовить безопасный internal TestFlight candidate.

Нужно:
- release configuration и secret injection без checked-in secrets;
- bundle/version/build numbers;
- privacy purpose strings, background modes justification и privacy manifest;
- crash-safe production logging redaction;
- provider quotas/kill switches;
- Xcode archive/export validation;
- unit/UI/offline/recovery test suite;
- device matrix на поддерживаемых iPhones/iOS;
- internal QA checklist: urban/suburban/small-town, network loss, permission denial, interruption, battery, bad POI, reroute;
- TestFlight notes, known issues, support/incident path;
- content/provider licenses and attribution.

Если signing/App Store Connect access отсутствует, подготовь archive/readiness artifacts и пометь upload blocked. Если пользователь явно разрешил upload и session доступна, выполни его и зафиксируй build id.

Не делай: public App Store release, paid marketing, Android, новые features.

Acceptance criteria:
- release archive валиден;
- critical tests зелёные;
- нет secrets/exact location в logs/build artifacts;
- offline/recovery проверены на real device для GO;
- privacy/provider attribution полны;
- все P0/P1 defects закрыты; иначе P20 остаётся BLOCKED;
- P20 COMPLETE только с реально доступным internal build и evidence; archive без доступного build означает BLOCKED для field reliability.

В финале дай build id либо точный blocker, QA matrix, defects и следующий P20A.
```

## P20A — runtime reliability field gate

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, все актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь P20=COMPLETE с реально доступным internal TestFlight build. Инспектируй repo, git status --short, rg --files, QA/event schemas/tests и сохраняй несвязанные изменения. Founder map/providers остаются за adapters. Apple/device/provider behavior проверяй по official docs. Не набирай внешних участников и не запускай TestFlight cohort без явного разрешения. Не расширяй scope и не смешивай reliability с retention. Запусти analysis tests и обнови P20A/G3_RUNTIME_RELIABILITY.

Задача: preregister и провести отдельный полевой gate надёжности runtime до шестисессионного behavioral alpha.

Матрица должна включать поддерживаемые iPhone/iOS, dense/residential/small-town routes, screen locked, background audio/location, network loss, permission variants, interruption, missed turn, online reroute, offline fallback, crash/relaunch и минимум одну полную beginner session на каждом обязательном сценарии.

До первого run зафиксируй sample/run count, severity taxonomy и thresholds. Минимальный кандидат gate:
- 0 safety-critical/P0 incidents;
- ≥90% полных сессий без P0/P1 runtime failure;
- ≥95% обязательных workout transitions/scenes либо корректно trigger, либо используют предусмотренный fallback;
- background lock, offline prepared mission и crash restore проходят на каждом supported OS family;
- reroute storm отсутствует, provider cost bounded;
- battery/thermal не превышают заранее выбранный operational budget.

Сохраняй anonymized run records без exact home/raw trace, defect reproduction artifacts и fix verification. Если реальные device runs отсутствуют, gate остаётся PENDING.

Не делай: оценку story retention, изменение content ради технических метрик, платный запуск.

Acceptance criteria:
- каждый denominator и device/OS виден;
- все P0/P1 воспроизводимы и закрыты до GO;
- thresholds не меняются после runs;
- реальные field/device evidence, а не только simulator;
- G3_RUNTIME_RELIABILITY=GO только при выполнении всех preregistered критериев.

В финале дай run matrix, pass/fail rates, incidents, remaining defects, решение G3 и следующий P20B либо stop.
```

## P20B — шестисессионная behavioral alpha

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь G3_RUNTIME_RELIABILITY=GO и human-approved P19 content. Инспектируй repo, git status --short, rg --files, analytics/research assets/tests и сохраняй несвязанные изменения. Карты/providers/founder code остаются adapterized. Не связывайся с людьми и не запускай cohort без явного разрешения. Не фабрикуй retention. Не расширяй scope до платежей или 27 миссий. Проверь analysis code на synthetic fixtures и обнови P20B/G4_BEHAVIORAL_RETENTION.

Задача: preregister и провести бесплатную шестисессионную behavioral alpha, отделённую и от одномиссионного component proof, и от Paid MVP.

Primary metric:
> доля заранее запланированных следующих тренировок, которые пользователь фактически начал в preregistered окне.

Обязательно отдельно показать M1→M2, достижение M3, достижение M6, participant-level repeat rate и opportunity-level next-workout starts. Completion, minutes, survey liking и намерение являются secondary. Place-specificity, recall реальных мест и «потеряло бы смысл в другом районе» остаются manipulation checks: они подтверждают работу географического механизма, но не заменяют behavior.

До cohort зафиксируй аудиторию, schedule, sample rationale, primary threshold, missing-data policy, exclusions, stop rule, incident handling и comparison target/control, если он предусмотрен. Нельзя считать ручное напоминание или открытие push как workout start. Runtime failures анализируй отдельно, потому что G3 должен был их минимизировать.

Создай/проверь cohort protocol, anonymized data export, analysis script, retention curves/table, manipulation-check report и blank/final decision report. Если реальных шести сессий нет, G4 остаётся PENDING.

Acceptance criteria для G4_BEHAVIORAL_RETENTION=GO:
- реальные участники и заранее назначенные workout opportunities;
- primary next-workout-start threshold достигнут без post-hoc изменения окна;
- M1→M2/M3/M6 denominators раскрыты;
- critical incidents и runtime-caused misses показаны отдельно;
- geo manipulation checks остаются положительными;
- нет скрытого исключения бросивших пользователей;
- evidence достаточно для коммерческого stop-loss решения.

В финале начни с primary behavioral result, затем M1→M2/M3/M6, manipulation checks, incidents, решение G4 и следующий P21 либо stop/pivot.
```

## P21 — commercial readiness и честный финальный gate

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md и все актуальные документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT и EXECUTION_STATUS. Проверь первичные evidence R03, R04, P10, P20A и P20B; названия COMPLETE/GO не принимай на веру. Инспектируй repo, git status --short, rg --files, reports, raw anonymized datasets, builds/tests и сохраняй несвязанные изменения. Founder map/providers остаются adapterized. Текущие vendor/App Store/pricing/legal правила проверяй по official sources. Не расширяй scope и не запускай продажи/публикацию без явного разрешения. Обнови P21/G5_COMMERCIAL.

Задача: провести requirement-by-requirement commercial readiness audit, а не написать оптимистичный launch memo.

Проверь:
- coverage по target strata и честную fallback rate;
- одномиссионный component A/B, его place manipulation и adverse events;
- реальные refundable deposits/preorders раннего smoke test;
- runtime reliability и шестисессионный next-scheduled-workout behavior, включая M1→M2/M3/M6;
- стоимость compilation: routing, tiles, POI data, AI, TTS, CDN/support;
- p50/p95 latency, provider quotas/SLA и cost per completed mission;
- шесть approved missions и повторяемость возле одного дома;
- privacy/data retention/deletion, licenses, attribution, terms/support;
- incident response и remote kill switch;
- season-pass/subscription hypothesis без преждевременной StoreKit complexity;
- founder stop-loss и kill/pivot criteria.

Сделай evidence matrix: requirement → authoritative source → evidence → proven/contradicted/missing. Не выводи GO из отсутствия ошибок. Missing evidence считается not ready.

Выходное решение только одно:
- GO: ограниченная платная/внешняя когорта с лимитами;
- NO-GO: остановить коммерческую разработку;
- PIVOT_REQUIRED: city packs, walking/travel, B2B engine или linear story running;
- BLOCKED: только если конкретное внешнее доказательство ещё собирается.

Не делай: придумывать retention/revenue, менять gates post hoc, публиковать app, строить следующий сезон.

Deliverables:
- commercial readiness report;
- evidence matrix;
- unit economics model с assumptions/ranges;
- risk register и launch/pivot checklist;
- обновлённый EXECUTION_STATUS с G5 decision.

Acceptance criteria для GO:
- G0_GEO_PROOF, G0_DEMAND, G2_COVERAGE, G3_RUNTIME_RELIABILITY и G4_BEHAVIORAL_RETENTION подтверждены первичными доказательствами;
- unit economics совместима с выбранной ценой и stop-loss;
- нет unresolved privacy/safety/P0 defects;
- operational owner и limits определены;
- scope первой внешней когорты ограничен и обратим;
- все missing evidence явно исключают GO.

В финале начни с решения GO/NO-GO/PIVOT/BLOCKED, затем дай пять сильнейших доказательств, пять главных рисков и единственное следующее действие. P22 разрешён только при G5_COMMERCIAL=GO.
```

## P22 — ограниченный Paid MVP

```text
Ты работаешь в репозитории Run Game. Этот чат не знает предыдущую переписку.

Обязательный старт: полностью прочитай docs/README.md, все актуальные GEO_NARRATIVE документы, AI_FIRST_EXECUTION_PLAN, DOCUMENT_AUDIT, commercial readiness report и EXECUTION_STATUS. Проверь G5_COMMERCIAL=GO по первичным evidence, не по названию статуса. Инспектируй repo, git status --short, rg --files, Xcode/StoreKit/provider configs/tests и сохраняй несвязанные изменения. Founder map/providers остаются за adapters. Apple payments, refunds, taxes/privacy и App Store rules проверяй только по официальным docs. Не используй credentials, не меняй App Store state и не набирай покупателей без явного разрешения. Не расширяй scope. Запусти tests и обнови P22/G6_PAID_MVP.

Задача: реализовать и проверить строго ограниченный Paid MVP, а не публичный масштабный launch.

Scope:
- один понятный season-pass/preorder offer, выбранный в P21;
- StoreKit 2/entitlement adapter либо approved payment path;
- restore purchase, refund/support path и graceful provider outage;
- paywall не скрывает geo coverage/fallback limitations;
- remote cohort/traffic/spend caps и kill switch;
- real paid cohort только в заранее ограниченной test geography;
- измерение qualified view→purchase, refund, six-session next-workout starts, completion, support burden, route/POI failures, COGS и contribution margin;
- raw financial/behavioral evidence без exact location.

До продаж preregister cohort size, price, duration, refund rule, success/kill thresholds и maximum loss. Если App Store/participants/authorization отсутствуют, подготовь implementation/readiness, но оставь G6 PENDING.

Не делай: public worldwide release, paid acquisition scaling, second season, Android, subscription complexity без решения P21.

Acceptance criteria для G6_PAID_MVP=GO:
- реальные покупки, не coupon/internal transactions;
- restore/refund/support протестированы;
- actual conversion/refund/COGS и next-workout behavior раскрыты;
- stop-loss и cohort caps соблюдены;
- нет unresolved P0/privacy/payment defects;
- экономика не противоречит P21 assumptions либо решение честно NO-GO/PIVOT.

В финале дай paid funnel, refunds, behavioral retention, COGS/support, incidents, решение G6 и не начинай масштабирование.
```

## Что считать успехом всего плана

План завершён не тогда, когда написан iPhone-код, а когда доказана вся цепочка:

```text
start + beginner workout
→ реальные и пригодные geographic anchors
→ объяснимый круговой route
→ детерминированное назначение авторских сцен
→ проверенная AI-локализация
→ offline RouteBundle
→ дешёвый one-mission geo component proof
→ реальные refundable deposits/preorders
→ production compiler и 300-start coverage
→ устойчивый iPhone runtime и отдельный reliability gate
→ фактический старт следующей запланированной тренировки в шести сессиях
→ commercial readiness
→ ограниченный Paid MVP с приемлемой стоимостью и поддержкой
```

Если цепочка ломается на coverage или field value, остановка либо pivot являются правильным результатом AI-first разработки, а не неудачей исполнения.
