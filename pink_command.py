#!/usr/bin/env python3
"""Natural-language command demo for the existing CRANE+ Gazebo simulation.

This is a small, deterministic Japanese phrase interpreter, not an LLM.
The original vision-gated robot controller remains unchanged.
"""
import os
import re
import subprocess
import sys
import time

VISION_SCRIPT = os.path.expanduser('~/pai_ws/flick_ball_vision_demo.py')
TOPIC = '/pink_ball/center_px'


def interpret(text):
    # Explicit stop/negation takes precedence over AI predictions.
    s = re.sub(r"\s+", "", text).lower()
    if any(w in s for w in (
        '何もしない', '動かない', '待機', 'ストップ', '停止',
        'やめて', 'やめろ', '触らない', '弾かない', '転がさない',
    )):
        print('AI safety override: WAIT')
        return 'wait'

    import joblib
    model = joblib.load(os.path.expanduser('~/pai_ws/ai_command/command_model.joblib'))
    probabilities = model.predict_proba([text])[0]
    index = int(probabilities.argmax())
    label = str(model.classes_[index]).upper()
    confidence = float(probabilities[index])
    print(f'AI inference: {label} (confidence={confidence:.3f})')
    if confidence < 0.45:
        print('Low confidence: no robot action')
        return 'unknown'
    return {'FLICK': 'flick', 'FIND': 'find', 'WAIT': 'wait'}.get(label, 'unknown')


def find_ball():
    try:
        import rclpy
        from geometry_msgs.msg import PointStamped
    except ImportError as e:
        print(f'ROS 2 import error: {e}')
        return
    rclpy.init()
    node = rclpy.create_node('pink_natural_language_query')
    detections = []
    sub = node.create_subscription(PointStamped, TOPIC,
                                   lambda msg: detections.append((msg.point.x, msg.point.y)), 10)
    print('カメラから最新の検出結果を取得しています（最大5秒）...', flush=True)
    deadline = time.monotonic() + 5.0
    try:
        while not detections and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        if detections:
            x, y = detections[-1]
            print(f'ピンクボールを検出しました: x={x:.1f}, y={y:.1f} px')
        else:
            print('ピンクボールを検出できませんでした。画像認識プログラムを確認してください。')
    finally:
        node.destroy_subscription(sub)
        node.destroy_node()
        rclpy.shutdown()


def main():
    print('日本語指示でロボットを動かすデモ（シミュレーション専用）')
    print('例：ピンクの丸いやつをやっつけろ / ピンクのボールを探して / 何もしないで')
    print('終了するには q を入力してください。')
    while True:
        try:
            utterance = input('\n指示 > ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n終了します。')
            break
        if utterance.lower() in ('q', 'quit', 'exit', '終了'):
            break
        action = interpret(utterance)
        if action == 'wait':
            print('判断: WAIT / 動作は実行しません。')
        elif action == 'find':
            print('判断: FIND / カメラの検出結果だけ確認します。')
            find_ball()
        elif action == 'flick':
            print('判断: FLICK / 既存の画像認識・安全範囲チェック付きプログラムを実行します。')
            print("動作: アームを初期位置に戻し、既存のボールをカメラで認識し、規定範囲内なら弾きます。")
            if not os.path.isfile(VISION_SCRIPT):
                print(f'ファイルが見つかりません: {VISION_SCRIPT}')
                continue
            # Use the environment of the user (ROS 2 should be sourced first).
            try:
                rc = subprocess.run([sys.executable, VISION_SCRIPT], check=False).returncode
                print('動作完了' if rc == 0 else f'動作は中断されました (終了コード {rc})')
            except KeyboardInterrupt:
                print('中断しました。')
        else:
            print('判断できませんでした。ピンクの対象と、実行したい動作を指定してください。')


if __name__ == '__main__':
    main()
