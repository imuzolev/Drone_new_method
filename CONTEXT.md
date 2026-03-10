где---
description: Полный контекст проекта DRONE NEW METHOD. Архитектура, стек технологий, правила разработки.
alwaysApply: true
---

# DRONE NEW METHOD — ПОЛНЫЙ КОНТЕКСТ ПРОЕКТА ДЛЯ CURSOR

> Вставь этот файл целиком в Cursor как системный контекст.
> Версия: 2.0 | Платформа: Windows 11 + WSL2 | Фаза: Phase 0 MVP

---

## 0. СУТЬ ПРОЕКТА (читать первым)

Автономный дрон для инвентаризации склада. Летит по проходу между стеллажами,
считывает штрихкоды, возвращается на базу.

**MVP-цель (Phase 0):** дрон в симуляции Gazebo Harmonic влетает в один проход
18м длиной, считывает ≥80% штрихкодов с двух стеллажей и возвращается на старт.

**Принцип:** три независимых контура — каждый тестируется отдельно.
Следующий контур добавляется только после стабилизации предыдущего.

```
Контур 1 — SURVIVAL      : PX4 + Optical Flow + TOF → никогда не падать
Контур 2 — INSPECTION    : LiDAR Wall-Follower + Scan Policy → читать коды
Контур 3 — RELOCALIZATION: FAST-LIO2 + Pillar Constraints → знать где ты
```

**Текущий статус:** старый проект на UE5.2 + ProjectAirSim закрыт.
Начинаем с чистого листа на Gazebo Harmonic + PX4 SITL + ROS 2 Humble.

---

## 1. СРЕДА РАЗРАБОТКИ

### 1.1 Платформа
- **ОС хоста:** Windows 11
- **Среда разработки:** WSL2 (Ubuntu 22.04)
- **IDE:** Cursor (работает в Windows, подключается к WSL2 через Remote WSL)
- **Симулятор:** Gazebo Harmonic (запускается в WSL2, GUI через WSLg)
- **Корень проекта:** в WSL — `/mnt/c/CORTEXIS/Drone_new_method`, в Windows — `c:\CORTEXIS\Drone_new_method`

### 1.2 Установка окружения — пошагово

**Шаг 1: Включить WSL2**
```powershell
# В PowerShell от администратора:
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
# Перезагрузить Windows, затем открыть Ubuntu из меню Пуск
```

**Шаг 2: Базовые зависимости в Ubuntu**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git wget build-essential cmake python3-pip python3-venv \
  software-properties-common lsb-release gnupg2
```

**Шаг 3: ROS 2 Humble**
```bash
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt update
sudo apt install -y ros-humble-desktop ros-humble-ros-gz ros-dev-tools
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

**Шаг 4: Gazebo Harmonic**
```bash
sudo curl https://packages.osrfoundation.org/gazebo.gpg \
  --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
  http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list
sudo apt update
sudo apt install -y gz-harmonic
# Проверка:
gz sim --version
```

**Шаг 5: PX4 Autopilot (SITL)**
```bash
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
# Сборка SITL для Gazebo:
make px4_sitl gz_x500
# Если сборка прошла успешно — увидишь запущенный симулятор
```

**Шаг 6: Micro-XRCE-DDS Agent (мост PX4 ↔ ROS 2)**
```bash
pip install --user -U empy==3.3.4 pyros-genmsg setuptools
cd ~
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent && mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install
sudo ldconfig /usr/local/lib/
```

**Шаг 7: PX4 ROS 2 пакеты**
```bash
cd /mnt/c/CORTEXIS/Drone_new_method
mkdir -p src
git clone https://github.com/PX4/px4_msgs.git src/px4_msgs
git clone https://github.com/PX4/px4_ros_com.git src/px4_ros_com
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

**Шаг 8: CycloneDDS (вместо FastDDS — меньше латентность)**
```bash
sudo apt install -y ros-humble-rmw-cyclonedds-cpp
echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
source ~/.bashrc
```

**Шаг 9: Проверочный запуск (3 терминала)**
```bash
# Терминал 1 — PX4 SITL + Gazebo:
cd ~/PX4-Autopilot
make px4_sitl gz_x500

# Терминал 2 — Micro-XRCE-DDS Agent:
MicroXRCEAgent udp4 -p 8888

# Терминал 3 — проверить топики ROS 2:
source /mnt/c/CORTEXIS/Drone_new_method/install/setup.bash
ros2 topic list
# Должны появиться /fmu/out/... топики
```

---

## 2. СТРУКТУРА ПРОЕКТА

```
/mnt/c/CORTEXIS/Drone_new_method/   # в WSL (в Windows: c:\CORTEXIS\Drone_new_method)
├── .cursor/
│   └── rules/
│       ├── general.mdc          ← главные правила для Cursor AI
│       ├── ros2_conventions.mdc ← соглашения по именованию
│       └── safety_rules.mdc     ← нельзя нарушать
├── src/
│   ├── px4_msgs/                ← клонировать с GitHub (не редактировать)
│   ├── px4_ros_com/             ← клонировать с GitHub (не редактировать)
│   ├── control/
│   │   ├── rack_follower/       ← ПИСАТЬ ВРУЧНУЮ: LiDAR wall-following
│   │   ├── px4_bridge/          ← ПИСАТЬ ВРУЧНУЮ: команды в PX4
│   │   └── twist_mux_config/    ← конфигурация приоритетов скоростей
│   ├── perception/
│   │   ├── lidar_preprocessor/  ← ПИСАТЬ ВРУЧНУЮ: фильтрация облака точек
│   │   ├── barcode_scanner/     ← ПИСАТЬ ВРУЧНУЮ: ZXing + Scan Policy FSM
│   │   └── apriltag_detector/   ← apriltag_ros (готовый)
│   ├── slam/
│   │   └── fast_lio2_wrapper/   ← FAST-LIO2 (готовый) + параметры
│   ├── navigation/
│   │   ├── mission_manager/     ← ПИСАТЬ ВРУЧНУЮ: BehaviorTree миссии
│   │   └── nav2_config/         ← только для Transit между проходами
│   └── telemetry/
│       └── kpi_recorder/        ← ПИСАТЬ ВРУЧНУЮ: метрики миссии
├── simulation/
│   ├── worlds/
│   │   └── warehouse_phase0.sdf ← карта склада (см. раздел 8)
│   ├── models/                  ← кастомные модели Gazebo
│   └── scenarios/               ← YAML файлы тест-сценариев
├── config/
│   ├── drone_params.yaml
│   ├── slam_params.yaml
│   └── nav2_params.yaml
├── scripts/
│   ├── launch_sim.sh            ← запуск всего одной командой
│   └── analysis/                ← анализ KPI после миссии
└── tests/
    ├── unit/
    └── integration/
