# R02B Field Verification & Evidence Memo (Valparaíso Route Draft)

**Дата обновления:** 10 августа 2026 года

**Текущий статус:** `offline preflight READY_FOR_DEVICE_SMOKE; physical device, audio, walk-through and run evidence pending`

**Исследовательский режим:** `SOLO_FOUNDER_NARRATIVE_RUN` — самостоятельная
личная проверка с заблокированным телефоном на уже знакомом маршруте.

**Активная локация:** г. Вальпараисо, Чили, предварительный центральный контур.

**Неактивная локация:** Santiago / Metro Cumming относится к предыдущей
фикстуре. Её локальную папку можно хранить как архив, но она не выбирается
автоматически и не подменяет Valparaíso.

**Зафиксированная ветка M1:** `atlas_disclosure = concealed`

**Выбранный канон:** «Нулевой слой»

---

## 1. Что существует и чего ещё нет

В репозитории есть founder-only SwiftUI research shell, offline master,
подготовка/проверка bundle, Apple Maps preview, локальный GPS→GPX, recovery
checkpoint, route/audio gates и unique-run JSON-дебриф. Это не production
iPhone product и не прохождение следующих инвестиционных ворот.

Offline preflight может подтвердить только согласованность binding, snapshot,
audio/manifest SHA, route/timeline fingerprints и подготовленных iOS resources.
Его максимальный статус — `READY_FOR_DEVICE_SMOKE`; он не выдаёт route safety,
workout, participant или M1-A approval.

На дату memo **не существуют** следующие human evidence:

- установка и smoke на физическом iPhone;
- подтверждённое поведение background audio/GPS и lock-screen controls;
- дневной walk-through с полным GPX;
- измеренные distance/elevation/legs/arrival times;
- route/workout/slot approvals;
- полное домашнее прослушивание master;
- M1-A founder run, immediate debrief и 24-hour recall.

R02 остаётся `IN_PROGRESS`.

---

## 2. Предварительные OSM-кандидаты

Для активной фикстуры выбраны четыре публичных ориентира:

