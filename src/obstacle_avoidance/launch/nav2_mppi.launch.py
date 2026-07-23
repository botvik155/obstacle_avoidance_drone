#!/usr/bin/env python3
"""
Mapless Nav2 (MPPI controller) bring-up for ArduPilot SITL + Gazebo lidar.

No map_server / AMCL: the map->base_link transform is supplied by the
mavros_tf_bridge node (tf_publisher.py) from /mavros/local_position/pose,
and both costmaps run as rolling windows off /lidar/scan.

Nodes started here:
  - controller_server  (nav2_mppi_controller / MPPIController)
  - planner_server     (NavFn A*)
  - behavior_server    (recoveries)
  - bt_navigator
  - waypoint_follower
  - lifecycle_manager  (autostart)
  - cmd_vel_to_mavros  (/cmd_vel body -> /mavros/setpoint_velocity ENU)

Assumes mavros, the ros_gz lidar bridge, and mavros_tf_bridge are already
running (they are part of your existing SITL/Gazebo launch).

Runs entirely from source (absolute paths), so it does NOT require the
obstacle_avoidance package to be colcon-installed.
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PKG_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_PARAMS = os.path.join(PKG_DIR, 'config', 'nav2_params.yaml')
BRIDGE_PY = os.path.join(PKG_DIR, 'obstacle_avoidance', 'cmd_vel_to_mavros.py')


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    lifecycle_nodes = [
        'planner_server',
        'controller_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
    ]

    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=DEFAULT_PARAMS),
        DeclareLaunchArgument('use_sim_time', default_value='true'),

        Node(
            package='nav2_controller', executable='controller_server',
            name='controller_server', output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
        ),
        Node(
            package='nav2_planner', executable='planner_server',
            name='planner_server', output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
        ),
        Node(
            package='nav2_behaviors', executable='behavior_server',
            name='behavior_server', output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
        ),
        Node(
            package='nav2_bt_navigator', executable='bt_navigator',
            name='bt_navigator', output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
        ),
        Node(
            package='nav2_waypoint_follower', executable='waypoint_follower',
            name='waypoint_follower', output='screen',
            parameters=[params_file, {'use_sim_time': use_sim_time}],
        ),
        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='lifecycle_manager_navigation', output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': True,
                'node_names': lifecycle_nodes,
            }],
        ),

        # Nav2 body-frame /cmd_vel -> MAVROS ENU velocity setpoint.
        # Run directly from source so no colcon install is required.
        ExecuteProcess(
            cmd=['python3', BRIDGE_PY],
            output='screen',
        ),
    ])
