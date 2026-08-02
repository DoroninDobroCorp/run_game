# R02B Field Verification & Evidence Memo (Santiago Master Audio & Route Draft)

**Дата составления:** 1 августа 2026 года
**Текущий статус:** `generated_unverified, route walk-through pending`
**Исследовательский режим:** `SOLO_FOUNDER_NARRATIVE_RUN` (самостоятельный забег, телефон заблокирован в кармане)
**Активная локация:** г. Сантьяго, Чили (стартовая зона возле Metro Cumming, Баррио Юнгай / Брасил)
**Архивный fixture:** г. Ла-Пас, Боливия сохранён как замороженный исторический фикстура
**Зафиксированная ветка M1:** `atlas_disclosure = concealed`
**Выбранный канон:** «Нулевой слой»
**Тестовое покрытие:** 19 standard unit tests + live OSM geo verifier (`tools/r02_verify_santiago_geo.py`) + field verification (`tools/r02_verify_field.py`)

---

## 1. Спецификация проверенных OSM кандидатов (г. Сантьяго, Чили)

Маршрут имеет предварительный статус `provisional_unverified`. Проверенные через live OpenStreetMap API кандидаты вокруг Metro Cumming:

- **Старт и Финиш**: Cumming ([OSM node 253281419](https://www.openstreetmap.org/node/253281419))
- **`threshold` (Slot 1)**: Centro Comunitario Palacio Álamos ([OSM way 592372641](https://www.openstreetmap.org/way/592372641)) — здание общественного центра на ул. Santo Domingo 2398
- **`witness` (Slot 2)**: Basílica del Salvador ([OSM way 180191510](https://www.openstreetmap.org/way/180191510)) — неоготическое культовое сооружение на ул. Huérfanos
- **`triangulation` (Slot 3)**: Plaza Brasil ([OSM way 23389924](https://www.openstreetmap.org/way/23389924)) — открытый городской парк

### Подтверждённость и допущения
- **OSM identity verified**: Подлинность объектов, типы и OSM IDs подтверждены через живой запрос к OSM API.
- **NOT YET VERIFIED (Provisional Assumptions)**: Пешеходная безопасность, фактическая ширина тротуаров, точная пешеходная длина маршрута, времена прибытия к POI и тип покрытия остаются непроверенными гипотезами до выполнения дневного обхода основателем.
- **Параметры расстояния и высоты**: `measured_loop_length_meters`, `measured_elevation_gain_meters`, `poi_leg_distances_meters` и `expected_poi_arrival_cue_sec` в `current.binding.json` сохранены в значении **`null`**.
- **Статус аппрува**: все `human_approved`, `human_route_approved` и `workout_approved` **остаются `false`** до пешего прохождения основателем.

Файл snapshot зафиксирован: `research/r02/local/santiago_cumming/osm_snapshot.json`.

---

## 2. Спецификация 30-минутного Master Audio (`1800.0s`)

Скомпилирован один единый непрерывный master-файл с чистой озвучкой реплик (без проговаривания дикторских меток `NAV:`, `ЛЕА:`, `АТЛАС:` и сценических указаний в скобках `[...]`), цифровой тишиной между cues и 27 голосовыми NAV-сигналами.

- **Master Audio Files**:
  - `research/r02/local/santiago_cumming/audio/m01_solo_founder_30min.aiff` (151 MB, длительность: **1800.00s**, SHA-256: `051b613003e7c382ceef786def51503944b4d6c6a1000345e51b86157345886d`)
  - `research/r02/local/santiago_cumming/audio/m01_solo_founder_30min.m4a` (4.8 MB, длительность: **1800.00s**, SHA-256: `732c1db66000954f317f5f696a1fc7743ebed835c5136963821cb46b205041c1`)
- **Manifest File**: `research/r02/local/santiago_cumming/audio/m01_solo_founder_30min.manifest.json`.

### Тайминг-сетка Master Audio:
- `0s`: NAV Старт тренировки + `c001` (8s)
- `240s`: `c002`
- `270s`: NAV Предупреждение о беге 1
- `300s`: NAV Бег 1 (60s)
- `360s`: NAV Переход на ходьбу (90s)
- `365s`: `c003` (Centro Comunitario Palacio Álamos)
- `660s`: NAV Переход на ходьбу 3
- `665s`: `c004` (Basílica del Salvador)
- `810s`: NAV Переход на ходьбу 4
- `815s`: `c005` (фиксация concealed)
- `960s`: NAV Переход на ходьбу 5
- `965s`: `c006a` (реакция concealed)
- `1110s`: NAV Переход на ходьбу 6
- `1115s`: `c007` (Plaza Brasil)
- `1410s`: NAV Переход на ходьбу 8
- `1415s`: `c008` (замыкание контура, восстановлена сильная реплика: «Я появилась не там, где меня забыли, а там, где ты прошёл»)
- `1500s`: NAV Заминка (5 мин)
- `1510s`: `c009` (фрагменты)
- `1650s`: `c010` (финал Леа, без фразы завершения NAV)
- `1792s`: NAV Финальное завершение тренировки (завершается до 1800.0s)

---

## 3. Последовательность следующих шагов

1. **A. Дневной пеший проход маршрута возле Metro Cumming (Walk-Through):**
   - Основатель днём выходит к публичной стартовой точке возле Metro Cumming с открытой картой (без аудиотрека), проходит контур пешком, замеряет время прибытия к Palacio Álamos, Basílica del Salvador, Plaza Brasil, проверяет тротуары, переходы и освещение.
2. **B. Корректировка таймингов по результатам замера / GPX:**
   - Рассчитываются пешеходная длина, набор высоты и фактические времена прибытия в `current.binding.json`.
   - При необходимости изменяются параметры точек или выбираются более близкие POI.
   - Устанавливаются флаги `human_route_approved = true`, `workout_approved = true`, `human_approved = true`.
3. **C. Финальная пересборка Master Audio:**
   - Перезапуск `python3 tools/r02_build_master.py --beats research/r02/mission_01_beats.v0.1.json --binding research/r02/local/santiago_cumming/current.binding.json --output-dir research/r02/local/santiago_cumming/audio`.
4. **D. Домашняя проверка Master Audio:**
   - Проверка воспроизведения `m01_solo_founder_30min.m4a` дома с заблокированным экраном телефона через `python3 tools/r02_verify_field.py --audio-dir research/r02/local/santiago_cumming/audio`.
5. **E. Физическая пробежка Основателя (Solo Founder Run):**
   - Пробежка M1-A ➔ дебрифинг в `founder_m01_run.json` ➔ 24-часовой опрос.
