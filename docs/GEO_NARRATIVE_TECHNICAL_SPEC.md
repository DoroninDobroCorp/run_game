# Run Game — техническая спецификация geo-narrative MVP

**Версия:** 0.2

**Дата:** 15 июля 2026 года

**Связанный продуктовый документ:** [GEO_NARRATIVE_PRODUCT_STRATEGY.md](./GEO_NARRATIVE_PRODUCT_STRATEGY.md)

## Технический вердикт

Целевое обещание реалистично в следующей форме:

> Пользователь задаёт старт; система заранее строит приблизительно подходящий круг, выбирает 2–3 реальных географических якоря и привязывает к ним разрешённые авторские сцены.

Нереалистично для первого MVP гарантировать одновременно:

- одинаково богатый опыт из любой точки мира;
- безошибочную оценку фактической проходимости и состояния улиц;
- точное возвращение домой ровно в заданную секунду;
- полностью офлайн-перестраиваемый маршрут;
- достоверный исторический рассказ о любом POI без проверяемых источников;
- безопасный маршрут только на основании OSM.

MVP строится как **L2 POI Quest Loop**: 2–3 локальных якоря, несколько кандидатов маршрута, авторские сцены, короткие AI-связки и заранее загруженный runtime bundle.

Здесь `L2` обозначает техническую способность geo-compiler, а не готовый коммерческий MVP. Один L2-эпизод проверяет только механику места; удержание проверяет шестисессионная alpha, оплату — отдельный Paid MVP.

## Архитектура

```text
iPhone / prototype client
  │
  │ start area + workout id + persistent preferences
  ▼
Mission Compiler API
  ├── Training Planner
  ├── Landmark Index
  ├── Route Provider Adapter
  ├── Candidate Generator
  ├── Route + POI Scorer
  ├── Story Template Registry
  ├── Scene Assignment Solver
  ├── AI Story Binder
  ├── Content Validators
  └── Audio Assembler
  │
  │ versioned RouteBundle
  ▼
iPhone Runtime
  ├── offline map slice
  ├── route corridor + maneuvers
  ├── run/walk timeline
  ├── scene windows
  ├── audio assets
  ├── fallback transitions
  └── event/checkpoint log
```

Существующий картографический код основателя позднее подключается через интерфейсы `PoiProvider` и/или `RouteProvider`. План не предполагает его внутреннюю архитектуру и не требует переписывания до отдельного аудита.

## Два пути реализации

### Prototype path до доказательства ценности

- 20–30 стартовых точек в одном доступном для полевого QA рынке;
- `FixturePoiProvider` или `OverpassResearchProvider`;
- hosted route API;
- один авторский template;
- ручная проверка каждого выбранного маршрута и POI;
- заранее собранные GPX/GeoJSON, аудио и cue sheet;
- простой trigger player либо Wizard-of-Oz;
- без production PostGIS, offline tiles, map matching cluster и универсального reroute.

Цель — проверить, даёт ли локальная сцена пользовательскую ценность, прежде чем строить масштабируемую инфраструктуру.

### Production path после положительного field signal

- региональный OSM/PostGIS index;
- versioned providers и schemas;
- автоматический scorer и validators;
- RouteBundle;
- iPhone locked-screen runtime;
- offline mission assets;
- детерминированный online reroute;
- аудит 300 стартовых точек до обещания широкого покрытия.

## Граница компонентов

### Training Planner

Вход:

- `workout_template_id`;
- отдельный оценённый темп ходьбы;
- отдельный оценённый темп лёгкого бега;
- допустимый диапазон продолжительности утверждённой тренировки;
- ограничения по набору высоты.

Выход:

- timeline разминки, run/walk-блоков и заминки;
- ожидаемая дистанция и диапазон;
- окна, в которых допустимы длинные сцены;
- окна, где разрешены только короткие команды;
- правила повторения нагрузки.

Для первой когорты `workout_template_id` выбирается не пользователем и не LLM. Он указывает на утверждённую тренировку текущего дня из beginner run/walk-прогрессии по образцу NHS Couch to 5K. Точные интервалы, повторы недели и stop rules проходят отдельный review тренера/физиотерапевта. Пользователь выбирает старт и время выхода; Mission Compiler подстраивает маршрут и сцены под неизменяемый fitness timeline.

Оценка дистанции:

```text
expected_distance =
  Σ(walk_duration × expected_walk_speed)
  + Σ(run_duration × expected_easy_run_speed)
```

