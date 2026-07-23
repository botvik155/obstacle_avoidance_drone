# obstacle_avoidance_drone

Mapless **Nav2 (MPPI) + 2D-lidar** obstacle avoidance for an ArduPilot multirotor,
with two parallel setups:

| Package | Use | Lidar | Clock |
|---|---|---|---|
| `obstacle_avoidance`    | **Simulation** (Gazebo + ArduPilot SITL) | Gazebo lidar → `/lidar/scan` | sim time (`/clock`) |
| `obstacle_avoidance_hw` | **Hardware / OBC** (real LightWare SF45/B) | `lightwarelidar2` → `/lidar/scan` | wall time |

Nav2 runs mapless: `map→base_link` comes from `/mavros/local_position/pose`
(flattened to 2D), both costmaps are rolling windows off `/lidar/scan`, and MPPI's
`/cmd_vel` is bridged to `/mavros/setpoint_velocity` (ENU, altitude held).

## Onboard computer (no Gazebo needed)

The OBC only runs the **`obstacle_avoidance_hw`** path — it does **not** need Gazebo
or ardupilot_gazebo. Install just the common + hardware pieces from
[`INSTALL.md`](INSTALL.md) (skip stages 4–7, which are simulation-only).

```bash
# 1. workspace
mkdir -p ~/obstacle_avoidance_drone/src && cd ~/obstacle_avoidance_drone/src

# 2. this repo
git clone <THIS_REPO_URL> .

# 3. the LightWare driver (third-party, not vendored here)
git clone https://github.com/LightWare-Optoelectronics/lightwarelidar2

# 4. build the C++ driver (our python nodes run from source, no build needed)
cd ~/obstacle_avoidance_drone
source /opt/ros/humble/setup.bash
colcon build --packages-select lightwarelidar2
source install/setup.bash

# 5. serial access for the SF45/B (log out/in after)
sudo usermod -aG dialout $USER
```

### Run (hardware)
```bash
# flight controller must be connected with a POSITION SOURCE (GPS / flow / VIO)
ros2 launch src/obstacle_avoidance_hw/launch/bringup_hw.launch.py   # SF45/B + mavros + tf
# after position fix + takeoff:
ros2 launch src/obstacle_avoidance_hw/launch/nav2_hw.launch.py      # Nav2 MPPI + cmd_vel bridge
rviz2 -d src/obstacle_avoidance_hw/config/nav2_drone.rviz           # send goals with the Nav2 Goal tool
```

> ⚠️ Nav2 and ArduPilot GUIDED both require a position estimate. Without GPS (or
> optical-flow/VIO/mocap) `/mavros/local_position/pose` never publishes, so
> `map→base_link` is absent and nothing navigates. GPS is useless indoors.

## Full setup
See [`INSTALL.md`](INSTALL.md) for the complete from-scratch install (both paths),
with exact download/build commands and a known-good version table.

## Key parameters
- Costmaps / MPPI critics: `src/obstacle_avoidance_hw/config/nav2_params.yaml`
- Standoff distance: `inflation_radius` + `cost_scaling_factor` + `ObstaclesCritic.repulsion_weight`
- Lidar port/baud/FOV: launch args in `bringup_hw.launch.py`
  (`lidar_port:=/dev/ttyACM0`, `lidar_baud:=115200`, `low_angle`/`high_angle`)

## Note on building the Python packages
`obstacle_avoidance*` are `ament_python` packages. With setuptools ≥ 80 `colcon build`
fails (`--editable not recognized`); the launch files therefore run the Python nodes
directly from source, so **building them is optional**. To build anyway:
`pip install "setuptools<80"` first.
