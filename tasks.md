# DRONE NEW METHOD — ПЛАН ЗАДАЧ Phase 0 MVP

> **Инструкция для AI-агента:**
> Это мастер-план проекта. Задачи выполняются строго последовательно сверху вниз.
> - ~~Зачёркнутые~~ задачи с `[x]` — выполнены, не трогать.
> - `[ ]` — ещё не сделаны. Бери **первую незачёркнутую** задачу и выполняй.
> - После выполнения задачи — отметь `[x]` и зачеркни текст.
> - Контекст проекта: `CONTEXT.md`. Правила: `.cursor/rules/*.mdc`.
> - Корень проекта в WSL: `/mnt/c/CORTEXIS/Drone_new_method`
> - Корень проекта в Windows: `c:\CORTEXIS\Drone_new_method`
> - **Проверка** в конце каждой задачи — обязательный критерий приёмки.

---

## Текущий статус модулей

| Модуль | Задача | Код | Собран | Протестирован | Заметки |
|--------|--------|-----|--------|---------------|---------|
| lidar_preprocessor | **B.1** ✅ | готов | ✅ | ✅ ~9Hz, 1196pts | TF2 world-frame фильтр добавлен |
| drone_bringup (loop2.launch.py) | **B.2** ✅ | готов | ✅ | ✅ 4 ноды | use_sim_time пропагация через SetParameter |
| rack_follower (C++) | B.3 | готов | нет | нет | ADJUSTING loop замкнут — проверить при тюнинге |
| px4_bridge (C++) | B.3, B.4 | готов | нет | нет | — |
| twist_mux_config (YAML + launch) | B.5 | готов | нет | нет | — |
| barcode_scanner + scan_policy_fsm | C.3–C.5 | готов | нет | нет | зависимость от SLAM убрана |
| SDF мир (warehouse_phase0.sdf) | C.2 | готов | — | нет | — |
| PNG штрихкоды в SDF | C.1–C.2 | готов | — | нет | — |
| Модель дрона x500_warehouse | A.8 ✅ | готов | — | ✅ | LiDAR+cam топики активны |
| fast_lio2_wrapper | D.1 | скелет | нет | нет | — |
| nav2_config | D.2 | скелет | нет | нет | — |
| kpi_recorder | D.4 | скелет | нет | нет | — |
| apriltag_detector | D.1+ | скелет | нет | нет | — |
| mission_manager | E.1 | скелет | нет | нет | — |

---

## ФАЗА A: Инфраструктура

- [x] ~~**A.0** — Создать структуру проекта: папки src/, config/, simulation/, scripts/, tests/, .cursor/rules/~~
- [x] ~~**A.0.1** — Написать CONTEXT.md с полным описанием архитектуры, правил, roadmap~~
- [x] ~~**A.0.2** — Написать .cursor/rules/general.mdc, ros2_conventions.mdc, safety_rules.mdc~~
- [x] ~~**A.0.3** — Создать warehouse_phase0.sdf (мир склада: стеллажи, штрихкоды-заглушки, освещение)~~
- [x] ~~**A.0.4** — Написать rack_follower_node (C++): PD-контроллер, LiDAR wall-following, watchdog~~
- [x] ~~**A.0.5** — Написать barcode_scanner_node (C++) + scan_policy_fsm (Python) + slot_kpi~~
- [x] ~~**A.0.6** — Написать twist_mux_config: YAML приоритеты (100/50/30/10) + launch файл~~
- [x] ~~**A.0.7** — Написать px4_bridge_node (C++): cmd_vel → TrajectorySetpoint, watchdog 200мс, clamp, NED~~
- [x] ~~**A.0.8** — Написать launch_sim.sh, config/drone_params.yaml, slam_params.yaml, nav2_params.yaml~~
- [x] ~~**A.0.9** — Создать скелеты пакетов: lidar_preprocessor, apriltag_detector, fast_lio2_wrapper, mission_manager, nav2_config, kpi_recorder~~

- [x] ~~**A.1** — Настройка WSL2 + базовые зависимости~~
  - ~~Убедиться что WSL2 Ubuntu 22.04 работает~~
  - ~~`sudo apt install build-essential cmake python3-pip python3-venv`~~
  - ~~**Проверка:** `wsl -l -v` показывает Ubuntu-22.04 Version 2~~

