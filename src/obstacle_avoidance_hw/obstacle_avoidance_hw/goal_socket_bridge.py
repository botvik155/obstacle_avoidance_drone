#!/usr/bin/env python3
"""
Goal socket bridge (runs on the OBC).

Receives navigation goals from a Ground Control Station over a UDP socket and
forwards them to Nav2 via the NavigateToPose action. Sends a small JSON status
reply back to whoever sent the goal (accepted / rejected / reached / aborted /
canceled), so the GCS knows what happened.

Run this SEPARATELY from the Nav2 launch, e.g.:
    python3 obstacle_avoidance_hw/goal_socket_bridge.py \
        --ros-args -p bind_port:=9200

Wire protocol (JSON, UDP):
    GCS -> OBC : {"cmd": "goal", "x": 5.0, "y": 2.0, "yaw": 0.0, "frame": "map"}
                 {"cmd": "cancel"}
    OBC -> GCS : {"status": "accepted"|"rejected"|"reached"|"aborted"|
                            "canceled"|"canceling"|"feedback", "msg": "..."}

x, y are metres in the goal frame (default "map" = relative to the EKF origin /
home where the drone initialised); yaw is radians.
"""

import json
import math
import socket

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class GoalSocketBridge(Node):

    def __init__(self):
        super().__init__('goal_socket_bridge')

        self.declare_parameter('bind_host', '0.0.0.0')
        self.declare_parameter('bind_port', 9200)
        self.declare_parameter('goal_frame', 'map')
        # Throttle feedback status replies to the GCS (seconds); 0 disables.
        self.declare_parameter('feedback_period', 1.0)

        host = self.get_parameter('bind_host').value
        port = int(self.get_parameter('bind_port').value)
        self.goal_frame = self.get_parameter('goal_frame').value
        self.feedback_period = float(self.get_parameter('feedback_period').value)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        self._goal_handle = None
        self._last_fb_t = 0.0

        # 20 Hz socket drain
        self.create_timer(0.05, self._poll_socket)

        self.get_logger().info(
            f"goal_socket_bridge listening on {host}:{port} "
            f"-> navigate_to_pose (frame '{self.goal_frame}')")

    # ---- socket helpers ----
    def _reply(self, addr, status, msg=''):
        if addr is None:
            return
        try:
            self.sock.sendto(
                json.dumps({'status': status, 'msg': msg}).encode(), addr)
        except OSError:
            pass

    def _poll_socket(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except (BlockingIOError, OSError):
                break

            try:
                d = json.loads(data.decode())
            except (ValueError, UnicodeDecodeError):
                self._reply(addr, 'rejected', 'malformed JSON')
                continue

            cmd = d.get('cmd', 'goal')
            if cmd == 'cancel':
                self._cancel(addr)
            elif cmd == 'goal':
                self._handle_goal(d, addr)
            else:
                self._reply(addr, 'rejected', f'unknown cmd: {cmd}')

    # ---- goal handling ----
    def _handle_goal(self, d, addr):
        try:
            x = float(d['x'])
            y = float(d['y'])
            yaw = float(d.get('yaw', 0.0))
        except (KeyError, TypeError, ValueError):
            self._reply(addr, 'rejected', 'goal needs numeric x, y [, yaw]')
            return

        frame = d.get('frame', self.goal_frame)

        if not self.client.server_is_ready():
            self.get_logger().warn('navigate_to_pose server not ready — is Nav2 up?')
            self._reply(addr, 'rejected', 'Nav2 action server not ready')
            return

        ps = PoseStamped()
        ps.header.frame_id = frame
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose.position.x = x
        ps.pose.position.y = y
        ps.pose.orientation.z = math.sin(yaw / 2.0)
        ps.pose.orientation.w = math.cos(yaw / 2.0)

        goal = NavigateToPose.Goal()
        goal.pose = ps

        self.get_logger().info(
            f"GOAL from {addr[0]}:{addr[1]} -> "
            f"x={x:.2f} y={y:.2f} yaw={yaw:.2f} frame={frame}")

        send_future = self.client.send_goal_async(
            goal, feedback_callback=lambda fb: self._on_feedback(fb, addr))
        send_future.add_done_callback(lambda f: self._on_goal_response(f, addr))

    def _on_goal_response(self, future, addr):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Nav2 rejected the goal')
            self._reply(addr, 'rejected', 'Nav2 rejected the goal')
            return
        self._goal_handle = goal_handle
        self._reply(addr, 'accepted', 'goal accepted')
        goal_handle.get_result_async().add_done_callback(
            lambda f: self._on_result(f, addr))

    def _on_result(self, future, addr):
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('goal REACHED')
            self._reply(addr, 'reached', 'goal reached')
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info('goal canceled')
            self._reply(addr, 'canceled', 'goal canceled')
        else:
            self.get_logger().warn(f'goal ended (status={status})')
            self._reply(addr, 'aborted', f'navigation ended, status={status}')
        self._goal_handle = None

    def _on_feedback(self, feedback_msg, addr):
        if self.feedback_period <= 0.0:
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        if (now - self._last_fb_t) < self.feedback_period:
            return
        self._last_fb_t = now
        dist = feedback_msg.feedback.distance_remaining
        self._reply(addr, 'feedback', f'distance_remaining={dist:.2f}m')

    def _cancel(self, addr):
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self.get_logger().info('cancel requested')
            self._reply(addr, 'canceling', 'cancel requested')
        else:
            self._reply(addr, 'rejected', 'no active goal to cancel')


def main(args=None):
    rclpy.init(args=args)
    node = GoalSocketBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
