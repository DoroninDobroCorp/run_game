# R02B Field Verification & Evidence Memo (Valparaíso Route Draft)

**Дата обновления:** 7 августа 2026 года

**Текущий статус:** `native_founder_build_simulator_verified, physical walk-through pending`

**Исследовательский режим:** `SOLO_FOUNDER_NARRATIVE_RUN` (самостоятельный забег, телефон заблокирован в кармане)

**Активная локация:** г. Вальпараисо, Чили (предварительный центральный контур)

**Предыдущая локация:** фикстура Santiago / Metro Cumming больше не активна; её локальные файлы не переносились

**Зафиксированная ветка M1:** `atlas_disclosure = concealed`
**Выбранный канон:** «Нулевой слой»

---

## 1. Предварительные OSM-кандидаты в Вальпараисо

Для активной фикстуры выбраны четыре публичных ориентира в центральной части города:

- **Старт и финиш:** Plaza de la Victoria ([OSM way 313292626](https://www.openstreetmap.org/way/313292626))
- **`threshold` (Slot 1):** Arco Británico ([OSM way 479821102](https://www.openstreetmap.org/way/479821102))
- **`witness` (Slot 2):** Parque Italia ([OSM way 313291642](https://www.openstreetmap.org/way/313291642))
- **`triangulation` (Slot 3):** Plaza O'Higgins ([OSM way 313290496](https://www.openstreetmap.org/way/313290496))

Локальные данные находятся в `research/r02/local/valparaiso_central/` и не попадают в Git. Проверка идентичности выполняется общей командой:

```bash
python3 tools/r02_verify_geo.py
```

### Подтверждённость и ограничения

- OpenStreetMap подтверждает только существование, тип, ID и имя каждого объекта.
- Порядок улиц между объектами пока не является утверждённым маршрутом.
- Тротуары, переходы, трафик, ремонт, освещение, доступность, покрытие и лестницы не проверены.
- Дистанция, набор высоты, длины отрезков и фактические времена прибытия к POI остаются `null`.
- Все `human_approved`, `human_route_approved` и `workout_approved` остаются `false`.
- Вальпараисский рельеф нельзя оценивать по расстоянию по прямой; решение принимается только после дневного пешего обхода.

---

## 2. Master Audio

Сценарий и 30-минутная timing-сетка не зависят от города. Condition A подставляет в реплики локальные названия «Арко Британико», «Парк Италия» и «Пласа О’Хиггинс».

```bash
python3 tools/r02_build_master.py
python3 tools/r02_verify_field.py
```

Сборка и проверка выполнены 7 августа 2026 года:

- `m01_solo_founder_30min.aiff` — `1800.00s`, 151 MB, SHA-256 `7adbbbf05cb71fab1feefa055a8310b1386c2664d16f93b8bcd533987ca94e0e`
- `m01_solo_founder_30min.m4a` — `1800.00s`, 4.9 MB, SHA-256 `17aece84537542363fc4950f82ff73355b2c8db70497e3b6121b7ecf3239eb22`
- `m01_solo_founder_30min.manifest.json` — 27 NAV-сигналов, 10 narrative cues, финальный NAV в `1792.0s`

Все файлы находятся в `research/r02/local/valparaiso_central/audio/` и игнорируются Git. Прежние Santiago-хэши не считаются evidence активной фикстуры.

### Тайминг-сетка

- `0s`: NAV старт тренировки + `c001`
- `240s`: `c002`
- `300–360s`: бег 1; `365s`: `c003` (`threshold`)
- `600–660s`: бег 3; `665s`: `c004` (`witness`)
- `815s`: `c005`; `965s`: `c006a`
- `1050–1110s`: бег 6; `1115s`: `c007` (`triangulation`)
- `1415s`: `c008` (замыкание контура)
- `1500s`: заминка; `1510s`: `c009`; `1650s`: `c010`
- `1792s`: финальный NAV-сигнал до окончания в `1800.0s`

---

## 3. Следующие шаги

Founder test теперь выполняется через локальный SwiftUI build `ios/RunGameFounder/RunGameFounder.xcodeproj`. Приложение включает route preview, отдельный walk-through с GPX, master-аудио, lock-screen controls, safety gate и дебриф. Подробная инструкция: `docs/R02_FOUNDER_IPHONE_TEST_GUIDE.md`.

1. **Установка на физический iPhone.** Выбрать Personal Team, собрать и запустить founder build; подтвердить реальный background audio/location behavior.
2. **Дневной walk-through без аудио.** Открыть карту на Plaza de la Victoria, проверить фактический безопасный контур через три POI и записать GPX. Не ускоряться ради совпадения с cue.
3. **Замеры и корректировка.** Заполнить дистанцию, набор высоты, длины отрезков, переходы, покрытие и времена прибытия в `current.binding.json`. При необходимости заменить любой POI.
4. **Human approval.** Только после обхода установить маршрутные и workout-флаги в `true`; OSM-проверка сама по себе этого не разрешает.
5. **Домашняя проверка.** Полностью прослушать master с заблокированным экраном; approval привязан к SHA-256 и автоматически сбрасывается после смены аудио.
6. **Solo founder run.** Выполнить M1-A, сразу экспортировать GPX/JSON-дебриф, затем добавить 24-часовой recall.

R02 не отмечается `COMPLETE` до фактической пробежки и заполнения evidence form.