- [x] ~~**A.2** — Установка ROS 2 Humble~~
  - ~~Добавить ключ и репозиторий, установить ros-humble-desktop~~
  - ~~`echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc`~~
  - ~~**Проверка:** `ros2 topic list` работает без ошибок~~

- [x] ~~**A.3** — Установка Gazebo Harmonic~~
  - ~~`sudo apt install gz-harmonic`~~
  - ~~**Проверка:** `gz sim --version` выводит версию~~

- [x] ~~**A.4** — Установка PX4 SITL~~
  - ~~`git clone https://github.com/PX4/PX4-Autopilot.git --recursive`~~
  - ~~`bash ./Tools/setup/ubuntu.sh && make px4_sitl gz_x500`~~
  - ~~**Проверка:** PX4 собран, бинарник `px4` + airframe `gz_x500` существуют~~

- [x] ~~**A.5** — Установка Micro-XRCE-DDS Agent~~
  - ~~Собрать из исходников (см. CONTEXT.md шаг 6)~~
  - ~~**Проверка:** `MicroXRCEAgent` установлен, запускается~~

- [x] ~~**A.6** — Установка дополнительных ROS 2 пакетов~~
  - ~~`sudo apt install ros-humble-twist-mux ros-humble-rmw-cyclonedds-cpp`~~
  - ~~Клонировать px4_msgs и px4_ros_com в `src/`~~
  - ~~`echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc`~~
  - ~~**Проверка:** `ros2 pkg list | grep twist_mux` → twist_mux, twist_mux_msgs~~

- [x] ~~**A.7** — Первая сборка workspace~~
  - ~~`cd /mnt/c/CORTEXIS/Drone_new_method && colcon build --symlink-install`~~
  - ~~Исправить все ошибки компиляции (rack_follower const fix, kpi_recorder __init__.py, config dirs)~~
  - ~~**Проверка:** 12 пакетов собрались за 5 мин 15 сек, 0 ошибок~~

- [x] ~~**A.8** — Модель дрона x500 с сенсорами в SDF~~
  - ~~Создана модель x500_warehouse: x500 + 3D LiDAR (360x16, 10Hz) + RGB камера (1280x720, 15fps)~~
  - ~~Airframe 4030_gz_x500_warehouse в PX4, PX4 пересобран~~
  - ~~Заглушка дрона убрана из warehouse_phase0.sdf, мир скопирован в PX4/worlds~~
  - ~~launch_sim.sh обновлён: PX4_GZ_WORLD=warehouse_phase0, spawn pose (-9,0,0.2)~~
  - ~~**Проверка:** модель и airframe готовы, топики: /drone/perception/lidar/raw, /drone/camera/image_raw~~

- [x] ~~**A.9** — Проверочный запуск полного стека~~
  - ~~PX4 SITL (airframe 4030) + Gazebo Harmonic с миром warehouse_phase0~~
  - ~~MicroXRCEAgent udp4 -p 8888 — сессия установлена~~
  - ~~ros2 topic list → все `/fmu/in/*` и `/fmu/out/*` топики видны через DDS~~
  - ~~**Проверка:** модель x500_0 спавнена на (-9,0,0.2), DDS коннект OK, ~80 PX4 топиков~~

---

## ФАЗА B: Контур 2 — Rack Follower в симуляции

- [x] ~~**B.1** — Реализовать lidar_preprocessor~~
  - ~~Заполнить скелет `src/perception/lidar_preprocessor/`~~
  - ~~Нода: подписка на raw PointCloud2, фильтрация (ground removal + range crop + height band)~~
  - ~~Публикация на `/drone/perception/lidar/filtered` (PointCloud2)~~
  - ~~Config YAML с параметрами фильтров, launch файл~~
  - ~~**Проверка:** `ros2 topic echo /drone/perception/lidar/filtered --no-arr` показывает отфильтрованные данные~~ ✅ filtered ~9 Hz, 1196 pts

- [x] ~~**B.2** — Единый launch файл для Loop 2~~
  - ~~Создать launch файл запускающий: lidar_preprocessor + rack_follower + twist_mux + px4_bridge~~
  - ~~**Проверка:** все 4 ноды стартуют, `ros2 node list` показывает их, статусы публикуются~~ ✅ 4 ноды, 3 status топика + /diagnostics