На первых тренировках контракт формулируется как диапазон времени, например 25–35 минут. После нескольких сессий используются персональные темпы.

ИИ не меняет fitness timeline.

### Landmark Index

Production-источник — серверный региональный индекс, а не публичный Overpass на каждый пользовательский запрос.

Рекомендуемая модель данных:

```text
Landmark
  id
  source_type
  source_id
  name
  geometry
  osm_tags
  archetypes[]
  access_flags[]
  sensitivity_flags[]
  visible_attributes[]
  source_links[]
  approved_facts[]
  data_confidence
  last_verified_at
```

Источники:

- региональные OSM extracts;
- `wikidata`/`wikipedia` tags из OSM;
- Wikipedia GeoSearch через серверный кэш;
- собственные пользовательские отчёты как отдельный overlay;
- вручную проверенные city packs в будущем.

Публичные Overpass-инстансы не имеют SLA и не должны быть runtime-backend коммерческого приложения. [Overpass API commons](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)

Публичный Wikidata SPARQL также не является надёжной runtime-зависимостью; сложные запросы ограничиваются и тайм-аутятся. [Wikidata query limits](https://www.wikidata.org/wiki/Wikidata%3ASPARQL_query_service/query_limits)

### PoiProvider

```text
interface PoiProvider {
  search(GeoEnvelope, PoiQuery) -> [Landmark]
  getById(LandmarkId) -> Landmark?
  reportIssue(LandmarkId, Issue) -> Receipt
}
```

Реализации:

- `FixturePoiProvider` для тестов;
- `OverpassResearchProvider` только для прототипа и аудита;
- `PostgisPoiProvider` для production;
- адаптер существующего кода основателя после его передачи.

### RouteProvider

```text
interface RouteProvider {
  roundTrips(Start, DistanceBudget, Seed, Heading?, RouteProfile) -> [Route]
  viaPoints(Start, [Waypoint], RouteProfile) -> Route
  reconnect(Current, NextTarget?, Start, RemainingBudget, RouteProfile) -> Route
  mapMatch([LocationSample]) -> MatchedTrace
}
```

Рекомендуемый MVP-провайдер — hosted GraphHopper:

- `round_trip` генерирует приблизительные круги;
- seed и начальное направление дают варианты;
- есть пешеходные профили и custom models;
- не требуется сразу разворачивать собственный routing cluster.

Расстояние кругового маршрута остаётся приблизительным, поэтому нужен набор кандидатов и собственный scorer. [GraphHopper routing API](https://github.com/graphhopper/graphhopper/blob/master/docs/web/api-doc.md#flexible)

Поздний кандидат — Valhalla: гибкие pedestrian costings, isochrones, map matching и self-hosting, но генератор приятных кругов нужно строить самостоятельно. [Valhalla API](https://valhalla.github.io/valhalla/api/)

OSRM полезен для A→B, таблиц и map matching. Его `Trip` упорядочивает уже выбранные точки, но не решает задачу выбора POI и дистанции. [OSRM API](https://project-osrm.org/docs/v26.4.0/http)

### Candidate Generator

Алгоритм MVP:

1. Получить достижимую область из ожидаемой дистанции.
2. Найти до 20–30 пригодных landmark-кандидатов.
3. Сгенерировать минимум шесть кругов с разными seed/heading.
4. Построить route corridor для каждого круга.
5. Найти landmarks внутри corridor и проверить подход по пешеходному графу.
6. При необходимости построить варианты через один или два выбранных POI.
7. Отдать кандидатов scorer.

Если L2 не получается:

1. попытаться построить L1 через один уверенный POI;
2. предложить ближайший другой старт или route-neutral fallback;
3. вернуть честный `coverage_insufficient`, а не вымышленные объекты.

### Hard filters POI

- достижим с публичного пешеходного графа;
- не `private`, не `foot=no`;
- не требует входа в здание;
- не частный дом;
- не военная или критическая инфраструктура;
- не медицинское учреждение;
- школа не используется как сюжетная цель;
- сцена не требует перебегать дорогу или останавливаться на проезжей части;
- не зависит от часов работы;
- тип объекта достаточно стабилен.

Отдельной контентной политики требуют:

- религиозные объекты;
- кладбища;
- мемориалы и места трагедий;
- объекты, связанные с уязвимыми группами;
- действующие предприятия и бренды.

### Route + POI Scorer

```text
score =
  + landmark_quality
  + archetype_diversity
  + narrative_role_fit
  + pedestrian_way_bonus
  + park_or_waterfront_bonus
  + novelty_bonus
  + fallback_route_bonus
  - target_distance_error
  - repeated_edge_penalty
  - major_road_crossing_penalty
  - elevation_penalty
  - unknown_surface_penalty
  - unknown_access_penalty
  - maneuver_density_penalty
  - POI_detour_penalty
```

Каждая составляющая логируется. Нельзя иметь единственный непрозрачный `AI route score`.

### Story Template Registry

Авторский шаблон содержит канон и географические требования:

```json
{
  "template_id": "signal_drop_v1",
  "duration_range_sec": [1500, 2100],
  "slots": [
    {
      "slot_id": "threshold",
      "allowed_archetypes": ["bridge", "gate", "district_boundary"],
      "preferred_workout_blocks": ["warmup_end"],
      "required_fields": ["name"],
      "fallback_scene_id": "generic_threshold"
    },
    {
      "slot_id": "observation",
      "allowed_archetypes": ["viewpoint", "open_square", "waterfront"],
      "preferred_workout_blocks": ["walk_recovery"],
      "required_fields": [],
      "fallback_scene_id": "generic_observation"
    }
  ]
}
```

Шаблон отдельно задаёт:

- опорные заранее написанные сцены;
- допустимые географические архетипы;
- переменные локализации;
- запрещённые темы;
- максимальную длительность;
- fallback;
- требуемый голос;
- канонические state changes.

### Scene Assignment Solver

Это ограниченная задача соответствия, а не чат с моделью.

Вход:

- route candidate;
- упорядоченные landmarks;
- along-route distances;
- workout timeline;
- story template slots.

Выход:

- назначение `slot → landmark/window`;
- оценка качества;
- объяснение каждого назначения;
- список незаполненных слотов;
- fallback plan.

Сначала используется детерминированный solver/поиск. LLM может предлагать semantic affinity, но не отменять hard constraints.

### AI Story Binder

Модель получает только структурированные и проверенные данные:

```json
{
  "slot_id": "threshold",
  "canonical_scene_intent": "hero instructs player to cross into monitored territory",
  "landmark": {
    "name": "Старый железнодорожный мост",
    "archetype": "bridge",
    "visible_attributes": ["river_crossing", "metal_structure"],
    "approved_facts": [],
    "confidence": 0.91
  },
  "max_spoken_seconds": 45,
  "allowed_placeholders": ["landmark.name"],
  "forbidden_claims": ["construction_date", "historical_event"]
}
```

Выход обязан соответствовать JSON Schema:

```text
LocalizedScene
  scene_id
  spoken_text
  referenced_landmark_ids[]
  referenced_fact_ids[]
  estimated_duration_sec
  fallback_scene_id
  validation_notes[]
```

Нужны проверки:

- referenced landmark существует;
- каждый фактический тезис имеет `approved_fact_id`;
- имя не изменено моделью;
- нет инструкций, противоречащих maneuvers;
- длина укладывается в окно;
- нет упоминания точного домашнего адреса;
- сцена не требует посмотреть на экран;
- fallback существует.

### Audio Assembler

Рекомендуемый художественный контракт:

- основной герой и драматические опорные сцены — заранее записанный голос;
- отдельный in-world «диспетчер» — TTS для названий, навигации и локальных связок;
- навигационные команды имеют отдельный звуковой приоритет;
- все AI/TTS-ассеты создаются до старта;
- каждый asset имеет checksum и fallback.

Так разница качества голоса объясняется миром и не разрушает главного персонажа.

## RouteBundle

```text
RouteBundle
  schema_version
  bundle_id
  generated_at
  expires_at
  route
    polyline
    corridor
    maneuvers[]
    expected_distance
    expected_duration_range
    fallback_return_path?
  workout
    timeline[]
  landmarks[]
  scenes[]
  scene_windows[]
  audio_assets[]
  offline_map_region?
  content_policy_version
  story_state_input
  story_state_effects
  checksums
```

После загрузки основная миссия проходит без сети.

## iPhone runtime

Рекомендуемые технологии:

- Swift/SwiftUI;
- Core Location;
- AVFoundation/AVAudioSession;
- MapLibre Native либо адаптер существующего картографического кода;
- локальное event/checkpoint storage;
- HealthKit позже для сохранения workout route;
- background location/audio только во время активной миссии.

MapLibre является renderer, но не поставляет tiles, POI или маршрутизацию. [MapLibre Native iOS](https://maplibre.org/maplibre-native/ios/latest/documentation/maplibre/)

Нельзя использовать `tile.openstreetmap.org` для bulk/offline download. Нужен разрешающий это provider или собственные tiles. [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)

### Location triggering

Сцена не запускается по одной GPS-точке.

Условие использует:

- route corridor;
- along-route progress;
- geofence подхода 80–150 м, калибруемый по типу места;
- GPS accuracy;
- несколько последовательных подтверждений;
- hysteresis;
- состояние манёвра;
- временное окно workout block.

Apple допускает background Core Location для реального fitness/navigation use case. [Core Location background updates](https://developer.apple.com/documentation/corelocation/handling-location-updates-in-the-background)

### Audio priority

```text
critical maneuver
  > workout transition
  > safety/system message
  > story scene
  > ambience/music
```

Длинная сцена приостанавливается перед сложным манёвром и продолжается после него.

### Checkpointing

Сохранять после:

- старта;
- каждого workout transition;
- входа в scene window;
- начала и завершения сцены;
- фиксации landmark visit;
- off-route;
- reroute;
- завершения.

Повторный запуск восстанавливает workout timeline, story state и использованные сцены без повторного канонического эффекта.

### Runtime reliability gate

До шестисессионного retention-теста вертикальный срез обязан пройти отдельный reliability pilot. Иначе эксперимент измерит качество GPS-плеера, а не ценность geo-story.

Логировать и заранее установить допустимые пороги для:

- crash-free session rate при заблокированном экране;
- непрерывности аудио при блокировке, входящем звонке и кратком переключении приложения;
- доли пропущенных или опоздавших critical maneuver/workout cues;
- расхода батареи на типовую 30-минутную сессию;
- времени и успешности восстановления после принудительного завершения процесса;
- ложных off-route и успешных reroute/fallback;
- расхождения реального и сохранённого прогресса;
- completion без обращения к тестовой команде.

Пороговые значения фиксируются после внутреннего device matrix test и до внешней alpha.

## Отклонение и перестроение

Off-route определяется локально только после нескольких плохих location samples и с учётом accuracy.

Онлайн-сценарий:

```text
current location
→ next reachable landmark, если ещё разумно
→ start zone
```

Если landmark больше не достижим в оставшемся бюджете:

- связанная сцена пропускается;
- проигрывается заранее подготовленный fallback;
- workout timeline продолжается;
- возврат строится детерминированно;
- live LLM не блокирует навигацию.

Офлайн-сценарий MVP:

- показать/озвучить возврат к последней подтверждённой точке маршрута;
- не рисовать прямую линию через неизвестную территорию;
- продолжить тренировочные интервалы;
- перейти на generic story fallback;
- сохранить сессию.

Полноценное offline rerouting требует регионального routing graph на устройстве и не входит в MVP.

## Приватность стартовой точки

Дом — чувствительный тип location data.

Правила:

- пользователь может задать ближайшую публичную стартовую точку вместо дома;
- сохранённый «дом» хранится только локально;
- точный старт не попадает в обычную продуктовую аналитику;
- Mission Compiler получает координату через наш backend, а не напрямую из клиента к нескольким providers;
- LLM получает только название/архетип landmarks и относительную структуру маршрута;
- share-карточка обрезает начало и конец маршрута;
- raw trace не хранится на сервере по умолчанию;
- retention policy фиксируется до внешнего теста.

Apple требует ясного назначения location/background collection и соответствующих consent/disclosure. [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

## Уровни продукта

### L1 — один якорь

- один уверенный POI;
- out-and-back или lollipop route;
- одна локальная сцена;
- остальной сюжет зависит от прогресса.

Использование: технический прототип и fallback. Недостаточно сильное основное позиционирование.

### L2 — POI Quest Loop

- автоматический круг;
- 2–3 POI;
- несколько route candidates;
- scorer;
- авторские сцены по архетипам;
- AI-связки;
- offline RouteBundle;
- онлайн-перестроение возврата;
- fallback до L1.

Использование: целевая техническая способность behavioral alpha и будущего Paid MVP.

### L3 — city packs

- вручную проверенные POI и подходы;
- конкретные факты и история мест;
- уникальные ветви маршрута;
- city-specific production;
- локальные партнёры/авторы.

Использование: премиальный контент, туризм или B2B после доказательства L2.

## Coverage audit

Аудит проходит в два этапа.

До первого field proof — 20–30 разнородных стартов в выбранном тестовом рынке. Этого достаточно, чтобы отладить hard filters и выбрать реальные маршруты для Wizard-of-Oz, но недостаточно для маркетингового обещания покрытия.

Только после положительного geo-story field signal и до публичного обещания «работает везде» взять 300 стартовых точек:

- 100 крупных городов/районов;
- 100 средних;
- 100 малых;
- внутри каждой группы центр, жилой район и окраина;
- использовать дистанционный бюджет первой beginner-тренировки.

Для каждой точки сохранить:

- количество raw POI;
- количество после hard filters;
- архетипы;
- количество route candidates;
- лучший score;
- target-distance error;
- road crossing/elevation/access penalties;
- L2/L1/failure;
- время компиляции;
- source confidence.

Рабочие ворота L2:

- ≥80% стартов дают минимум два пригодных POI;
- ≥90% дают хотя бы один маршрут в ±15% ожидаемой дистанции;
- каждый успешный старт имеет запасной вариант;
- ≥95% выбранных имён и видимых признаков проходят ручную выборочную проверку;
- median RouteBundle <15 секунд, p95 <30 секунд;
- mission bundle после загрузки исполняется без сети;
- ни один известный `private`/`foot=no` сегмент не проходит hard filters;
- причина каждого отказа машинно читаема.

Это внутренние пороги решения, а не отраслевые стандарты. Они должны быть pre-registered до полного аудита.

## Полевые эксперименты

### Component test географической ценности

Сравнить для одной и той же тренировочной структуры:

- A: story + маршрут + локальные сцены;
- B: тот же production value и маршрут, но история не использует реальные места.

Поведенческий primary:

> доля пользователей, начавших следующую запланированную тренировку/миссию в заранее определённое допустимое окно.

В одноэпизодном Wizard-of-Oz этот показатель ещё нельзя надёжно оценить, поэтому он остаётся directionally useful. Обязательный retention test проводится на шестисессионной alpha.

Manipulation checks и secondary:

- оценка того, потерял бы опыт смысл в другом районе;
- recall двух локальных мест;
- естественность маршрута;
- раздражение навигацией;
- желание пройти другую миссию возле дома;
- желание исследовать новый район;
- ошибки POI;
- off-route recovery;
- M1→M2/M3 после первого «вау».

Если локальная версия не создаёт practically meaningful lift против control по заранее выбранным показателям, geo-narrative component thesis не доказан.

### Full-product behavioral alpha

Шесть тренировок используют вручную написанную мини-арку, постоянного героя, 2–3 поворота/cliffhanger и одинаковую утверждённую beginner-программу.

Primary:

- фактический старт M2, M3 и M6 в допустимое окно;
- завершение сессии без ручной помощи.

Secondary:

- route accept/reroll/abort;
- crash-free locked-screen session;
- audio continuity и critical-cue miss rate;
- восстановление после off-route;
- повторяемость POI к M6;
- желание продолжить историю.

### Commercial gate

До производства длинного сезона нужен наблюдаемый денежный сигнал: возвратный депозит, предзаказ либо реальная покупка продолжения. Опрос «сколько бы вы заплатили» не считается оплатой.

Также измеряются переменная стоимость RouteBundle, TTS/AI/routing, support incidents и ручной QA на завершённую миссию.

## Стоимость MVP-инфраструктуры

GraphHopper считает round-trip запрос дороже обычного route. При нескольких кандидатах одна компиляция расходует несколько запросов; текущие тарифы нужно перепроверять перед запуском. На июль 2026 hosted-планы находятся в диапазоне десятков/сотен евро в месяц. [GraphHopper pricing](https://www.graphhopper.com/pricing/)

Основные расходы, вероятно:

- tiles/offline map provider;
- route requests;
- региональный OSM/PostGIS pipeline;
- AI localization;
- TTS и CDN;
- полевой QA;
- авторский и аудиоконтент;
- support по плохим маршрутам и POI.

LLM bill не является главным коммерческим риском. Главные риски — coverage, качество маршрута, повторяемость и retention.

## Технические kill criteria

- coverage audit не достигает L2 в значительной части целевого рынка;
- приятный маршрут нельзя отличить от математически валидного без ручной работы на каждый старт;
- POI слишком часто отсутствуют или недоступны;
- локальные сцены систематически ощущаются как подстановка названия;
- p95 компиляции неприемлем для pre-run опыта;
- route/navigation failures разрушают тренировку;
- стоимость каждой mission compilation несовместима с ценой;
- существующий картографический код невозможно безопасно адаптировать и замена выходит за stop-loss;
- контрольный эксперимент не показывает ценность географической локализации.
