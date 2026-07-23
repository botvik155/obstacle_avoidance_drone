# Obstacle-Avoidance Drone Stack — Full Install From Scratch

End-to-end setup for the Nav2 (MPPI) + lidar obstacle-avoidance stack, covering
both the **simulation** path (Gazebo + ArduPilot SITL) and the **hardware** path
(LightWare SF45/B lidar + real flight controller). Target: a clean **Ubuntu 22.04**
machine.

Legend:  [COMMON] needed for everything · [SIM] simulation only · [HW] hardware only

Run the stages in order. Lines starting with `sudo` need admin rights.

--------------------------------------------------------------------------------
## 0. Prerequisites [COMMON]
--------------------------------------------------------------------------------
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget lsb-release gnupg build-essential python3-pip
```

Set the locale (ROS 2 needs UTF-8):
```bash
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
```

--------------------------------------------------------------------------------
## 1. ROS 2 Humble [COMMON]
--------------------------------------------------------------------------------
```bash
sudo add-apt-repository -y universe

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools
```

Source ROS in every shell:
```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source /opt/ros/humble/setup.bash
```

Build tooling (colcon + rosdep):
```bash
sudo apt install -y python3-colcon-common-extensions python3-rosdep
sudo rosdep init 2>/dev/null || true
rosdep update
```

--------------------------------------------------------------------------------
## 2. Nav2 + RViz [COMMON]
--------------------------------------------------------------------------------
```bash
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-nav2-mppi-controller \
  ros-humble-nav2-rviz-plugins \
  ros-humble-rviz2 \
  ros-humble-tf2-ros \
  ros-humble-tf2-geometry-msgs
```
(`navigation2` pulls controller/planner/behaviors/bt-navigator/waypoint-follower/
lifecycle-manager/costmap-2d/navfn; the mppi-controller line is explicit insurance.)

--------------------------------------------------------------------------------
## 3. MAVROS (+ GeographicLib datasets) [COMMON]
--------------------------------------------------------------------------------
```bash
sudo apt install -y ros-humble-mavros ros-humble-mavros-extras ros-humble-mavros-msgs

# REQUIRED one-time: geoid/gravity/magnetic datasets (MAVROS won't start cleanly without them)
sudo /opt/ros/humble/lib/mavros/install_geographiclib_datasets.sh
```

--------------------------------------------------------------------------------
## 4. Gazebo↔ROS bridge [SIM]
--------------------------------------------------------------------------------
Gazebo Sim 8 (Harmonic) pairing for Humble:
```bash
sudo apt install -y ros-humble-ros-gzharmonic
```
This provides `ros_gz_bridge` (used to bridge `/clock` and `/lidar/scan`).

--------------------------------------------------------------------------------
## 5. Gazebo Sim 8 "Harmonic" [SIM]
--------------------------------------------------------------------------------
```bash
sudo curl https://packages.osrfoundation.org/gazebo.gpg \
  --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt update
sudo apt install -y gz-harmonic
```

--------------------------------------------------------------------------------
## 6. ardupilot_gazebo plugin [SIM]
--------------------------------------------------------------------------------
```bash
sudo apt install -y libgz-sim8-dev rapidjson-dev

cd ~
git clone https://github.com/ArduPilot/ardupilot_gazebo
cd ardupilot_gazebo
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
make -j$(nproc)

# Environment (append to ~/.bashrc)
cat >> ~/.bashrc <<'EOF'
export GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/ardupilot_gazebo/build:$GZ_SIM_SYSTEM_PLUGIN_PATH
export GZ_SIM_RESOURCE_PATH=$HOME/ardupilot_gazebo/models:$HOME/ardupilot_gazebo/worlds:$GZ_SIM_RESOURCE_PATH
EOF
source ~/.bashrc
```

--------------------------------------------------------------------------------
## 7. ArduPilot SITL + MAVProxy [SIM]
--------------------------------------------------------------------------------
```bash
cd ~
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

./waf configure --board sitl
./waf copter

# add autotest (sim_vehicle.py) to PATH
echo 'export PATH=$PATH:$HOME/ardupilot/Tools/autotest' >> ~/.bashrc
source ~/.bashrc
```
MAVProxy/pymavlink are installed by the prereqs script. If missing:
```bash
pip3 install --user MAVProxy pymavlink
```

--------------------------------------------------------------------------------
## 8. LightWare SF45/B driver [HW]
--------------------------------------------------------------------------------
Cloned into the workspace src (built in stage 10):
```bash
mkdir -p ~/obstacle_avoidance_drone/src
cd ~/obstacle_avoidance_drone/src
git clone https://github.com/LightWare-Optoelectronics/lightwarelidar2
```
Serial access for the USB sensor (log out/in afterwards):
```bash
sudo usermod -aG dialout $USER
```
(Optional) LightWare Studio for sensor config — download the .deb from lightware.co.za.

--------------------------------------------------------------------------------
## 9. This project's packages [COMMON]
--------------------------------------------------------------------------------
Place `obstacle_avoidance` (sim) and `obstacle_avoidance_hw` (hardware) under
`~/obstacle_avoidance_drone/src/`. If you're cloning your own repo:
```bash
cd ~/obstacle_avoidance_drone/src
# git clone <your-repo-url> .        # or copy the two package folders here
```
Layout expected:
```
~/obstacle_avoidance_drone/
  src/
    lightwarelidar2/          # from stage 8
    obstacle_avoidance/       # sim package
    obstacle_avoidance_hw/    # hardware package
