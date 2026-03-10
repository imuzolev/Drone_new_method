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

## ERR-006 — `rclpy` теряет context при запуске через `wsl -d ... bash -c`

**Дата:** 2026-03-10
**Фаза:** B.1–B.2 (runtime-проверка)
**Критичность:** MEDIUM

**Симптом:**
CLI-команды и Python-скрипты на `rclpy`, запущенные через агентский вызов `wsl -d Ubuntu-22.04 -u imuzolev bash -c "..."`, вели себя нестабильно:
```text
Failed to create subscription: rcl node's context is invalid, at ./src/rcl/node.c:428
```
или
```text
publisher's context is invalid
!rclpy.ok()
```
Из-за этого `ros2 topic hz` и тестовые Python-subscriber'ы могли показывать ложное отсутствие данных, хотя симуляция и DDS уже работали.

**Причина:**
При запуске через неинтерактивный `bash -c` процессы `rclpy` получают внешние сигналы/завершение родительского контекста. Стандартные signal handlers `rclpy` интерпретируют это как shutdown и рано инвалидируют ROS context. Дополнительно использование `timeout` усиливает эффект, т.к. процесс получает SIGTERM во время spin/shutdown.

**Решение:**
1. Для тестовых Python-нод отключать стандартные обработчики сигналов:
```python
rclpy.init(signal_handler_options=rclpy.SignalHandlerOptions.NO)
```
2. Вместо `rclpy.shutdown()` использовать `rclpy.try_shutdown()` в короткоживущих диагностических скриптах.
3. Для "залипших" состояний после неудачных запусков делать полный `wsl --shutdown`.
4. Для длительных runtime-проверок предпочитать живой интерактивный WSL-терминал.

**Файлы:**
- `scripts/test_px4_sub.py`

**Урок:**
В WSL-автоматизации нельзя слепо доверять поведению `rclpy` под `bash -c` и `timeout`. Если CLI/скрипт говорит "context is invalid", это не доказывает отсутствие данных в ROS graph.

---

## ERR-007 — `ros2 topic echo` без явного QoS даёт ложное впечатление, что данных нет

**Дата:** 2026-03-10
**Фаза:** B.1–B.2 (runtime-проверка)
**Критичность:** MEDIUM

**Симптом:**
После успешного старта симуляции следующие команды выглядели как "пустые":
```bash
ros2 topic echo /clock --once
ros2 topic echo /drone/perception/lidar/raw/points --once
```
При этом `ros2 topic list` и `ros2 topic info -v` показывали активных publisher'ов. Аналогично проверка PX4-топиков через стандартный CLI была ненадёжной.

**Причина:**
QoS профили publisher'ов не совпадали с тем, что неявно использует `ros2 topic echo`:
- `ros_gz_bridge` публикует `/clock` и `/drone/perception/lidar/raw/points` как `RELIABLE`.
- PX4 uXRCE-DDS публикует многие `/fmu/out/*` топики как `BEST_EFFORT` c особыми QoS-настройками.
Без совпадающего QoS подписчик создаётся, но сообщений не получает, что выглядит как "топик пустой".

**Решение:**
Проверять QoS перед диагностикой:
```bash
ros2 topic info /clock -v
ros2 topic info /drone/perception/lidar/raw/points -v
```
Затем вызывать `echo` с явным QoS:
```bash
ros2 topic echo /clock --qos-reliability reliable --once
ros2 topic echo /drone/perception/lidar/raw/points --qos-reliability reliable --once
```
Для PX4-топиков надёжнее использовать короткий `rclpy` subscriber с явно заданным `QoSProfile`, чем полагаться на `ros2 topic echo`.

**Файлы:**
- `scripts/test_px4_sub.py`

**Урок:**
Для Gazebo bridge и PX4 DDS пустой вывод `ros2 topic echo` ещё не означает отсутствие данных. Сначала смотреть `ros2 topic info -v`, потом подбирать совместимый QoS.

---

## ERR-008 — PX4 DDS публикует часть критичных топиков с версионными суффиксами

**Дата:** 2026-03-10
**Фаза:** B.3
**Критичность:** HIGH

**Симптом:**
`px4_bridge_node` и диагностический helper видели сенсорные PX4-топики (`/fmu/out/sensor_combined`,
`/fmu/out/vehicle_attitude`), но не получали статус арминга и локальную позицию по ожидаемым именам:
```bash
ros2 topic info /fmu/out/vehicle_status -v
ros2 topic info /fmu/out/vehicle_local_position -v
```
показывали либо `Publisher count: 0`, либо `Unknown topic`.

Из-за этого `px4_bridge` оставался в `FAILED/DEGRADED`, а helper для `B.3` не мог дождаться
валидного состояния PX4.

**Причина:**
Текущая связка PX4 SITL + `px4_msgs` публикует часть uXRCE-DDS топиков в граф под именами:
- `/fmu/out/vehicle_status_v2`
- `/fmu/out/vehicle_local_position_v1`

но код был написан под старые имена без версионных суффиксов.

