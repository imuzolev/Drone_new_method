# DRONE NEW METHOD — Журнал ошибок и решений

> База знаний проекта: каждая встреченная ошибка, причина, решение.
> **Перед поиском нового решения — сначала проверь этот файл.**
> Формат: ERR-NNN → симптом → причина → решение → файлы затронуты.

---

## ERR-001 — Airframe 4030: PX4_SIM_MODEL пустой → спавнится не та модель

**Дата:** 2026-03-09
**Фаза:** A.8
**Критичность:** CRITICAL

**Симптом:**
При запуске `make px4_sitl gz_x500_warehouse` PX4 спавнил стандартный x500 (без LiDAR и камеры) вместо x500_warehouse. Топики `/drone/perception/lidar/raw` и `/drone/camera/image_raw` не появлялись.

**Причина:**
В файле airframe 4030 была строка:
```sh
PX4_SIM_MODEL=
```
Это обнуляло переменную. Затем при sourcing базового airframe 4001_gz_x500 срабатывало:
```sh
PX4_SIM_MODEL=${PX4_SIM_MODEL:=x500}
```
Конструкция `:=` устанавливает значение только если переменная пуста — и т.к. она была обнулена, ставился `x500`.

Дополнительно путь sourcing был `\etc/...` вместо `${R}etc/...` — без переменной `${R}` (PX4 ROMFS root).

**Решение:**
Исправлен файл `ROMFS/px4fmu_common/init.d-posix/airframes/4030_gz_x500_warehouse`:
```sh
#!/bin/sh
#
# @name Gazebo x500 warehouse
#
# @type Quadrotor
#

PX4_SIM_MODEL=${PX4_SIM_MODEL:=x500_warehouse}

. ${R}etc/init.d-posix/airframes/4001_gz_x500
```

После исправления — `make px4_sitl_default` для пересборки ROMFS.

**Файлы:**
- `~/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/airframes/4030_gz_x500_warehouse`
- `~/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/airframes/4030_gz_x500_warehouse` (генерируется)

**Урок:**
При создании нового PX4 airframe всегда использовать `${PX4_SIM_MODEL:=имя_модели}` (не пустое присвоение) и `${R}` для путей ROMFS. Проверять содержимое build-артефакта после сборки.

---

## ERR-002 — Модель x500_warehouse: двойная вложенность директории

**Дата:** 2026-03-09
**Фаза:** A.8
**Критичность:** CRITICAL

**Симптом:**
Gazebo не находит model.sdf для x500_warehouse. Модель не загружается даже при правильном `PX4_SIM_MODEL`.

**Причина:**
Файлы модели были скопированы в `models/x500_warehouse/x500_warehouse/model.sdf` (двойная вложенность), тогда как PX4/Gazebo ожидают `models/x500_warehouse/model.sdf`.

Справочная структура (рабочая модель x500):
```
models/x500/
├── model.config
├── model.sdf
└── thumbnails/
```

Фактическая (сломанная):
```
models/x500_warehouse/
└── x500_warehouse/
    ├── model.config
    └── model.sdf
```

**Решение:**
```bash
cd ~/PX4-Autopilot/Tools/simulation/gz/models/x500_warehouse
mv x500_warehouse/model.config .
mv x500_warehouse/model.sdf .
rmdir x500_warehouse
```

**Файлы:**
- `~/PX4-Autopilot/Tools/simulation/gz/models/x500_warehouse/model.config`
- `~/PX4-Autopilot/Tools/simulation/gz/models/x500_warehouse/model.sdf`

**Урок:**
При копировании моделей в PX4 всегда проверять структуру через `ls -laR` и сравнивать с эталонной моделью (например, x500). Формат: `models/<model_name>/model.sdf` — ровно один уровень.

---

## ERR-003 — WSL2 clock skew: предупреждения при colcon build

**Дата:** 2026-03-09
**Фаза:** A.7
**Критичность:** LOW (cosmetic)

**Симптом:**
```
gmake[2]: Warning: File '...compiler_depend.make' has modification time X.XXX s in the future
gmake[2]: warning: Clock skew detected. Your build may be incomplete.
```

**Причина:**
Рассинхронизация часов между Windows хостом и WSL2. Файловая система NTFS (через `/mnt/c/`) имеет timestamps от Windows, а WSL2 kernel может отставать.

**Решение:**
Безвредно для сборки — результат идентичен. Если мешает:
```bash
# Синхронизировать время WSL2 с хостом:
sudo hwclock -s
# Или:
sudo ntpdate time.windows.com
```

**Файлы:** Нет конкретных — затрагивает любую сборку через `/mnt/c/`.