```

Python deps for the live nodes are just rclpy/geometry_msgs/tf2 (already from ROS).
No numpy/opencv/torch needed for the current stack.

--------------------------------------------------------------------------------
## 10. Build the workspace [COMMON]
--------------------------------------------------------------------------------
```bash
cd ~/obstacle_avoidance_drone
source /opt/ros/humble/setup.bash

# resolve any declared package deps
rosdep install --from-paths src --ignore-src -r -y

# lightwarelidar2 is C++ and builds cleanly
colcon build --packages-select lightwarelidar2
```

⚠️ **setuptools caveat:** Ubuntu/pip may ship setuptools >= 80, which removed the
commands colcon uses to build **ament_python** packages (you'll see
`error: option --editable not recognized`). The launch files run our Python nodes
directly from source, so you can skip building them. If you *do* want to
`colcon build` `obstacle_avoidance*`:
```bash
pip3 install "setuptools<80"
colcon build
```

Source the overlay in every shell:
```bash
echo "source ~/obstacle_avoidance_drone/install/setup.bash" >> ~/.bashrc
source ~/obstacle_avoidance_drone/install/setup.bash
```

--------------------------------------------------------------------------------
## 11. Verify
--------------------------------------------------------------------------------
```bash
# ROS + Nav2 MPPI
ros2 pkg prefix nav2_mppi_controller && echo "nav2 OK"
# MAVROS
ros2 pkg prefix mavros && echo "mavros OK"
# Sim bridge
ros2 pkg prefix ros_gz_bridge && echo "ros_gz OK"
# Gazebo
gz sim --version
# ArduPilot SITL launcher
which sim_vehicle.py
# Lidar driver
ros2 pkg prefix lightwarelidar2 && echo "sf45b driver OK"
```

--------------------------------------------------------------------------------
## 12. Run
--------------------------------------------------------------------------------
### Simulation path
```bash
# terminal 1: Gazebo world
gz sim -v4 -r runway.sdf
# terminal 2: ArduPilot SITL (gazebo model)
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console
# terminal 3: infra (clock+scan bridges, mavros, tf)
ros2 launch src/obstacle_avoidance/launch/bringup.launch.py
# arm -> GUIDED -> takeoff, then terminal 4: Nav2
ros2 launch src/obstacle_avoidance/launch/nav2_mppi.launch.py
# terminal 5: RViz + Nav2 Goal tool
rviz2 -d src/obstacle_avoidance/config/nav2_drone.rviz
```

### Hardware path (real SF45/B, SITL or real FCU)
```bash
# terminal 1: flight controller — SITL:
sim_vehicle.py -v ArduCopter --console --map
#              — or a real FCU over UDP/serial (needs a GPS/position source!)
# terminal 2: infra (real lidar + mavros + tf, wall-time, NO gz/clock)
ros2 launch src/obstacle_avoidance_hw/launch/bringup_hw.launch.py
# after a position fix + takeoff, terminal 3: Nav2
ros2 launch src/obstacle_avoidance_hw/launch/nav2_hw.launch.py
# terminal 4: RViz
rviz2 -d src/obstacle_avoidance_hw/config/nav2_drone.rviz
```

⚠️ **Hardware needs a position estimate.** Without GPS (or optical-flow/VIO/mocap),
`/mavros/local_position/pose` never publishes, so `map->base_link` is absent and
Nav2 cannot run — and ArduPilot GUIDED velocity control won't work either. GPS is
useless indoors: use optical-flow + rangefinder or VIO there.

--------------------------------------------------------------------------------
## Version reference (known-good, as installed)
--------------------------------------------------------------------------------
| Component            | Version        |
|----------------------|----------------|
| Ubuntu               | 22.04.5 LTS    |
| ROS 2                | Humble         |
| Python               | 3.10.12        |
| Gazebo Sim           | 8.11.0 (Harmonic) |
| nav2 (mppi/bringup)  | 1.1.20         |
| mavros / extras      | 2.14.0         |
| ros_gz_bridge        | 0.244.12       |
| rviz2                | 11.2.26        |
| lightwarelidar2      | source (main)  |
