# Phase B — Что не получилось и что осталось нерешённым

> Документация проблем, встреченных при реализации Фазы B.
> Формат: номер, симптом, причина, статус.

---

## ERR-B-01 — PX4 падает после получения VehicleCommand ARM

**Подэтап:** B.3 (попытка вооружить дрон для теста PD-контроллера)
**Критичность:** HIGH

**Симптом:**
Запущен `arm_and_takeoff.py`, отправлен `VEHICLE_CMD_COMPONENT_ARM_DISARM`. Через ~1с после
отправки команды процесс `px4_sitl_default/bin/px4` исчез из таблицы процессов. Gazebo
продолжил работать, Micro-XRCE-DDS-Agent остался жив, но `/fmu/out/*` топики перестали
публиковать данные.

**Причина:**
Точная причина не установлена. Предположения:
1. PX4 SITL не прошёл prearm-проверки и завершился с ненулевым кодом (отсутствие GPS-fix,
   EKF не инициализирован — дрон находится на земле в точке (-9, 0, 0.2)).
2. Конфликт: `px4_bridge_node` уже публикует `OffboardControlMode` на
   `/fmu/in/offboard_control_mode` (50 Гц), `arm_and_takeoff.py` начинает
   публиковать туда же — возможно, дублирование сообщений вызывает внутренний assert PX4.
3. Версия px4_msgs (2.0.1) может требовать другой формат поля `VehicleCommand`.

**Решение (не реализовано):**
- Убрать px4_bridge из запуска перед arm-тестом (он дублирует offboard-публикацию).
- Добавить задержку для инициализации EKF (PX4 нужно ~5–10с видеть Gazebo, прежде чем
  примет ARM в OFFBOARD).
- Использовать QGroundControl или PX4 shell (`commander arm`) вместо VehicleCommand через ROS 2.

**Файлы:**
- `scripts/arm_and_takeoff.py` — содержит скрипт арминга (написан, не протестирован до конца)

---

## ERR-B-02 — `ros2 topic hz` даёт "rcl node's context is invalid"

**Подэтап:** B.3, B.4, B.5
**Критичность:** MEDIUM

**Симптом:**
```
Failed to create subscription: rcl node's context is invalid, at ./src/rcl/node.c:428
```
Команда `ros2 topic hz /fmu/out/vehicle_status` выдаёт ошибку, хотя
`ros2 topic list` топик видит, а `ros2 topic echo` не выдаёт ошибки (просто пустой вывод).

**Причина:**
После краша `arm_and_takeoff.py` с исключением `rclpy.executors.ExternalShutdownException`
в системе оставались некорректно завершённые rclpy-процессы. Перезапуск демона
(`ros2 daemon stop/start`) проблему не устранил.
Вероятно — конфликт DDS-участников в shared memory или некорректный shutdown rclpy-контекста.

**Решение (не реализовано):**
- После каждого аварийного завершения rclpy-скриптов — полная перезагрузка WSL (`wsl --shutdown`).
- Использовать RCUTILS_LOGGING_BUFFERED_STREAM=0 чтобы не оставлять незакрытые handles.

---

## ERR-B-03 — `arm_and_takeoff.py` использовал несуществующий метод `create_wall_timer`

**Подэтап:** B.3
**Критичность:** LOW (исправлено)

**Симптом:**
```
AttributeError: 'ArmAndTakeoff' object has no attribute 'create_wall_timer'.
Did you mean: 'create_timer'?
```

**Причина:**
В C++ rclcpp это `create_wall_timer`, в Python rclpy — просто `create_timer`.

**Решение:** Исправлено — заменён вызов.

**Файлы:** `scripts/arm_and_takeoff.py`

---

## ERR-B-04 — PX4 SITL не перезапускается через `nohup` или `setsid` из `wsl -d ... bash -c`

**Подэтап:** B.3 (после краша PX4, попытка рестарта)
**Критичность:** HIGH

**Симптом:**
После краша PX4 все попытки перезапустить `make px4_sitl gz_x500_warehouse` через
`nohup ... &` или `setsid ... &` внутри `wsl -d Ubuntu-22.04 -u imuzolev bash -c "..."` не дали
результата — процесс не запускался, log-файл не создавался.

**Причина:**
Команда `make px4_sitl gz_x500_warehouse` — сложный многошаговый процесс (cmake + ninja + px4 binary
+ Gazebo). При использовании `nohup ... > logfile &` в контексте `bash -c`, если вызывающая
оболочка завершается раньше, чем дочерние процессы успевают отсоединиться, они могут получить
SIGHUP. Несмотря на `nohup`/`setsid`, у cmake/ninja нет обработчиков SIGHUP.

Первоначальный запуск PX4 работал только в интерактивном терминале пользователя (`wsl -- bash scripts/launch_sim.sh` в отдельном окне терминала).

**Решение (не реализовано):**
Симуляцию нужно запускать в отдельном, живом WSL-терминале пользователя, а не
из агентских команд. Для B.3–B.5 необходимо:
1. Открыть WSL-терминал вручную.
2. Запустить `bash scripts/launch_sim.sh` (интерактивно).
3. Только после этого запускать тесты через агента.

---

## Итог: что выполнено / не выполнено

| Подэтап | Код написан | Собирается | Базово протестирован | Полный тест |
|---------|------------|-----------|---------------------|-------------|
| B.1 lidar_preprocessor | ✅ | ✅ | ✅ (filtered ~9 Hz, 1196 pts) | ✅ |
| B.2 loop2.launch.py | ✅ | ✅ | ✅ (4 ноды стартуют) | ⏳ требует живой сим |
| B.3 PD tuning | — | — | ⏳ preflight FIXED (ERR-009), ожидает runtime | ❌ |
| B.4 Watchdog test | — | — | ⏳ зависит от B.3 | ❌ |
| B.5 twist_mux prio | — | — | ⏳ зависит от B.3 | ❌ |

**Ключевой блокер для B.3–B.5 (RESOLVED):**
PX4 preflight fail из-за отсутствующих Gazebo system-плагинов и world properties
в `warehouse_phase0.sdf` — исправлено (см. ERR-009 в errors.md).

**Оставшийся нюанс:**
Запуск PX4 SITL предпочтительнее в живом интерактивном WSL-терминале.
`bash scripts/launch_sim.sh` → затем B.3–B.5.