- [ ] **B.3** — Тюнинг PD-контроллера rack_follower
  - Запустить в Gazebo, наблюдать lateral_error через `ros2 topic echo`
  - Подобрать Kp, Kd, base_speed экспериментально
  - Записать rosbag: `ros2 bag record /drone/control/rack_follower/wall_distance`
  - **Проверка:** lateral_error_rms < 0.10м на пролёте 18м

- [ ] **B.4** — Тест watchdog (safety_rules.mdc RULE 2)
  - Убить rack_follower во время полёта (`ros2 lifecycle set ... shutdown` или kill)
  - **Проверка:** px4_bridge переходит в hover (нулевые скорости), дрон зависает, не падает

- [ ] **B.5** — Тест twist_mux приоритетов
  - Одновременно опубликовать cmd_vel от rack_follower (pri 30) и safety (pri 100)
  - **Проверка:** на `/cmd_vel_out` проходят только команды от safety (приоритет 100)

---

## ФАЗА C: Считывание штрихкодов

- [ ] **C.1** — Сгенерировать PNG штрихкоды
  - Написать скрипт `scripts/generate_barcodes.py`: 48 PNG (EAN-13 или QR, уникальные значения)
  - Сохранить в `simulation/models/barcodes/textures/`
  - **Проверка:** 48 файлов PNG существуют, каждый содержит уникальный код

- [ ] **C.2** — Подключить PNG текстуры к SDF
  - Заменить белые заглушки `bcL_*` и `bcR_*` на модели с текстурами из C.1
  - **Проверка:** в Gazebo визуально видны штрихкоды на стеллажах

- [ ] **C.3** — Собрать ZXing-C++ и интегрировать
  - Установить zxing-cpp: `sudo apt install libzxing-dev` или собрать из git
  - Пересобрать barcode_scanner с `HAS_ZXING` flag
  - **Проверка:** нода стартует, лог показывает «ZXing ENABLED»

- [ ] **C.4** — Проверить pipeline камера → ZXing → detections
  - Зависнуть дрон напротив штрихкода вручную (через `ros2 topic pub` на cmd_vel)
  - **Проверка:** `ros2 topic echo /drone/perception/barcode/detections` показывает barcode_value

- [ ] **C.5** — Интеграция scan_policy_fsm с полётом
  - Запустить rack_follower + barcode_scanner + scan_policy_fsm одновременно
  - **Проверка:** FSM переходит APPROACH → SCANNING → (HOVER_SCAN при плохом чтении) → DONE

- [ ] **C.6** — Оценка качества считывания
  - Полный пролёт через проход, подсчитать считанные коды
  - Если < 5 из 24 — настроить: exposure камеры, LED подсветку в SDF, скорость дрона
  - **Проверка:** ≥10 из 24 слотов считаны (левая сторона)

---

## ФАЗА D: SLAM + Навигация

- [ ] **D.1** — Настроить FAST-LIO2
  - Заполнить `src/slam/fast_lio2_wrapper/`: launch, конфиг, привязка к LiDAR топику
  - Подключить IMU топик из PX4
  - **Проверка:** `ros2 topic echo /drone/slam/pose` — позиция обновляется при движении дрона

- [ ] **D.2** — Настроить Nav2 для Transit
  - Заполнить `src/navigation/nav2_config/`: параметры costmap, planner, controller
  - Создать статическую карту или использовать SLAM-карту
  - **Проверка:** дрон по Nav2 долетает от дока (X=-9.5) до точки входа в проход

- [ ] **D.3** — Handover Nav2 → RackFollower
  - Реализовать aisle_entry_controller (в rack_follower или mission_manager)
  - Логика: отменить Nav2 action → снизить скорость → активировать RackFollower → ждать stable
  - **Проверка:** дрон плавно переходит от Nav2 к wall-following без рывка

- [ ] **D.4** — Реализовать kpi_recorder_node
  - Заполнить `src/telemetry/kpi_recorder/`: подписка на SlotKPI данные, запись CSV
  - Публикация агрегированных метрик на `/drone/telemetry/kpi`
  - **Проверка:** после прогона CSV файл содержит по строке на каждый слот