```

---

## 3. CURSOR RULES

### `.cursor/rules/mcp_context7.mdc`
```
# MCP Context7 Usage Rule

ОБЯЗАТЕЛЬНО: Перед написанием кода с использованием любых библиотек, API или фреймворков (особенно ROS 2, Gazebo, PX4, но не ограничиваясь ими), ты (ИИ) ДОЛЖЕН автоматически использовать MCP-сервер Context7, чтобы найти актуальную документацию и примеры кода. Не полагайся только на внутренние знания, так как они могут быть устаревшими (галлюцинациями).
```

### `.cursor/rules/general.mdc`
```
# Drone New Method — General Rules

You are assisting development of an autonomous warehouse inventory drone (project: Drone New Method).
Environment: ROS 2 Humble, C++ (performance-critical nodes), Python (mission logic).
Simulator: Gazebo Harmonic. Autopilot: PX4 SITL via Micro-XRCE-DDS.
Host OS: Windows 11, dev environment: WSL2 Ubuntu 22.04.

## Architecture (NEVER violate)
System has THREE independent loops. Never mix concerns between them:
  Loop 1 (Survival):    PX4 + TOF sensors — drone must never crash
  Loop 2 (Inspection):  LiDAR rack-follower + scan policy — read barcodes
  Loop 3 (Relocalization): FAST-LIO2 + barcode factors — know position in warehouse

Add Loop N+1 only after Loop N is stable and tested.

## Current phase: Phase 0 MVP
Goal: fly one 18m aisle, read ≥80% barcodes, return to start.
DO NOT suggest: UWB docking, GTSAM factor graph, aisle graph extraction,
  complex commissioning, NvDLA optimization. These are Phase 1+.

## Code style
- C++ nodes: follow Google C++ style, use clang-format
- Python: ruff linter, type hints required
- No magic numbers — all params via ROS 2 yaml config
- Every node publishes /node_name/status (std_msgs/String: OK/DEGRADED/FAILED)
- Business logic never in ROS callbacks — callbacks dispatch only

## When suggesting solutions
1. Always ask: which loop does this belong to?
2. Prefer simple over clever for Phase 0
3. If suggesting a library, provide the exact apt/pip install command for Ubuntu 22.04
4. If suggesting code, make it runnable in WSL2 without extra setup
```

### `.cursor/rules/ros2_conventions.mdc`
```
# ROS 2 Naming Conventions

## Topic names
/drone/control/rack_follower/cmd_vel       # TwistStamped
/drone/control/rack_follower/status        # String (OK/DEGRADED/FAILED)
/drone/control/rack_follower/wall_distance # Float32 (meters to rack)
/drone/perception/barcode/detections       # custom BarcodeDetection.msg
/drone/perception/barcode/scan_quality     # Float32 (0.0-1.0)
/drone/perception/lidar/filtered           # PointCloud2
/drone/slam/pose                           # PoseWithCovarianceStamped
/drone/slam/health                         # String
/drone/mission/state                       # String (enum)
/drone/telemetry/kpi                       # custom MissionKPI.msg
/drone/safety/battery_budget              # Float32 (% threshold)

## QoS profiles
# Sensor data: BEST_EFFORT, VOLATILE, depth=5
# Commands: RELIABLE, VOLATILE, depth=10
# Map/Config: RELIABLE, TRANSIENT_LOCAL, depth=1

## Package naming
ros2 package: snake_case (rack_follower, barcode_scanner)
Node class: PascalCase (RackFollower, BarcodeScanner)
File: snake_case.cpp / snake_case.py

## Launch files
Always use Python launch files (.launch.py), not XML
All nodes launched with parameters from yaml config files
```

### `.cursor/rules/safety_rules.mdc`
```
# Safety Rules — NEVER VIOLATE

RULE 1: Collision avoidance never goes through WiFi/network
  → TOF-based stop must be in PX4 companion script, not ROS 2 topic

RULE 2: All velocity commands have explicit timeout watchdog
  → If rack_follower sends no cmd_vel for >200ms → auto-hover
  → Implement as watchdog timer in px4_bridge node

RULE 3: No movement without valid localization
  → Before any motion: check SLAM covariance trace < threshold
  → On position loss: immediate hover, never continue mission

RULE 4: Battery threshold is always dynamic, never static
  → threshold = f(distance_to_dock, current_speed, hover_power)
  → Recalculate every 5 seconds
  → NEVER use fixed percentage like "return at 20%"

RULE 5: Barcode contradicts SLAM — both confident → STOP
  → Log event, hover in place, wait for operator
  → Never fly when two reliable sources disagree on position

RULE 6: On ANY unhandled exception in mission logic → hover and alert
  → Wrap all BehaviorTree tick() calls in try/catch
