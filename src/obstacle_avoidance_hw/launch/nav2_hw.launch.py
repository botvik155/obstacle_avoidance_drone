#!/usr/bin/env python3
"""
Nav2 (MPPI) bring-up for the REAL-lidar setup (obstacle_avoidance_hw).

Identical wiring to the sim nav2 launch, but on WALL time: use_sim_time:=false
everywhere (there is no /clock without Gazebo). Consumes /lidar/scan from the
LightWare sf45b driver (see bringup_hw.launch.py) and drives ArduPilot SITL via
the cmd_vel -> /mavros/setpoint_velocity bridge.

Run bringup_hw.launch.py first; start this once the drone is armed/airborne.
Runs entirely from source (no colcon install of this package required).
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PARAMS = os.path.join(PKG_DIR, 'config', 'nav2_params.yaml')
BRIDGE_PY = os.path.join(PKG_DIR, 'obstacle_avoidance_hw', 'cmd_vel_to_mavros.py')


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
        # Real hardware -> wall time.
        DeclareLaunchArgument('use_sim_time', default_value='false'),

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
        ExecuteProcess(
            cmd=['python3', BRIDGE_PY],
            output='screen',
        ),
    ])
