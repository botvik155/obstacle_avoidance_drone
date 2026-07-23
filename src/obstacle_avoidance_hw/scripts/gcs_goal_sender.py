#!/usr/bin/env python3
"""
GCS goal sender (runs on the Ground Control Station).

Standalone — needs ONLY Python 3 stdlib, no ROS. Sends a Nav2 goal to the OBC's
goal_socket_bridge over UDP and prints the status replies it sends back.

Examples:
    # go to x=5, y=2 (metres, map frame), facing yaw=0, OBC at 192.168.1.50
    ./gcs_goal_sender.py 5 2 0 --host 192.168.1.50

    # yaw defaults to 0
    ./gcs_goal_sender.py 10 -3 --host 192.168.1.50

    # cancel the current goal
    ./gcs_goal_sender.py --cancel --host 192.168.1.50

x, y are metres in the map frame (relative to the EKF origin / home where the
drone initialised); yaw is radians. Default port 9200 matches the bridge.
"""

import argparse
import json
import socket
import sys

TERMINAL = {'reached', 'aborted', 'rejected', 'canceled'}


def main():
    ap = argparse.ArgumentParser(
        description='Send a Nav2 goal to the OBC over UDP.')
    ap.add_argument('x', type=float, nargs='?', help='goal x (m, map frame)')
    ap.add_argument('y', type=float, nargs='?', help='goal y (m, map frame)')
    ap.add_argument('yaw', type=float, nargs='?', default=0.0,
                    help='goal yaw (rad, default 0)')
    ap.add_argument('--host', default='127.0.0.1',
                    help="OBC IP address (default 127.0.0.1)")
    ap.add_argument('--port', type=int, default=9200,
                    help='OBC bridge UDP port (default 9200)')
    ap.add_argument('--frame', default='map', help="goal frame (default 'map')")
    ap.add_argument('--cancel', action='store_true',
                    help='cancel the current goal instead of sending one')
    ap.add_argument('--timeout', type=float, default=120.0,
                    help='seconds to wait for status replies (default 120)')
    args = ap.parse_args()

    if args.cancel:
        msg = {'cmd': 'cancel'}
    else:
        if args.x is None or args.y is None:
            ap.error('provide x and y (or use --cancel)')
        msg = {'cmd': 'goal', 'x': args.x, 'y': args.y,
               'yaw': args.yaw, 'frame': args.frame}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    sock.sendto(json.dumps(msg).encode(), (args.host, args.port))
    print(f"sent -> {args.host}:{args.port}: {msg}")

    # listen for status replies until a terminal status or timeout
    try:
        while True:
            data, _ = sock.recvfrom(2048)
            try:
                d = json.loads(data.decode())
            except ValueError:
                continue
            status = d.get('status', '?')
            print(f"  [{status}] {d.get('msg', '')}")
            if status in TERMINAL:
                return 0 if status == 'reached' else 1
    except socket.timeout:
        print('(timeout waiting for status — is the OBC bridge running / reachable?)')
        return 2


if __name__ == '__main__':
    sys.exit(main())