**Решение:**
Переподписать runtime-код на фактические имена топиков:
- `px4_bridge_node`: `/fmu/out/vehicle_status_v2`
- `scripts/offboard_takeoff_via_twist_mux.py`: `/fmu/out/vehicle_status_v2`,
  `/fmu/out/vehicle_local_position_v1`

Проверка после фикса:
```bash
ros2 topic info /fmu/out/vehicle_status_v2 -v
ros2 topic info /fmu/out/vehicle_local_position_v1 -v
```
показывает `Publisher count: 1`.

**Файлы:**
- `src/control/px4_bridge/src/px4_bridge_node.cpp`
- `scripts/offboard_takeoff_via_twist_mux.py`

**Урок:**
Для PX4 uXRCE-DDS нельзя предполагать стабильные имена `/fmu/out/*` "на память". Перед интеграцией
нужно сверять фактический graph через `ros2 topic list` и `ros2 topic info -v`.

---

## ERR-009 — PX4 не проходит preflight в `x500_warehouse`, поэтому `B.3` нельзя довести до полёта

**Дата:** 2026-03-10
**Фаза:** B.3
**Критичность:** CRITICAL → **RESOLVED**

**Симптом:**
После исправления DDS-подписок и успешного получения `VehicleStatus`/`VehicleLocalPosition`
safe-takeoff helper всё равно не может перейти к ARM/OFFBOARD:
```text
pre_flight_checks_pass=False
xy_valid=False z_valid=False v_xy_valid=False v_z_valid=False
heading_good_for_control=False
```

Дополнительно логи PX4 содержат:
```text
Preflight Fail: barometer 0 missing
Preflight Fail: ekf2 missing data
Preflight Fail: Found 0 compass (required: 1)
Preflight Fail: No connection to the GCS
```

**Причина:**
Три раздельных проблемы в `warehouse_phase0.sdf`:

**9a) Отсутствие Gazebo system-плагинов для сенсоров:**
Мир `warehouse_phase0.sdf` объявлял `<plugin>` теги явно (Physics, UserCommands,
SceneBroadcaster, Sensors, Imu), что **переопределяло** набор плагинов по умолчанию.
В стандартном PX4-мире `default.sdf` нет ни одного `<plugin>` тега, поэтому Gazebo загружает
все дефолтные системы. В warehouse отсутствовали:
- `gz-sim-magnetometer-system` → магнетометр не публикует данные → "Found 0 compass"
- `gz-sim-air-pressure-system` → барометр не публикует данные → "barometer 0 missing"
- `gz-sim-navsat-system` → GPS не публикует данные → EKF2 не может инициализироваться

**9b) Отсутствие `<magnetic_field>`, `<atmosphere>`, `<spherical_coordinates>`:**
Даже если бы плагины были загружены, без `<magnetic_field>` магнетометр возвращает нули,
без `<atmosphere>` барометр не генерирует корректное давление,
без `<spherical_coordinates>` GPS (navsat) не может вычислить координаты.

**9c) Отсутствие GCS-параметров в airframe:**
`NAV_DLL_ACT=2` (из базового 4001_gz_x500) вызывает failsafe при отсутствии GCS,
а `COM_RCL_EXCEPT` не включал режим OFFBOARD в исключения.

**Решение:**

1. Добавлены в `warehouse_phase0.sdf`:
```xml
<gravity>0 0 -9.8</gravity>
<magnetic_field>6e-06 2.3e-05 -4.2e-05</magnetic_field>
<atmosphere type="adiabatic"/>
<spherical_coordinates>
  <surface_model>EARTH_WGS84</surface_model>
  <world_frame_orientation>ENU</world_frame_orientation>
  <latitude_deg>47.397971057728974</latitude_deg>
  <longitude_deg>8.546163739800146</longitude_deg>
  <elevation>0</elevation>
</spherical_coordinates>
```

2. Добавлены недостающие system-плагины:
```xml
<plugin filename="gz-sim-magnetometer-system" name="gz::sim::systems::Magnetometer"/>
<plugin filename="gz-sim-air-pressure-system" name="gz::sim::systems::AirPressure"/>
<plugin filename="gz-sim-navsat-system" name="gz::sim::systems::NavSat"/>
```

3. Обновлён airframe `4030_gz_x500_warehouse`:
```sh
param set-default NAV_DLL_ACT 0
param set-default COM_RCL_EXCEPT 4
```

4. Мир скопирован в PX4: `~/PX4-Autopilot/Tools/simulation/gz/worlds/warehouse_phase0.sdf`
5. PX4 ROMFS пересобран: `make px4_sitl_default`

**Верификация:**
```text
pre_flight_checks_pass=True
xy_valid=True z_valid=True v_xy_valid=True v_z_valid=True
xy_global=True z_global=True
PX4 log: "home set" → "Ready for takeoff!"
```

**Файлы:**
- `simulation/worlds/warehouse_phase0.sdf`
- `~/PX4-Autopilot/Tools/simulation/gz/worlds/warehouse_phase0.sdf`
- `~/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/airframes/4030_gz_x500_warehouse`

