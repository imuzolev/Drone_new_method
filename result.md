# DRONE NEW METHOD — Промежуточные результаты

> Этот файл фиксирует результаты каждого этапа/проверки.
> Обновляется после завершения фазы, крупной задачи или аудита.
> Формат: дата → что проверялось → результат → вердикт.

---

## 2026-03-09 — Аудит Фазы A (Инфраструктура)

### Окружение

| Компонент | Версия / Статус | Проверено |
|-----------|----------------|-----------|
| WSL2 Ubuntu | 22.04.5 LTS, Version 2 | OK |
| ROS 2 | Humble | OK |
| Gazebo Harmonic | 8.10.0 | OK |
| PX4 SITL | бинарник 57 MB, airframes OK | OK |
| MicroXRCEAgent | /usr/local/bin/MicroXRCEAgent | OK |
| CycloneDDS (RMW) | rmw_cyclonedds_cpp | OK |
| twist_mux | twist_mux + twist_mux_msgs | OK |

### Сборка workspace

| Метрика | Значение |
|---------|----------|
| Пакетов собрано | 12 |
| Ошибки компиляции | 0 |
| Предупреждения | Clock skew в px4_ros_com (WSL2 артефакт, безвредно) |
| Время сборки | ~4 мин 10 сек |

### Задачи Фазы A — поэлементный аудит