**Урок:**
Игнорировать clock skew warnings при сборке на WSL2 + NTFS. Если нужна чистая сборка — можно перенести workspace в нативную ext4 файловую систему WSL (`~/workspace/` вместо `/mnt/c/`).

---

## ERR-004 — PX4 SITL гибнет от SIGHUP + отсутствует ros_gz_bridge

**Дата:** 2026-03-10
**Фаза:** A.9 (runtime-проверка)
**Критичность:** CRITICAL

**Симптом:**
1. `launch_sim.sh` запускает PX4 и Gazebo, но через ~20с PX4 умирает с "ninja: build stopped: interrupted by user" / "make: *** Hangup". Gazebo GUI остаётся, но дрон не управляется.
2. `/drone/perception/lidar/raw` не виден в ROS 2 (`ros2 topic echo` — "does not appear to be published yet"), хотя LiDAR работает на стороне Gazebo Transport.

**Причина:**
Две раздельных проблемы:

**4a) SIGHUP для PX4:** `make px4_sitl gz_x500_warehouse &` запускается в фоне в bash-скрипте. При запуске через `wsl -- bash script.sh` PX4 наследует группу процессов скрипта. Когда скрипт продолжает выполнение (sleep/source/wait), `make` получает SIGHUP и убивает PX4. Gazebo выживает, т.к. является отдельным процессом.

**4b) Отсутствие ros_gz_bridge:** Сенсоры x500_warehouse (LiDAR, камера) публикуют на **Gazebo Transport** (собственный протокол), а не на ROS 2 DDS. Пакет `ros-humble-ros-gzharmonic-bridge` не был установлен. Без него ROS 2 не видит данные сенсоров.

**Решение:**

1. **SIGHUP:** Обернуть фоновые процессы в `setsid`, чтобы создать новую сессию:
```sh
setsid make px4_sitl gz_x500_warehouse &
setsid MicroXRCEAgent udp4 -p 8888 &
```

2. **ros_gz_bridge:** Установить и запустить:
```sh
sudo apt install ros-humble-ros-gzharmonic-bridge
ros2 run ros_gz_bridge parameter_bridge \
    /drone/perception/lidar/raw/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked \
    /drone/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image \
    /drone/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock &
```

3. **set -u:** ROS 2 setup.bash использует неинициализированные переменные — `set -u` вызывает crash. Заменить `set -euo pipefail` на `set -eo pipefail` и точечно `set +u` / `set -u` вокруг `source`.

**Файлы:**
- `scripts/launch_sim.sh` (переписан)

**Урок:**
- Фоновые процессы в bash-скриптах через WSL обязательно оборачивать в `setsid`.
- Gazebo Harmonic использует собственный Transport — для ROS 2 **всегда** нужен `ros_gz_bridge`.
- `set -u` несовместим с `source /opt/ros/*/setup.bash` — отключать через `set +u` перед source.

---

## ERR-005 — PX4 server already running for instance 0

**Дата:** 2026-03-10
**Фаза:** A.9 (runtime)
**Критичность:** HIGH

**Симптом:**
При запуске `launch_sim.sh` PX4 падает с:
```
INFO  [px4] PX4 server already running for instance 0
FAILED: src/modules/simulation/gz_bridge/CMakeFiles/gz_x500_warehouse
ninja: build stopped: subcommand failed.
```
Остальные процессы (DDS Agent, ros_gz_bridge) стартуют, но бесполезны без PX4.

**Причина:**
Cleanup-паттерн `pkill -f "px4.*warehouse"` не матчит основной процесс PX4, т.к. его cmdline — `/home/.../build/px4_sitl_default/bin/px4` без слова "warehouse". Стейлый PX4 с предыдущего запуска занимает instance 0, новый экземпляр отказывается стартовать.

**Решение:**
Расширить cleanup в `launch_sim.sh`:
```sh
pkill -9 -f "px4_sitl_default/bin/px4" 2>/dev/null || true
pkill -9 -f "PX4_SIM_MODEL=" 2>/dev/null || true
pkill -9 -f "gz sim" 2>/dev/null || true
pkill -9 -f "ruby.*gz" 2>/dev/null || true
pkill -9 -f MicroXRCEAgent 2>/dev/null || true
pkill -9 -f parameter_bridge 2>/dev/null || true
rm -f /tmp/px4_sitl* /tmp/px4-* 2>/dev/null || true
sleep 3
```

**Файлы:**
- `scripts/launch_sim.sh`

**Урок:**
Cleanup в launch-скриптах должен использовать максимально точные паттерны для каждого типа процесса. SIGKILL (-9) надёжнее SIGTERM для зависших SITL-процессов. Удалять lockfiles PX4 из `/tmp`.

---
