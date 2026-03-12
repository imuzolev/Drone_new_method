# Drone New Method

## Описание

**Drone New Method** — проект автономного дрона для инвентаризации складов. Дрон летит по проходам между стеллажами, считывает штрихкоды с полок и возвращается на точку старта. Система предназначена для автоматизации учёта товаров без участия человека в зоне хранения.

**Проблема:** ручная инвентаризация занимает много времени и подвержена ошибкам. Дрон может пролететь десятки проходов за смену, собирая данные о каждой ячейке.

**Подход:** три независимых контура — выживание (полёт), осмотр (считывание кодов), локализация (знание позиции). Каждый контур настраивается отдельно, что упрощает отладку и повышает надёжность.

---

## Цель проекта

| Фаза | Цель | Критерий успеха |
|------|------|-----------------|
| **Phase 0 (MVP)** | Первый полный цикл в симуляции | Пролететь один проход 18 м, считать ≥80% штрихкодов (≥38 из 48), вернуться на старт |
| Phase 1+ | Hardware-in-the-Loop | Реальный дрон в тестовом складе |

**Текущий статус:** Phase 0 MVP — тюнинг Rack Follower (следование вдоль стеллажа по LiDAR), интеграция со считыванием штрихкодов. Базовая инфраструктура готова, симуляция стабильна.

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Симулятор | Gazebo Harmonic |
| Автопилот | PX4 SITL (software-in-the-loop) |
| Middleware | ROS 2 Humble |
| DDS | CycloneDDS |
| SLAM | FAST-LIO2 |
| Сценарий | Склад warehouse_phase0: проход 18×2.8 м, 2 стеллажа, 48 штрихкодов |

---

## Быстрый старт

### Окружение

- **ОС:** Windows 11
- **Среда:** WSL2 Ubuntu 22.04
- **Стек:** ROS 2 Humble, Gazebo Harmonic, PX4 SITL

### Запуск симуляции

```bash
# В WSL: перейти в корень проекта
cd /mnt/c/CORTEXIS/Drone_new_method

# Терминал 1: симуляция (PX4 + Gazebo + DDS + ros_gz_bridge)
bash scripts/launch_sim.sh

# Терминал 2: управление дроном (Loop 2 — Rack Follower)
source /opt/ros/humble/setup.bash
source install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 launch drone_bringup loop2.launch.py

# Взлёт и полёт вдоль стеллажа — через отдельный скрипт:
python3 scripts/offboard_takeoff_via_twist_mux.py
```

### Перед первым запуском

1. Установить зависимости (см. [CONTEXT.md](CONTEXT.md) — раздел «Установка окружения»)
2. Собрать workspace: `colcon build --symlink-install`
3. Клонировать PX4-Autopilot и настроить airframe `gz_x500_warehouse`

---

## Цель Phase 0

- Пролететь один проход 18 м между стеллажами
- Считать **≥80% штрихкодов** (≥38 из 48)
- Вернуться на старт без падения

---

## Архитектура — три контура

Система разбита на три независимых контура. Каждый настраивается и тестируется по отдельности:

| Контур | Назначение | Компоненты |
|--------|------------|------------|
| **1. Survival** | Дрон не падает | PX4, Optical Flow, TOF |
| **2. Inspection** | Считывание штрихкодов | LiDAR Rack Follower, Scan Policy FSM |
| **3. Relocalization** | Оценка позиции | FAST-LIO2, ограничения по штрихкодам |

---

## Структура проекта

```
├── src/
│   ├── control/           # px4_bridge, rack_follower
│   ├── perception/       # lidar_preprocessor, barcode_scanner
│   ├── slam/             # fast_lio2_wrapper
│   ├── navigation/       # mission_manager, nav2_config
│   └── telemetry/       # kpi_recorder
├── simulation/
│   ├── worlds/           # warehouse_phase0.sdf
│   └── models/           # x500_warehouse, штрихкоды
├── config/               # drone_params.yaml, slam_params.yaml
├── scripts/              # launch_sim.sh, анализ KPI
├── tasks.md              # План задач Phase 0
├── CONTEXT.md            # Полный контекст проекта
└── result.md             # Результаты и вердикты
```

---

## Ключевые документы

| Файл | Описание |
|------|----------|
| [CONTEXT.md](CONTEXT.md) | Полный контекст: установка, архитектура, roadmap |
| [tasks.md](tasks.md) | План задач Phase 0 (A–F) |
| [result.md](result.md) | Результаты фаз и аудиты |
| [errors.md](errors.md) | Зафиксированные ошибки и их решения |
| [.cursor/rules/](.cursor/rules/) | Правила разработки (safety, ROS 2, coding) |

---

## Топики ROS 2

| Топик | Тип | Назначение |
|-------|-----|------------|
| `/drone/perception/lidar/filtered` | PointCloud2 | Отфильтрованный LiDAR |
| `/drone/control/rack_follower/cmd_vel` | Twist | Команды следования вдоль стеллажа |
| `/drone/control/rack_follower/status` | String | OK / DEGRADED / FAILED |
| `/drone/perception/barcode/detections` | BarcodeDetection | Результаты сканирования |
| `/drone/slam/pose` | PoseWithCovarianceStamped | Позиция от SLAM |

---

## Безопасность (Safety Rules)

- Избежание столкновений — через TOF в PX4, **не** через ROS
- Все velocity-команды имеют watchdog 200 мс → при отсутствии команд дрон переходит в hover
- Движение только при валидной локализации
- Порог батареи — динамический: `f(дистанция, скорость, мощность)`, а не статический %
- При конфликте штрихкода и SLAM — СТОП, ожидание оператора
- Любое необработанное исключение в mission logic → hover + alert

---

## Лицензия

Проект для внутренней разработки CORTEXIS.
