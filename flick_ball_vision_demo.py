#!/usr/bin/env python3
"""CRANE+ Gazebo Fortress: reset scene, then perform a gripper flick.

Run inside the ROS 2 Humble / Gazebo Docker container. Requires Gazebo's
/world/default/create and /world/default/remove services and a model SDF at
/tmp/pink_ball.sdf.
"""
import argparse
import subprocess
import sys
import time

import rclpy
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from trajectory_msgs.msg import JointTrajectoryPoint

WORLD = 'default'
BALL_NAME = 'pink_ball'
BALL_SDF = '/tmp/pink_ball.sdf'
ARM_ACTION = '/crane_plus_arm_controller/follow_joint_trajectory'
HAND_ACTION = '/crane_plus_gripper_controller/follow_joint_trajectory'
ARM_JOINTS = [f'crane_plus_joint{i}' for i in range(1, 5)]
HAND_JOINTS = ['crane_plus_joint_hand']
INITIAL_ARM = [0.0, 0.0, 0.0, 0.0]
FLICK_ARM = [0.35, 0.0, -2.20, 0.0]
HAND_CLOSED = [0.1745]
HAND_OPEN = [-0.5236]


def ign_service(service, request_type, request):
    cmd = [
        'ign', 'service', '-s', f'/world/{WORLD}/{service}',
        '--reqtype', f'ignition.msgs.{request_type}',
        '--reptype', 'ignition.msgs.Boolean',
        '--timeout', '5000', '--req', request,
    ]
    response = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    combined = (response.stdout + '\n' + response.stderr).strip()
    if response.returncode != 0 or 'data: true' not in response.stdout:
        raise RuntimeError(f'Gazebo {service} failed: {combined}')
    print(f'Gazebo {service}: OK', flush=True)


def send_trajectory(node, action, names, positions, seconds):
    client = ActionClient(node, FollowJointTrajectory, action)
    if not client.wait_for_server(timeout_sec=10):
        raise RuntimeError(f'Controller not available: {action}')
    goal = FollowJointTrajectory.Goal()
    goal.trajectory.joint_names = names
    point = JointTrajectoryPoint()
    point.positions = positions
    total_ns = round(seconds * 1_000_000_000)
    point.time_from_start = Duration(sec=total_ns // 1_000_000_000,
                                     nanosec=total_ns % 1_000_000_000)
    goal.trajectory.points.append(point)
    future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future, timeout_sec=15)
    if not future.done() or future.result() is None or not future.result().accepted:
        raise RuntimeError(f'Goal rejected or timed out: {action}')
    handle = future.result()
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=60)
    if not result_future.done() or result_future.result() is None:
        raise RuntimeError(f'Execution timed out: {action}')
    result = result_future.result()
    if result.status != GoalStatus.STATUS_SUCCEEDED or result.result.error_code != 0:
        raise RuntimeError(f'Trajectory failed: {action}; status={result.status}; error={result.result.error_code}; {result.result.error_string}')
    print(f'Controller OK: {action}', flush=True)


def main():
    parser = argparse.ArgumentParser(description='Reset CRANE+ scene and flick the pink ball')
    parser.add_argument('--settle-seconds', type=float, default=2.0,
                        help='Wait after ball creation (wall clock seconds)')
    args = parser.parse_args()
    if args.settle_seconds < 0:
        parser.error('--settle-seconds must be >= 0')
    rclpy.init()
    node = rclpy.create_node('flick_ball_sequence')
    try:
        print('1/7 Move arm to initial joint angles (5 s)', flush=True)
        send_trajectory(node, ARM_ACTION, ARM_JOINTS, INITIAL_ARM, 5.0)

        print('Using existing pink ball', flush=True)

        print(f'4/7 Wait {args.settle_seconds:g} seconds for ball to settle', flush=True)
        time.sleep(args.settle_seconds)

        # VISION_GATE_BEGIN: require fresh camera detection before moving to the ball.
        from geometry_msgs.msg import PointStamped
        centers = []
        sub = node.create_subscription(
            PointStamped, '/pink_ball/center_px',
            lambda msg: centers.append((msg.point.x, msg.point.y)), 10)
        print('Vision check: waiting for fresh ball coordinates (up to 10 s)', flush=True)
        deadline = time.monotonic() + 10.0
        try:
            while not centers and time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.2)
        finally:
            node.destroy_subscription(sub)
        if not centers:
            raise RuntimeError('No ball detected; arm will not approach the ball')
        x, y = centers[-1]
        print(f'Vision check: ball at ({x:.1f}, {y:.1f}) px', flush=True)
        if not (290 <= x <= 350 and 180 <= y <= 240):
            raise RuntimeError('Ball outside safe image region; no flick')
        print('Vision check PASSED: ball inside allowed region', flush=True)
        # VISION_GATE_END

        print('5/7 Close gripper (1 s)', flush=True)
        send_trajectory(node, HAND_ACTION, HAND_JOINTS, HAND_CLOSED, 1.0)

        print('6/7 Move closed gripper into flick position (5 s)', flush=True)
        send_trajectory(node, ARM_ACTION, ARM_JOINTS, FLICK_ARM, 5.0)

        print('7/7 Open gripper to flick the ball (0.5 s)', flush=True)
        send_trajectory(node, HAND_ACTION, HAND_JOINTS, HAND_OPEN, 0.5)

        print('Sequence completed successfully.', flush=True)
        return 0
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError, KeyboardInterrupt) as exc:
        print(f'STOPPED: {exc}', file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