```

---

## 4. ТЕХНОЛОГИЧЕСКИЙ СТЕК

### Готовые решения — брать as-is, не изобретать

| Компонент | Репозиторий / Пакет | Установка |
|-----------|---------------------|-----------|
| Симулятор | Gazebo Harmonic | `sudo apt install gz-harmonic` |
| Autopilot | PX4 v1.14 SITL | `github.com/PX4/PX4-Autopilot` |
| DDS мост | Micro-XRCE-DDS | `github.com/eProsima/Micro-XRCE-DDS-Agent` |
| ROS msgs | px4_msgs | `github.com/PX4/px4_msgs` |
| Middleware | ROS 2 Humble | `sudo apt install ros-humble-desktop` |
| DDS | CycloneDDS | `sudo apt install ros-humble-rmw-cyclonedds-cpp` |
| SLAM | FAST-LIO2 | `github.com/hku-mars/FAST_LIO` |
| Factor Graph | GTSAM | `github.com/borglab/gtsam` (Phase 1+) |
| Nav (Transit) | Nav2 | `sudo apt install ros-humble-nav2-*` |
| Mission Logic | BehaviorTree.CPP v4 | `github.com/BehaviorTree/BehaviorTree.CPP` |
| BT Debugger | Groot2 | `behaviortree.dev` (ОБЯЗАТЕЛЕН) |
| Barcode | ZXing-C++ | `github.com/zxing-cpp/zxing-cpp` |
| AprilTag | apriltag_ros | `sudo apt install ros-humble-apriltag-ros` |
| Ground removal | linefit | `github.com/lorenwel/linefit_ground_segmentation` |
| Vel. arbitration | twist_mux | `sudo apt install ros-humble-twist-mux` |
| Localization | robot_localization | `sudo apt install ros-humble-robot-localization` |

### Писать вручную — готового нет

| Модуль | Файл | Описание |
|--------|------|----------|
| `rack_follower_node` | `src/control/rack_follower/` | P/PD controller по LiDAR distance |
| `scan_policy_fsm` | `src/perception/barcode_scanner/` | FSM управления сканированием |
| `pillar_constraint_node` | `src/slam/fast_lio2_wrapper/` | детектор стоек для SLAM |
| `battery_budget_node` | `src/control/px4_bridge/` | динамический порог возврата |
| `barcode_conflict_resolver` | `src/navigation/mission_manager/` | логика противоречий |
| `aisle_entry_controller` | `src/control/rack_follower/` | handover Nav2 → RackFollower |
| `kpi_recorder_node` | `src/telemetry/kpi_recorder/` | метрики миссии |
| BehaviorTree leaf nodes | `src/navigation/mission_manager/` | actions и conditions |

---

## 5. КЛЮЧЕВЫЕ МОДУЛИ — КОД И ЛОГИКА

### 5.1 Rack Follower (Контур 2 — самый важный)

```cpp
// src/control/rack_follower/rack_follower_node.cpp
// Логика: держать дистанцию target_distance до стеллажа через LiDAR
// Вход:  /drone/perception/lidar/filtered (PointCloud2)
// Выход: /drone/control/rack_follower/cmd_vel (TwistStamped)

// Алгоритм:
// 1. Из облака точек взять минимальное расстояние по оси Y (боковое)
// 2. error = target_distance - measured_distance
// 3. v_lateral = Kp * error + Kd * d(error)/dt
// 4. v_forward = base_speed * (1.0 - abs(error) / max_error)
//    (замедляться при большой ошибке, останавливаться если ошибка критическая)
// 5. Watchdog: если нет входящих данных >200ms → публиковать нулевую скорость

// Параметры для тюнинга (в yaml):
// target_distance: 0.8  # метры от стеллажа
// Kp: 0.5               # начальное значение, тюнить
// Kd: 0.1
// base_speed: 0.3       # м/с при сканировании
// max_error: 0.4        # при этой ошибке скорость = 0
// watchdog_timeout_ms: 200
```

### 5.2 Scan Policy FSM

```python
# src/perception/barcode_scanner/scan_policy_fsm.py
# Состояния:
#   APPROACH  → летим к стеллажу, инициализация
#   SCANNING  → движемся вдоль на скорости 0.3 м/с, читаем коды
#   HOVER_SCAN→ зависли для повторного считывания плохого слота
#   ADJUSTING → меняем дистанцию ±0.1м при низком качестве
#   DONE      → проход завершён

# Переходы:
#   APPROACH  → SCANNING:    rack_follower stable + distance OK (1с подряд)
#   SCANNING  → HOVER_SCAN:  scan_quality < 0.6 на текущем слоте
#   HOVER_SCAN→ ADJUSTING:   3 попытки failed
#   ADJUSTING → HOVER_SCAN:  дистанция изменена
#   ADJUSTING → DONE(FAIL):  6 попыток total → пометить MANUAL_REVIEW
#   SCANNING  → DONE:        X > aisle_end_threshold

# Output на каждый слот:
#   { slot_id, barcode_value, confidence, timestamp, attempts, status }
#   status: SUCCESS | PARTIAL | MANUAL_REVIEW
```

### 5.3 Handover Nav2 → Rack Follower

```python
# Entry Zone = буфер 1.5м перед входом в проход
# Логика переключения:

# 1. Nav2 приводит дрон к точке AisleEntry (X=-9, Y=0)
# 2. В Entry Zone:
#    a. Отменить Nav2 action (cancel NavigateToPose)
#    b. Уменьшить скорость до 0.2 м/с
#    c. Активировать RackFollower node
#    d. Ждать stable state:
#       - lateral_error < 0.05м в течение 1 секунды
#       - rack_detected = True на обоих сторонах
#    e. twist_mux приоритет → rack_follower (выше nav2)
#    f. Переключить Scan Policy в SCANNING