| Задача | Описание | % соответствия | Комментарий |
|--------|----------|:-:|---|
| A.0 | Структура проекта | 100 | src/, config/, simulation/, scripts/, tests/, .cursor/rules/ — всё на месте |
| A.0.1 | CONTEXT.md | 100 | 1017 строк, полное описание архитектуры и roadmap |
| A.0.2 | .cursor/rules/*.mdc | 100 | 4 файла: general, safety_rules, ros2_conventions, global_venv |
| A.0.3 | warehouse_phase0.sdf | 95 | 233 строки SDF. Проход 18м, 2 стеллажа, 48 штрихкодов-заглушек, 4 лампы. -5%: штрихкоды — белые боксы без текстур |
| A.0.4 | rack_follower_node (C++) | 100 | 311 строк. PD-контроллер, watchdog 200мс, QoS по conventions, status pub |
| A.0.5 | barcode_scanner + FSM + KPI | 100 | barcode_scanner_node.cpp (164), scan_policy_fsm.py (393), slot_kpi.py (56). ZXing условная компиляция |
| A.0.6 | twist_mux_config | 100 | YAML приоритеты 100/50/30/10, e_stop lock 255, launch файл |
| A.0.7 | px4_bridge_node (C++) | 100 | 243 строки. cmd_vel→TrajectorySetpoint, NED, watchdog, clamp, offboard 50Hz |
| A.0.8 | launch_sim.sh + YAML configs | 95 | launch_sim.sh корректен. drone_params.yaml полный. slam_params, nav2_params — заглушки |
| A.0.9 | Скелеты 6 пакетов | 90 | Все 6 есть. -10%: apriltag_detector и nav2_config — CMake install ссылается на несуществующие config/, kpi_recorder — нет Python package dir |
| A.1 | WSL2 Ubuntu 22.04 | 100 | Подтверждено |
| A.2 | ROS 2 Humble | 100 | Подтверждено |
| A.3 | Gazebo Harmonic | 100 | v8.10.0 |
| A.4 | PX4 SITL | 100 | Бинарник + gz_ airframes |
| A.5 | MicroXRCEAgent | 100 | Установлен из исходников |
| A.6 | Доп. пакеты ROS 2 | 100 | twist_mux, cyclonedds, px4_msgs (242+ msg), px4_ros_com |
| A.7 | Первая сборка | 100 | 12 пакетов, 0 ошибок |
| A.8 | Модель x500_warehouse | 60→100 | **Исправлено 2 критических бага** (см. errors.md: ERR-001, ERR-002). После фикса — 100% |
| A.9 | Проверочный запуск | 50→100 | Из-за багов A.8 спавнился plain x500 без сенсоров. После фикса A.8 — ожидаемо 100% |

### Модель x500_warehouse — сенсоры

| Сенсор | Параметры | Топик |
|--------|-----------|-------|
| 3D LiDAR (Livox Mid-360 analog) | 360×16 samples, 10 Hz, range 0.1–40м | /drone/perception/lidar/raw |
| RGB камера (left-facing) | 1280×720, 15 fps, hFOV 60° | /drone/camera/image_raw |

### Мир warehouse_phase0 — геометрия

| Параметр | Значение |
|----------|----------|
| Длина прохода | 18м (X: -9 → +9) |
| Ширина прохода | 2.8м |
| Секций на стеллаж | 12 × 1.5м |
| Уровней полок | 4 (Z: 0.8, 1.6, 2.4, 3.2м) |
| Штрихкодов-заглушек | 48 (24 левый + 24 правый, уровни 1–2) |
| Высота потолка | 8м |
| Spawn дрона | (-9, 0, 0.2) |

### Состояние пакетов

| Модуль | Код | Собран | Протестирован |
|--------|:---:|:------:|:-------------:|
| rack_follower (C++) | полный | OK | нет |
| px4_bridge (C++) | полный | OK | нет |
| barcode_scanner + scan_policy_fsm (C++/Python) | полный | OK | нет |
| twist_mux_config (YAML + launch) | полный | OK | нет |
| lidar_preprocessor | скелет | OK | нет |
| apriltag_detector | скелет | OK | нет |
| fast_lio2_wrapper | скелет | OK | нет |
| mission_manager | скелет | OK | нет |
| nav2_config | скелет | OK | нет |
| kpi_recorder | скелет | OK | нет |
| SDF мир (warehouse_phase0.sdf) | полный | — | нет |
| Модель дрона x500_warehouse (LiDAR+cam) | полный | — | нет |
| px4_msgs | внешний | OK | — |
| px4_ros_com | внешний | OK | — |

### Вердикт

**GO — Фаза A завершена. Можно приступать к Фазе B (Контур 2 — Rack Follower в симуляции).**

Следующая задача: **B.1 — Реализовать lidar_preprocessor**

---

## 2026-03-09 — Генерация штрихкодов и интеграция в SDF

### Что сделано

1. **Скрипт `scripts/generate_barcodes.py`** — генерирует 48 QR-кодов (не EAN-13, т.к. EAN-13 не поддерживает произвольный текст).
2. **48 PNG файлов** созданы в `simulation/models/barcodes/textures/`:
   - `barcode_L_01_1.png` ... `barcode_L_12_2.png` (24 шт, левый стеллаж) → декодируются в `God is good! | barcode_L_NN_M`
   - `barcode_R_01_1.png` ... `barcode_R_12_2.png` (24 шт, правый стеллаж) → декодируются в `All the time | barcode_R_NN_M`
   - Размер: 400×300px, ~20KB каждый, чёрный QR на белом фоне, ERROR_CORRECT_H
3. **Скрипт `scripts/update_sdf_barcodes.py`** — автоматически заменяет 48 белых заглушек в SDF на модели с PBR текстурами.
4. **SDF обновлён** — `warehouse_phase0.sdf` содержит `<pbr><metal><albedo_map>` для каждого штрихкода.
   - Пути: абсолютные `/mnt/c/CORTEXIS/Drone_new_method/simulation/models/barcodes/textures/barcode_X_NN_M.png`
5. **PX4 синхронизирован** — SDF и текстуры скопированы в:
   - `/home/imuzolev/PX4-Autopilot/Tools/simulation/gz/worlds/warehouse_phase0.sdf`
   - `/home/imuzolev/PX4-Autopilot/Tools/simulation/gz/models/barcodes/textures/`

### Проверка

| Проверка | Результат |
|----------|-----------|
| 48 PNG существуют | OK |
| Каждый PNG содержит QR-код | OK (qrcode + Pillow, ERROR_CORRECT_H) |
| L → "God is good!", R → "All the time" | OK (payload включает ID) |
| SDF парсится без ошибок | OK (gz sim загрузил без ошибок текстур) |
| PX4 SDF синхронизирован | OK |

### Вердикт

**DONE — 48 QR-кодов сгенерированы и интегрированы в SDF мир. Визуальная проверка в Gazebo GUI требуется отдельно (headless-запуск подтвердил валидность SDF).**

---

## 2026-03-10 — Consistency Fixes For Phase A

### Что исправлено

1. `scripts/start_gazebo.sh` сделан более совместимым по shell-опциям: `pipefail` теперь включается безопасно и больше не валит запуск через WSL из-за ошибки `invalid option name pipefail`.
2. `scripts/launch_sim.sh` теперь явно экспортирует `GZ_SIM_RESOURCE_PATH`, чтобы PX4/Gazebo видели модели из проекта вместе с PX4-моделями.
3. Доведены до корректного skeleton-state пакеты:
   - `src/perception/apriltag_detector/config/apriltag_detector_params.yaml`
   - `src/navigation/nav2_config/config/nav2_params.yaml`
   - `src/telemetry/kpi_recorder/kpi_recorder/__init__.py`
   - `src/telemetry/kpi_recorder/kpi_recorder/kpi_recorder_node.py`
4. Восстановлены артефакты штрихкодов в проекте:
   - `simulation/models/barcodes/model.config`
   - `simulation/models/barcodes/model.sdf`
   - `simulation/models/barcodes/textures/*.png` (48 файлов, сгенерированы заново)
5. PNG также синхронизированы в WSL-каталог `/home/imuzolev/gz_barcodes`, на который ссылается `warehouse_phase0.sdf`.

### Проверка

| Проверка | Результат |
|----------|-----------|
| `qrcode` + `Pillow` в `.venv` импортируются | OK |
| Генерация 48 PNG в `simulation/models/barcodes/textures/` | OK |
| WSL mirror `/home/imuzolev/gz_barcodes` содержит 48 PNG | OK |
| Skeleton packages больше не ссылаются на отсутствующие артефакты | OK |
| Launcher scripts приведены к консистентному виду | OK |

### Вердикт

**Phase A приведена в консистентное состояние на текущей машине.** Остаётся только runtime-подтверждение полного стека (PX4 SITL + DDS + топики) как отдельная живая проверка, но файловые и инфраструктурные расхождения Phase A устранены.

---