**Урок:**
При создании кастомного Gazebo-мира для PX4 SITL с явным набором `<plugin>` тегов нужно включать
**все** system-плагины, которые требуются сенсорам модели. Если стандартный мир PX4 не объявляет
плагины явно — это значит, что Gazebo загружает все дефолтные. Явное объявление переопределяет
этот набор. Также обязательны `<magnetic_field>`, `<atmosphere>`, `<spherical_coordinates>` —
без них соответствующие сенсоры возвращают нули, и EKF2 не может пройти инициализацию.

---

## ERR-010 — twist_mux требует Twist, а не TwistStamped

**Дата:** 2026-03-10
**Фаза:** B.3
**Критичность:** HIGH

**Симптом:**
Выход `twist_mux` на `/cmd_vel_out` имел тип `geometry_msgs/msg/Twist`, но `rack_follower` и takeoff-скрипт публиковали сообщения с типом `geometry_msgs/msg/TwistStamped`.
Команда `ros2 topic echo /cmd_vel_out` падала с ошибкой `Cannot echo topic '/cmd_vel_out', as it contains more than one type`.

**Причина:**
По умолчанию ROS 2 `twist_mux` настроен на использование `Twist`. Попытка включить `use_stamped: true` в `twist_mux.yaml` привела к ошибке конфигурации, т.к. этот параметр работает только в новых версиях twist_mux или требует другой структуры словаря (в Humble он не поддерживался без пересборки).

**Решение:**
`px4_bridge`, `rack_follower` и `offboard_takeoff_via_twist_mux.py` переведены на использование обычного `geometry_msgs/msg/Twist` вместо `TwistStamped`. Параметр `use_stamped: true` удалён из конфига `twist_mux`.

**Файлы:**
- `src/control/px4_bridge/src/px4_bridge_node.cpp`
- `src/control/rack_follower/src/rack_follower_node.cpp`
- `scripts/offboard_takeoff_via_twist_mux.py`

---

## ERR-011 — LiDAR фильтрует все точки (No valid wall points)

**Дата:** 2026-03-10
**Фаза:** B.3
**Критичность:** HIGH

**Симптом:**
`rack_follower_node` выдавал `[WARN]: No valid wall points — publishing zero velocity`.

**Причина:**
1. Преобразование `TF transform to 'world' failed`. Так как frame `world` не транслировался, фильтрация происходила в frame `sensor`.
2. В `sensor` фрейме Z = 0 означает уровень самого лидара. Пороги Z были: `z_ground_threshold = 0.05` в `lidar_preprocessor` и `filter_z_min = 0.3` в `rack_follower`. Это обрезало все точки ниже лидара и чуть выше его, удаляя вообще все точки стеллажа перед дроном.

**Решение:**
*(Временное)*: Значения порогов Z адаптированы под `sensor` frame (-1.5 и 2.5 м).
*(Финальное, Итерация 2)*: В `px4_bridge_node.cpp` добавлен `tf2_ros::TransformBroadcaster`, публикующий `world` -> `base_link` на основе `/fmu/out/vehicle_odometry`. В `lidar_preprocessor_node.cpp` фрейм облака точек принудительно устанавливается в `base_link` перед трансформацией. Пороги Z в конфигурациях возвращены к значениям для `world` фрейма (0.05 и 0.3 м).

**Файлы:**
- `src/perception/lidar_preprocessor/config/lidar_preprocessor_params.yaml`
- `src/control/rack_follower/config/rack_follower_params.yaml`
- `src/control/px4_bridge/src/px4_bridge_node.cpp`
- `src/perception/lidar_preprocessor/src/lidar_preprocessor_node.cpp`

---

## ERR-012 — Дрон улетает в сторону (ошибка СК в px4_bridge)

**Дата:** 2026-03-10
**Фаза:** B.3
**Критичность:** CRITICAL

**Симптом:**
При запуске `rack_follower` после взлёта дрон бесконтрольно улетал по диагонали или врезался в стену (RMS error > 0.75m), не следуя вдоль стеллажа.

**Причина:**
Неправильный маппинг скоростей из ROS Body (FLU) в PX4 Local (NED) в `px4_bridge`.
Изначально было:
```cpp
msg.velocity[0] = static_cast<float>(vx);     // forward  → north
msg.velocity[1] = static_cast<float>(-vy);    // left     → −east
```
Но в Gazebo дрон стартует, смотря на Восток (+X в мире). Соответственно, его Body Forward (+X) соответствует East (+Y в NED), а Body Left (+Y) соответствует North (+X в NED).

**Решение:**
*(Временное)*: Маппинг осей в `px4_bridge` изменён на `vel_x = vy (North)`, `vel_y = vx (East)`.
*(Финальное, Итерация 2)*: В `px4_bridge_node.cpp` внедрён динамический пересчёт (rotation matrix) скоростей из Body FLU в Local NED с учётом текущего Yaw, полученного из `/fmu/out/vehicle_odometry`. Это позволяет дрону корректно отрабатывать Body velocities независимо от текущего курса.

**Файлы:**
- `src/control/px4_bridge/src/px4_bridge_node.cpp`

---