# При выходе из прохода (X > 9.0):
#    a. Rack Follower → deactivate
#    b. Nav2 → resume с текущей позицией из SLAM
#    c. twist_mux приоритет → nav2
```

### 5.4 Barcode Contradiction Logic

```python
def resolve_barcode_slam_conflict(barcode_conf, slam_cov_trace, barcode_matches_slam):
    SLAM_UNCERTAIN = 0.5   # порог ковариации (тюнить)
    BC_RELIABLE    = 0.95  # порог уверенности в считывании

    if barcode_conf > BC_RELIABLE and slam_cov_trace > SLAM_UNCERTAIN:
        # SLAM деградировал, барcode надёжен → релокализация
        return "RELOCALIZE_FROM_BARCODE"
    elif barcode_conf > BC_RELIABLE and slam_cov_trace < SLAM_UNCERTAIN:
        if not barcode_matches_slam:
            # Оба уверены, но противоречат — КРИТИЧНО
            return "HOVER_AND_ALERT_OPERATOR"
        return "CONTINUE"
    elif barcode_conf < 0.5:
        # Барcode ненадёжен → игнорировать, доверять SLAM
        return "IGNORE_BARCODE"
    else:
        return "REDUCE_SPEED_COLLECT_MORE_DATA"
```

### 5.5 Dynamic Battery Budget

```python
def compute_return_threshold(
    current_pos, dock_pos,
    flight_power_w=120, hover_power_w=100,
    return_speed=2.0, battery_capacity_wh=22.2
):
    import math
    distance = math.sqrt(sum((a-b)**2 for a,b in zip(current_pos, dock_pos)))
    return_time_sec = (distance / return_speed) * 1.2   # +20% запас
    landing_energy_wh = 3 * 30 * hover_power_w / 3600   # 3 попытки посадки
    return_energy_wh = (return_time_sec * flight_power_w / 3600) + landing_energy_wh
    threshold_pct = (return_energy_wh / battery_capacity_wh) * 100 + 5  # +5% margin
    return min(threshold_pct, 40.0)  # не выше 40% в любом случае
```

### 5.6 Pillar Constraint Node (для Контура 3)

```python
# src/slam/fast_lio2_wrapper/pillar_detector.py
# Алгоритм:
# 1. Принять /drone/perception/lidar/filtered (PointCloud2)
# 2. Фильтр по высоте: оставить точки 0.1м < z < 3.5м (убрать пол/потолок)
# 3. PCL EuclideanClusterExtraction: найти вертикальные кластеры
# 4. Для каждого кластера — RANSAC на вертикальный цилиндр/бокс
#    Критерии стойки: ширина < 0.15м, высота > 1.5м
# 5. Сортировать по X-позиции вдоль прохода
# 6. Детектировать регулярный шаг (ожидаемый: 1.5м)
#    Метод: sliding window autocorrelation на X-позициях стоек
# 7. Публиковать Between Factors в GTSAM topic (Phase 1)
#    Для Phase 0: только визуализировать в RViz2

# Зависимости: python3-pcl или open3d
# Установка: pip install open3d --break-system-packages
```

---

## 6. FAIL-SAFES — BEHAVIOR TREE

### 6.1 Потеря одометрии в тёмном углу
```
FallbackNode: VisualLoss
├── Condition: IsLidarHealthy?           ← FAST-LIO2 health check
│   └── True → продолжить нормально
└── Sequence: LidarLossRecovery
    ├── PublishEvent(LIDAR_LOST)
    ├── ReduceVelocity(0.05 м/с)
    ├── ActivateFrontLED(MAX)
    ├── Retry(3): ScanForKnownBarcode   ← из карты, ближайший
    └── [fail] InitiateWallFollowReturn ← Level 1: по стене к доку
```

### 6.2 Проход заблокирован (погрузчик и т.п.)
```
FallbackNode: AisleBlocked
├── Condition: IsPathClear(3м вперёд)?
│   └── True → продолжить
└── Sequence: BlockedHandler
    ├── HoverInPlace(30с)
    ├── [если не уехал] MarkAisleBlocked(aisle_id)
    ├── ReplanMissionSkipAisle
    └── [нет альтернативы] ReturnToDock(report=AISLE_BLOCKED)
```

### 6.3 Критический разряд батареи внутри прохода
```
ParallelNode: BatteryMonitor (всегда активен)
├── Sequence: CriticalBattery
│   ├── Condition: Battery% < compute_return_threshold()?
│   ├── Condition: ReturnEnergyAvailable?
│   │   ├── True  → EmergencyReturn(override=True)
│   │   └── False → ImmediateDescentSafeZone + PublishAlarm
└── Condition: Battery% < 25%?
    └── AbortAisle + ReturnToDock(save_partial_data=True)
```

### 6.4 Штрихкод не читается (Data Quality Failure — КРИТИЧНО)
```
FallbackNode: BarcodeQuality
├── Condition: ScanQuality > 0.6?
│   └── True → продолжить
└── Sequence: QualityRecovery
    ├── HoverInPlace
    ├── Retry(3): AdjustDistance(±0.1м шаги)
    ├── Retry(2): AdjustTilt(±5°)
    └── [6 попыток fail] MarkSlot(MANUAL_REVIEW) + Continue
```

---

## 7. MISSION KPI LAYER

```python
# src/telemetry/kpi_recorder/kpi_recorder_node.py
# ОБЯЗАТЕЛЕН — без него невозможно понять работает ли система

from dataclasses import dataclass
from typing import Literal

@dataclass
class SlotKPI:
    slot_id: str
    aisle_id: str
    attempt_count: int
    success: bool
    scan_quality: float
    time_spent_sec: float
    status: Literal['SUCCESS', 'PARTIAL', 'MANUAL_REVIEW']