- **Старт и финиш:** Plaza de la Victoria ([OSM way 313292626](https://www.openstreetmap.org/way/313292626))
- **`threshold`:** Arco Británico ([OSM way 479821102](https://www.openstreetmap.org/way/479821102))
- **`witness`:** Parque Italia ([OSM way 313291642](https://www.openstreetmap.org/way/313291642))
- **`triangulation`:** Plaza O'Higgins ([OSM way 313290496](https://www.openstreetmap.org/way/313290496))

Локальные данные находятся в
`research/r02/local/valparaiso_central/` и не попадают в Git. Live identity
check запускается явно:

```bash
python3 tools/r02_verify_geo.py \
  --snapshot research/r02/local/valparaiso_central/osm_snapshot.json
```

OSM подтверждает только существование/type/ID/name объекта. Он не подтверждает
тротуар, переходы, трафик, ремонт, освещение, доступность, покрытие, лестницы,
приятность или соответствие нагрузке. Прямое расстояние особенно недостаточно
для рельефа Вальпараисо. Пока реального обхода нет, route metadata остаётся
неизмеренной, а human approvals — `false`.

Apple Maps preview строится через онлайн-сервис Apple и также не является safety
approval. Founder app не имеет собственного backend, аккаунтов или аналитики.

---

## 3. Master audio и пространственно-временное ограничение

Текущий M4A — 30-минутный fixed-time research master. Manifest фиксирует его
SHA/duration, 10 narrative cues и 27 workout `NAV` events. Эти 27 сигналов —
run/walk/start/finish transitions, **не turn-by-turn navigation**.

Ключевая сетка:

- `0s`: стартовый workout NAV; `8s`: `c001`;
- `240s`: `c002`;
- `365s`: `c003` (`threshold`);
- `665s`: `c004` (`witness`);
- `815s`: `c005`; `965s`: выбранная ветка `c006a`;
- `1115s`: `c007` (`triangulation`);
- `1415s`: `c008` (предполагаемое замыкание контура);
- `1510s`: `c009`; `1650s`: `c010`;
- `1792s`: финальный workout NAV до конца master в `1800s`.

Geo cues не запускаются приложением по live location. Authored fallback существует
в script contract, но текущий player не выбирает его автоматически при
пропущенном POI. Поэтому первый silent walk-through обязан измерить фактические
arrivals. Основатель не ускоряется и не меняет безопасный путь ради cue.

После GPX запускается offline analyzer:

```bash
python3 tools/r02_analyze_gpx.py \
  --gpx /absolute/local/path/to/walkthrough.gpx \
  --mission ios/RunGameFounder/Resources/Local/mission.json \
  --manifest ios/RunGameFounder/Resources/Local/m01_solo_founder_30min.manifest.json
```

Он выдаёт derived distance, unsmoothed elevation gain, четыре ordered leg
distances, closure, closest approaches, relative arrivals и cue deltas без raw
coordinates, place names, абсолютного времени старта или input path. Числовые
значения для binding собраны в `binding_field_values`; высота требует отдельной
человеческой проверки. Report не делает вывод о safety/approval.
Неполные/невалидные данные дают non-zero exit. Если меняется route/binding,
повторяются preparation, preflight и walk-through, а старый route
fingerprint/approval не переносится. Если меняется только audio timing,
повторяются preparation, preflight и полное домашнее прослушивание того же
нового SHA; старое audio approval недействительно.

---

## 4. Offline preparation перед человеком

```bash
python3 tools/r02_prepare_ios.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --output-dir ios/RunGameFounder/Resources/Local
python3 tools/r02_preflight.py \
  --fixture-dir research/r02/local/valparaiso_central \
  --ios-resources-dir ios/RunGameFounder/Resources/Local
```

Эквивалент: `make r02-preflight`. Только результат
`READY_FOR_DEVICE_SMOKE` разрешает перейти к установке; он не разрешает field run.

На 10 августа offline preflight фактически прошёл со статусом
`READY_FOR_DEVICE_SMOKE`; все route/workout/slot approvals и семь field-review
полей при этом остались отдельными human blockers. Финальные automated test
counts фиксируются после единого проверочного прогона текущего shared worktree.

---

## 5. Следующая последовательность

1. **Physical-device smoke дома.** Установить build, подтвердить bundle load,
   точное location permission, локальную тестовую запись/recovery GPX и сам факт
   lock-screen playback. Это ещё не полное аудио-одобрение.
2. **Дневной walk-through.** Без сюжета, бега и наушников пройти все POI и
   вернуться к публичному старту. Partial/incomplete GPX хранить как aborted
   evidence, не как approval.
3. **Derived analysis и human review.** Сохранить raw GPX локально, передавать в
   LLM по умолчанию только derived report; взять числовые поля из
   `binding_field_values`, отдельно записать покрытие, переходы, рельеф и route
   defects. После реального review перенести measurements/notes в локальный
   `current.binding.json` и выставить approval flags только по факту; повторный
   preflight должен убрать `human_blockers_to_m1_a`, после чего нужен обычный
   Xcode Build & Run поверх установленного приложения и видимый закрытый Mac gate.
4. **Retiming/rebuild при необходимости.** После любого изменения повторить
   preparation и preflight. Audio-only rebuild требует нового полного домашнего
   прослушивания; изменение route/binding — также нового walk-through. Не
   переносить старое `3/3` между fingerprints/SHA.
5. **Route approval.** Только достаточный сохранённый GPX через все контрольные
   точки плюс ручной checklist создают device-local fingerprint-bound approval.
   Оно не редактирует binding, не открывает participant export и не является
   production safety certification.
6. **Полная домашняя аудиопроверка.** Прослушать весь master без seeking,
   заблокировать экран, проверить Pause/Play и явно подтвердить отсутствие
   остановок, пропусков и конфликтов. Любой критичный incident отменяет approval.
7. **M1-A founder run.** Только при `3/3`, свежей GPS-точке с accuracy ≤35 м не
   дальше 100 м от публичного старта, знакомом маршруте и заранее назначенной
   следующей тренировке.
8. **Evidence capture.** Сохранить GPX и immediate JSON с единым run ID;
   recovered `.partial.gpx` считать aborted. Сохранение immediate JSON ставит
   локальный 24-hour recall в очередь. Не раньше `dueAt` заполнить его без
   просмотра immediate и экспортировать отдельный recall JSON с тем же run ID.

R02 не отмечается `COMPLETE` до реальной последовательности выше, закрытия
критичных defects и R02C A/B parity lock.