- [ ] **D.5** — Полный transit + scan цикл
  - Nav2 → Entry Zone → RackFollower → сканирование → конец прохода
  - **Проверка:** kpi_recorder записывает результаты, дрон доезжает до конца прохода

---

## ФАЗА E: End-to-End миссия

- [ ] **E.1** — BehaviorTree миссии
  - Заполнить `src/navigation/mission_manager/`: BT XML файл + leaf nodes (C++)
  - Дерево: TakeOff → TransitToAisle → EnterAisle → ScanAisle → ReturnToDock → Land
  - **Проверка:** BT загружается, Groot2 показывает дерево, дрон выполняет полный цикл

- [ ] **E.2** — Fail-safe: потеря одометрии
  - BT fallback: IsLidarHealthy? → ReduceVelocity → ScanForBarcode → WallFollowReturn
  - **Проверка:** отключить LiDAR плагин в Gazebo → дрон останавливается / снижает скорость

- [ ] **E.3** — Fail-safe: проход заблокирован
  - BT fallback: IsPathClear(3м)? → HoverInPlace(30с) → MarkAisleBlocked → ReturnToDock
  - **Проверка:** добавить препятствие в SDF → дрон ожидает, затем возвращается

- [ ] **E.4** — Fail-safe: критический разряд батареи
  - Реализовать battery_budget_node в px4_bridge (динамический порог)
  - BT: Battery% < compute_return_threshold()? → EmergencyReturn
  - **Проверка:** симулировать низкий заряд → дрон прерывает миссию и возвращается

- [ ] **E.5** — Fail-safe: штрихкод не читается
  - Уже реализовано в scan_policy_fsm (HOVER_SCAN → ADJUSTING → MANUAL_REVIEW)
  - Интегрировать с BT: ScanQuality check → FSM обрабатывает → BT продолжает
  - **Проверка:** заклеить один штрихкод в SDF → FSM помечает MANUAL_REVIEW, миссия продолжается

- [ ] **E.6** — 3 полных прогона без крашей
  - Запуск полного цикла: dock → transit → вход → сканирование → возврат → посадка
  - **Проверка:** все 3 раза дрон возвращается на dock, KPI записан

---

## ФАЗА F: Измерение и Go/No-Go

- [ ] **F.1** — 10 прогонов с записью KPI
  - Написать скрипт автоматизации: запуск → ожидание DONE → сбор CSV → рестарт
  - Сохранить rosbag каждого прогона в `rosbags/`
  - **Проверка:** 10 CSV файлов + 10 rosbag записей

- [ ] **F.2** — Анализ KPI
  - Написать `scripts/analysis/compute_kpi.py`
  - Метрики: success_rate, avg_attempts_per_slot, reads_per_meter, total_time
  - Вывод: таблица + графики
  - **Проверка:** скрипт выводит success_rate числом

- [ ] **F.3** — Документация failure modes
  - Для каждого отказа из 10 прогонов: описание, причина, частота, план исправления
  - Сохранить в `docs/failure_modes.md`
  - **Проверка:** файл существует с минимум 3 описанными failure modes

- [ ] **F.4** — Go/No-Go решение
  - success_rate > 0.80 → начать Phase 1 (Hardware-in-Loop)
  - success_rate ≤ 0.80 → определить узкое место через KPI, вернуться к соответствующей фазе
  - **Проверка:** решение задокументировано в `docs/phase0_report.md`

---

## Переход Phase 0 → Phase 1 (Hardware-in-Loop)

Условия перехода (все должны быть выполнены):
- [ ] Phase 0c go-критерий достигнут (success_rate ≥ 0.80)
- [ ] Все 6 safety rules проверены в симуляции
- [ ] Документированы failure modes (docs/failure_modes.md)
- [ ] Выбран companion computer (минимум Jetson Orin Nano 8GB, не Jetson Nano)
- [ ] LiDAR noise plugin включён и протестирован

---

## Как работать с этим файлом

1. Открой в Cursor, найди **первую задачу с `[ ]`** — это твой следующий шаг.
2. Скажи агенту: *«Выполни задачу A.7 из tasks.md»* (или просто *«следующая задача»*).
3. После выполнения агент должен **отметить задачу как выполненную**: `[x]` + зачеркнуть текст.
4. Если задача требует ручных действий (установка ПО) — выполни сам, затем попроси агента отметить.