@dataclass
class MissionKPI:
    mission_id: str
    total_slots_attempted: int
    successful_reads: int
    manual_review_count: int
    total_distance_m: float
    total_time_sec: float
    # Производные — ключевые метрики:
    success_rate: float           # target Phase 0: > 0.80
    avg_attempts_per_slot: float  # target: < 1.5
    reads_per_meter: float        # target: > 0.5
    # Go/No-Go критерий Phase 0:
    # success_rate > 0.80 → Phase 1
    # success_rate < 0.80 → итерировать Контур 2 (Inspection)
```

---

## 8. КАРТА СКЛАДА (warehouse_phase0.sdf)

Сохранить как `simulation/worlds/warehouse_phase0.sdf` (полный путь в WSL: `/mnt/c/CORTEXIS/Drone_new_method/simulation/worlds/warehouse_phase0.sdf`)

Параметры:
- Проход: 18м длина × 2.8м ширина
- Стеллажи с обеих сторон: высота 4м, 12 секций по 1.5м
- 4 полки: высоты 0.8 / 1.6 / 2.4 / 3.2м
- Стойки (pillars): 13 шт × шаг 1.5м — критично для Pillar Detector
- Штрихкоды: белые заглушки на уровнях 1 и 2 (48 шт) → заменить PNG текстурами
- Дрон: синяя заглушка на старте X=-9, Y=0, Z=1.0, красный нос = направление +X
- Освещение: 3 точечных источника + ambient ≈ 350 lux
- AprilTag dock маркер на полу у старта

**Запуск:**
```bash
cd /mnt/c/CORTEXIS/Drone_new_method
gz sim simulation/worlds/warehouse_phase0.sdf
```

**Следующий шаг:** сгенерировать PNG штрихкоды (EAN-13/QR) и подключить
как текстуры к моделям `bcL_*` и `bcR_*` в SDF.

```xml
<?xml version="1.0" ?>
<sdf version="1.9">
  <world name="warehouse_phase0">

    <!-- ФИЗИКА -->
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <!-- ПЛАГИНЫ -->
    <plugin filename="gz-sim-physics-system"           name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system"     name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system"           name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>

    <!-- ОСВЕЩЕНИЕ: 3 точечных лампы под потолком + ambient fill -->
    <light name="lamp_start" type="point">
      <pose>-5 0 7.5 0 0 0</pose><cast_shadows>true</cast_shadows><intensity>1.1</intensity>
      <diffuse>0.95 0.95 0.9 1</diffuse><specular>0.3 0.3 0.3 1</specular>
      <attenuation><range>16</range><constant>0.3</constant><linear>0.02</linear><quadratic>0.005</quadratic></attenuation>
    </light>
    <light name="lamp_center" type="point">
      <pose>0 0 7.5 0 0 0</pose><cast_shadows>false</cast_shadows><intensity>1.0</intensity>
      <diffuse>0.9 0.9 0.85 1</diffuse><specular>0.2 0.2 0.2 1</specular>
      <attenuation><range>16</range><constant>0.3</constant><linear>0.02</linear><quadratic>0.005</quadratic></attenuation>
    </light>
    <light name="lamp_end" type="point">
      <pose>5 0 7.5 0 0 0</pose><cast_shadows>false</cast_shadows><intensity>1.0</intensity>
      <diffuse>0.9 0.9 0.85 1</diffuse><specular>0.2 0.2 0.2 1</specular>
      <attenuation><range>16</range><constant>0.3</constant><linear>0.02</linear><quadratic>0.005</quadratic></attenuation>
    </light>
    <light name="ambient_fill" type="directional">
      <pose>0 0 10 0 0 0</pose><cast_shadows>false</cast_shadows><intensity>0.35</intensity>
      <direction>0 0 -1</direction><diffuse>0.55 0.55 0.55 1</diffuse><specular>0.05 0.05 0.05 1</specular>
    </light>

    <!-- ПОЛ 25×12м -->
    <model name="floor"><static>true</static><pose>0 0 0 0 0 0</pose>
      <link name="link">
        <collision name="col"><geometry><box><size>25 12 0.1</size></box></geometry></collision>
        <visual name="vis"><geometry><box><size>25 12 0.1</size></box></geometry>
          <material><ambient>0.35 0.35 0.35 1</ambient><diffuse>0.45 0.45 0.45 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- ПОТОЛОК на высоте 8м — нужен для реалистичного LiDAR -->
    <model name="ceiling"><static>true</static><pose>0 0 8 0 0 0</pose>
      <link name="link">
        <collision name="col"><geometry><box><size>25 12 0.1</size></box></geometry></collision>
        <visual name="vis"><geometry><box><size>25 12 0.1</size></box></geometry>
          <material><ambient>0.55 0.55 0.55 1</ambient><diffuse>0.6 0.6 0.6 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!--
    ГЕОМЕТРИЯ ПРОХОДА:
      Длина: 18м (X от -9 до +9)
      Ширина: 2.8м
      Левый стеллаж:  Y_фронт = +1.45, Y_зад = +2.95
      Правый стеллаж: Y_фронт = -1.45, Y_зад = -2.95
      Высота стеллажей: 4.0м
      Секции: 12 × 1.5м (центры: ±8.25, ±6.75, ±5.25, ±3.75, ±2.25, ±0.75)
      Стойки: 13 × 1.5м (X: -9,-7.5,-6,-4.5,-3,-1.5,0,1.5,3,4.5,6,7.5,9)
      Полки: 4 уровня (Z: 0.8, 1.6, 2.4, 3.2м)
      Штрихкоды: уровни 1 и 2 — высота сканирования дрона
    -->

    <!-- ===== ЛЕВЫЙ СТЕЛЛАЖ (Y > 0) ===== -->

    <!-- Задняя стена левого стеллажа -->
    <model name="rack_L_back"><static>true</static><pose>0 2.95 2.0 0 0 0</pose>
      <link name="link">
        <collision name="col"><geometry><box><size>18.2 0.1 4.0</size></box></geometry></collision>
        <visual name="vis"><geometry><box><size>18.2 0.1 4.0</size></box></geometry>
          <material><ambient>0.5 0.4 0.3 1</ambient><diffuse>0.55 0.45 0.35 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- Горизонтальные полки левого стеллажа: 4 уровня -->
    <model name="shelf_L1"><static>true</static><pose>0 1.7 0.8 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_L2"><static>true</static><pose>0 1.7 1.6 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_L3"><static>true</static><pose>0 1.7 2.4 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_L4"><static>true</static><pose>0 1.7 3.2 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>

    <!-- Стойки левого стеллажа: 13 шт × шаг 1.5м
         ВАЖНО для Pillar Detector — регулярный шаг критичен для SLAM constraint -->
    <model name="pL0"> <static>true</static><pose>-9.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL1"> <static>true</static><pose>-7.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL2"> <static>true</static><pose>-6.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL3"> <static>true</static><pose>-4.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL4"> <static>true</static><pose>-3.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL5"> <static>true</static><pose>-1.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL6"> <static>true</static><pose> 0.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL7"> <static>true</static><pose> 1.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL8"> <static>true</static><pose> 3.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL9"> <static>true</static><pose> 4.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL10"><static>true</static><pose> 6.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL11"><static>true</static><pose> 7.5 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pL12"><static>true</static><pose> 9.0 1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>

    <!-- Штрихкоды левого стеллажа — уровень 1 (Z=0.8м)
         Белые панели-заглушки. Заменить на PNG текстуры EAN-13/QR.
         Центры секций: X = -8.25, -6.75, -5.25, -3.75, -2.25, -0.75, 0.75, 2.25, 3.75, 5.25, 6.75, 8.25 -->
    <model name="bcL_1_1"> <static>true</static><pose>-8.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_2_1"> <static>true</static><pose>-6.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_3_1"> <static>true</static><pose>-5.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_4_1"> <static>true</static><pose>-3.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_5_1"> <static>true</static><pose>-2.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_6_1"> <static>true</static><pose>-0.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_7_1"> <static>true</static><pose> 0.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_8_1"> <static>true</static><pose> 2.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_9_1"> <static>true</static><pose> 3.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_10_1"><static>true</static><pose> 5.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_11_1"><static>true</static><pose> 6.75 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_12_1"><static>true</static><pose> 8.25 1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>

    <!-- Штрихкоды левого стеллажа — уровень 2 (Z=1.6м) -->
    <model name="bcL_1_2"> <static>true</static><pose>-8.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_2_2"> <static>true</static><pose>-6.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_3_2"> <static>true</static><pose>-5.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_4_2"> <static>true</static><pose>-3.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_5_2"> <static>true</static><pose>-2.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_6_2"> <static>true</static><pose>-0.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_7_2"> <static>true</static><pose> 0.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_8_2"> <static>true</static><pose> 2.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_9_2"> <static>true</static><pose> 3.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_10_2"><static>true</static><pose> 5.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_11_2"><static>true</static><pose> 6.75 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcL_12_2"><static>true</static><pose> 8.25 1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>

    <!-- ===== ПРАВЫЙ СТЕЛЛАЖ (Y < 0) ===== -->

    <model name="rack_R_back"><static>true</static><pose>0 -2.95 2.0 0 0 0</pose>
      <link name="link">
        <collision name="col"><geometry><box><size>18.2 0.1 4.0</size></box></geometry></collision>
        <visual name="vis"><geometry><box><size>18.2 0.1 4.0</size></box></geometry>
          <material><ambient>0.5 0.4 0.3 1</ambient><diffuse>0.55 0.45 0.35 1</diffuse></material>
        </visual>
      </link>
    </model>

    <model name="shelf_R1"><static>true</static><pose>0 -1.7 0.8 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_R2"><static>true</static><pose>0 -1.7 1.6 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_R3"><static>true</static><pose>0 -1.7 2.4 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>
    <model name="shelf_R4"><static>true</static><pose>0 -1.7 3.2 0 0 0</pose><link name="l">
      <collision name="c"><geometry><box><size>18 0.5 0.04</size></box></geometry></collision>
      <visual name="v"><geometry><box><size>18 0.5 0.04</size></box></geometry>
        <material><ambient>0.45 0.35 0.25 1</ambient><diffuse>0.5 0.4 0.3 1</diffuse></material></visual></link></model>

    <!-- Стойки правого стеллажа: 13 шт -->
    <model name="pR0"> <static>true</static><pose>-9.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR1"> <static>true</static><pose>-7.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR2"> <static>true</static><pose>-6.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR3"> <static>true</static><pose>-4.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR4"> <static>true</static><pose>-3.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR5"> <static>true</static><pose>-1.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR6"> <static>true</static><pose> 0.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR7"> <static>true</static><pose> 1.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR8"> <static>true</static><pose> 3.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR9"> <static>true</static><pose> 4.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR10"><static>true</static><pose> 6.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR11"><static>true</static><pose> 7.5 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>
    <model name="pR12"><static>true</static><pose> 9.0 -1.72 2.0 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.08 0.08 4.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.08 0.08 4.0</size></box></geometry><material><ambient>0.25 0.25 0.25 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual></link></model>

    <!-- Штрихкоды правого стеллажа — уровень 1 (Z=0.8м) -->
    <model name="bcR_1_1"> <static>true</static><pose>-8.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_2_1"> <static>true</static><pose>-6.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_3_1"> <static>true</static><pose>-5.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_4_1"> <static>true</static><pose>-3.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_5_1"> <static>true</static><pose>-2.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_6_1"> <static>true</static><pose>-0.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_7_1"> <static>true</static><pose> 0.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_8_1"> <static>true</static><pose> 2.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_9_1"> <static>true</static><pose> 3.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_10_1"><static>true</static><pose> 5.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_11_1"><static>true</static><pose> 6.75 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_12_1"><static>true</static><pose> 8.25 -1.43 0.8 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>

    <!-- Штрихкоды правого стеллажа — уровень 2 (Z=1.6м) -->
    <model name="bcR_1_2"> <static>true</static><pose>-8.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_2_2"> <static>true</static><pose>-6.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_3_2"> <static>true</static><pose>-5.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_4_2"> <static>true</static><pose>-3.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_5_2"> <static>true</static><pose>-2.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_6_2"> <static>true</static><pose>-0.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_7_2"> <static>true</static><pose> 0.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_8_2"> <static>true</static><pose> 2.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_9_2"> <static>true</static><pose> 3.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_10_2"><static>true</static><pose> 5.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_11_2"><static>true</static><pose> 6.75 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>
    <model name="bcR_12_2"><static>true</static><pose> 8.25 -1.43 1.6 0 0 0</pose><link name="l"><visual name="v"><geometry><box><size>0.12 0.005 0.07</size></box></geometry><material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material></visual></link></model>

    <!-- ДРОН — визуальная заглушка на стартовой позиции
         Старт: X=-9.0, Y=0.0, Z=1.0 (высота полёта)
         Синий корпус, красный нос = направление полёта (+X)
         ЗАМЕНИТЬ на реальную модель x500 после установки PX4:
           <include><uri>model://x500</uri><pose>-9 0 0.5 0 0 0</pose></include> -->
    <model name="drone">
      <static>false</static>
      <pose>-9.0 0 1.0 0 0 0</pose>
      <link name="base_link">
        <visual name="body">
          <geometry><box><size>0.35 0.35 0.08</size></box></geometry>
          <material><ambient>0.1 0.1 0.85 1</ambient><diffuse>0.15 0.15 0.95 1</diffuse></material>
        </visual>
        <visual name="arm_fl"><pose>0.12 0.12 0 0 0 0.785</pose>
          <geometry><box><size>0.25 0.04 0.03</size></box></geometry>
          <material><ambient>0.2 0.2 0.2 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>
        <visual name="arm_fr"><pose>0.12 -0.12 0 0 0 -0.785</pose>
          <geometry><box><size>0.25 0.04 0.03</size></box></geometry>
          <material><ambient>0.2 0.2 0.2 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>
        <visual name="arm_rl"><pose>-0.12 0.12 0 0 0 -0.785</pose>
          <geometry><box><size>0.25 0.04 0.03</size></box></geometry>
          <material><ambient>0.2 0.2 0.2 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>
        <visual name="arm_rr"><pose>-0.12 -0.12 0 0 0 0.785</pose>
          <geometry><box><size>0.25 0.04 0.03</size></box></geometry>
          <material><ambient>0.2 0.2 0.2 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>
        <visual name="motor_fl"><pose>0.18 0.18 0.02 0 0 0</pose>
          <geometry><cylinder><radius>0.055</radius><length>0.02</length></cylinder></geometry>
          <material><ambient>0.7 0.7 0.7 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material></visual>
        <visual name="motor_fr"><pose>0.18 -0.18 0.02 0 0 0</pose>
          <geometry><cylinder><radius>0.055</radius><length>0.02</length></cylinder></geometry>
          <material><ambient>0.7 0.7 0.7 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material></visual>
        <visual name="motor_rl"><pose>-0.18 0.18 0.02 0 0 0</pose>
          <geometry><cylinder><radius>0.055</radius><length>0.02</length></cylinder></geometry>
          <material><ambient>0.7 0.7 0.7 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material></visual>
        <visual name="motor_rr"><pose>-0.18 -0.18 0.02 0 0 0</pose>
          <geometry><cylinder><radius>0.055</radius><length>0.02</length></cylinder></geometry>
          <material><ambient>0.7 0.7 0.7 1</ambient><diffuse>0.8 0.8 0.8 1</diffuse></material></visual>
        <visual name="nose"><pose>0.2 0 0 0 0 0</pose>
          <geometry><sphere><radius>0.03</radius></sphere></geometry>
          <material><ambient>1 0 0 1</ambient><diffuse>1 0 0 1</diffuse></material></visual>
        <inertial>
          <mass>1.5</mass>
          <inertia><ixx>0.015</ixx><iyy>0.015</iyy><izz>0.025</izz></inertia>
        </inertial>
        <collision name="col">
          <geometry><box><size>0.4 0.4 0.1</size></box></geometry>
        </collision>
      </link>
    </model>

    <!-- AprilTag dock маркер на полу у старта (X=-9.5) -->
    <model name="dock_apriltag"><static>true</static><pose>-9.5 0 0.06 0 0 0</pose>
      <link name="link">
        <visual name="vis"><geometry><box><size>0.4 0.4 0.01</size></box></geometry>
          <material><ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse></material>
        </visual>
      </link>
    </model>

  </world>
</sdf>
```

---

## 9. PHASE 0 ROADMAP

### Неделя 1 — Фундамент
```
[ ] WSL2 + Ubuntu 22.04 настроен
[ ] ROS 2 Humble установлен, ros2 topic list работает
[ ] Gazebo Harmonic: gz sim warehouse_phase0.sdf открывается
[ ] PX4 SITL: make px4_sitl gz_x500 собирается и запускается
[ ] Micro-XRCE-DDS: /fmu/out/* топики видны в ROS 2
[ ] Структура папок workspace создана
[ ] .cursor/rules/*.mdc файлы созданы
ПРОВЕРКА: дрон в Gazebo удерживает позицию 30 секунд без падения
```

### Неделя 2 — Контур 2 (основа)
```
[ ] rack_follower_node v1: P-controller, держит дистанцию от стены
[ ] LiDAR данные из Gazebo приходят на /drone/perception/lidar/filtered
[ ] twist_mux настроен с приоритетами
[ ] Watchdog: нет команды 200мс → hover
ПРОВЕРКА: дрон летит вдоль стеллажа 18м, lateral_error_rms < 0.10м
```

### Неделя 3 — Считывание кодов
```
[ ] ZXing-C++ собран и интегрирован
[ ] Camera топик из Gazebo → ZXing pipeline
[ ] PNG штрихкоды подключены к моделям в SDF
[ ] scan_policy_fsm v1: APPROACH → HOVER_SCAN → DONE
[ ] Первые считанные коды логируются с позицией
ПРОВЕРКА: 5 штрихкодов считаны при ручном зависании напротив
```

### Неделя 4 — SLAM и связность
```
[ ] FAST-LIO2 запущен в Gazebo, карта строится
[ ] Nav2 базовая конфигурация для Transit
[ ] Handover v1: грубое переключение Nav2 → RackFollower
[ ] kpi_recorder_node пишет SlotKPI в CSV
ПРОВЕРКА: дрон едет от дока до входа в проход через Nav2
```

### Неделя 5 — End-to-End
```
[ ] Полный цикл: dock → transit → вход → сканирование → возврат
[ ] BehaviorTree управляет всей миссией
[ ] Все 4 fail-safe сценария реализованы в BT
ПРОВЕРКА: 3 полных прогона без крашей
```

### Неделя 6 — Измерение и Go/No-Go
```
[ ] 10 прогонов, сохранить KPI каждого
[ ] Посчитать success_rate
[ ] Задокументировать все failure modes из реальных прогонов
GO: success_rate > 0.80 → начать Phase 1 (Hardware-in-Loop)
NO-GO: success_rate ≤ 0.80 → найти узкое место через KPI, итерировать
```

---

## 10. ТИПИЧНЫЕ ОШИБКИ (изучить до начала)

| Ошибка | Причина | Решение |
|--------|---------|---------|
| LiDAR corridor degeneracy | Две параллельные плоскости → ICP underconstrained | Pillar Between Factors по оси прохода |
| Nav2 застрял в Entry Zone | inflation radius блокирует узкий проход | Entry Zone controller с уменьшенным inflation |
| Rack Follower осциллирует | Kp слишком высокий + wall effect | Уменьшить Kp, добавить Kd, feedforward при dist < 0.6м |
| Штрихкод не читается ZXing | Motion blur при скорости 0.3м/с | exposure ≤ 1/500s, LED подсветка, HOVER_SCAN mode |
| DDS лаг при WiFi roaming | FastDDS + нестабильная сеть | CycloneDDS + safety logic в PX4, не через сеть |
| Handover вызывает рывок | Nav2 не отменён, борьба velocity commanders | Обязательно cancel Nav2 action перед активацией RackFollower |
| Barcode reads wrong aisle | Perceptual aliasing идентичных проходов | Barcode-first relocalization, не ORB features |
| Батарея садится в проходе | Статический порог не учитывает расстояние | Dynamic budget, пересчёт каждые 5с |

---

## 11. ПОЛЕЗНЫЕ КОМАНДЫ

Все команды ниже — из корня проекта в WSL: `cd /mnt/c/CORTEXIS/Drone_new_method` (в PowerShell: `cd c:\CORTEXIS\Drone_new_method`).

```bash
# Перейти в корень проекта (WSL):
cd /mnt/c/CORTEXIS/Drone_new_method
source install/setup.bash

# Запуск всей системы (после написания launch файла):
ros2 launch drone_new_method full_sim.launch.py

# Запуск только Gazebo с картой:
gz sim simulation/worlds/warehouse_phase0.sdf

# Запуск PX4 SITL (в отдельном терминале):
cd ~/PX4-Autopilot && make px4_sitl gz_x500

# Запуск DDS агента:
MicroXRCEAgent udp4 -p 8888

# Просмотр всех топиков:
ros2 topic list | grep drone

# Просмотр LiDAR данных:
ros2 topic echo /drone/perception/lidar/filtered --no-arr

# Просмотр позиции дрона:
ros2 topic echo /drone/slam/pose

# Визуализация в RViz2:
ros2 run rviz2 rviz2

# Сборка workspace:
cd /mnt/c/CORTEXIS/Drone_new_method && colcon build --symlink-install

# Запуск тестов:
cd /mnt/c/CORTEXIS/Drone_new_method && colcon test && colcon test-result --verbose

# Анализ KPI после миссии:
cd /mnt/c/CORTEXIS/Drone_new_method && python3 scripts/analysis/compute_kpi.py --bag rosbags/mission_001/
```

---

## 12. HARDWARE TARGET (Phase 1+ — не нужно сейчас)

```
Flight Controller:  Holybro Pixhawk 6C
Companion Computer: Jetson Orin NX 16GB
LiDAR:             Livox Mid-360 (360°, 40м range)
Camera:            FLIR Blackfly S Global Shutter (9MP)
Rangefinders:      Benewake TFmini-S × 4 (front/back/left/right)
Optical Flow:      PX4Flow
Frame:             Ducted design (кольцевые кожухи — обязательно)
Battery:           6S LiPo 22.2V 6000mAh
```

Compute distribution на Jetson (Phase 1+):
- NvDLA: barcode ROI detector (YOLOv8-nano INT8, ~2ms)
- GPU: FAST-LIO2 point cloud processing
- CPU cores 0-1: ROS 2 CycloneDDS (isolated via isolcpus)
- CPU core 2: BehaviorTree.CPP mission logic
- CPU core 3: Nav2 planner
- CPU core 4: ZXing barcode decode (on-demand)

---

*Документ актуален для Phase 0. Обновить после перехода в Phase 1.*
*Всё что помечено "(Phase 1+)" — не реализовывать сейчас.*
