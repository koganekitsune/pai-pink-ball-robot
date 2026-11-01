# PAI最終課題：日本語指示でピンクボールを弾くロボット

## 概要

ROS 2 Humble と Gazebo Fortress 上で、CRANE+ V2 ロボットアームが、日本語の指示に応じてピンクボールを探したり、グリッパで弾いたりするデモです。

**処理の流れ**：日本語入力 → 学習済み機械学習モデルによる指示分類 → カメラによるボール検出 → 位置条件の確認 → ロボットアームの動作

## AIの利用

- `ai_command/ai_command_model.py` で、日本語の指示36例を使った教師あり学習を実施します。
- **文字単位TF-IDF（1〜3文字のn-gram）＋ロジスティック回帰**によって、指示を `FLICK`（弾く）・`FIND`（探す）・`WAIT`（待機）の3種類に分類します。
- 学習済みモデルは `ai_command/command_model.joblib` に保存しており、`pink_command.py` が実行時に読み込んで推論します。
- 予測確率の最大値が **0.45未満**の場合はロボット動作を実行しません。明示的な停止・否定表現はモデル推論より優先します。
- 画像のボール認識は**AIモデルではなく**、OpenCVのHSV色抽出と輪郭検出を使ったルールベース処理です。ロボットの関節軌道も事前に定義した固定軌道です。

学習用例文と同じ・類似した指示を主な対象とする小規模モデルであり、LLMのような自由な言語理解や、未知の環境でのロバストな動作は保証しません。模倣学習による関節軌道生成は、今回の完成システムには使用していません。

## ファイル構成

```text
.
├── README.md
├── pink_command.py                   # 日本語の指示受付、AI推論と動作の連携
├── detect_pink_ball_ros.py          # OpenCVによる画像認識・ROS 2トピック配信
├── flick_ball_vision_demo.py        # カメラ検出確認・アーム制御・グリッパ操作
├── crane_plus_with_camera.launch.py # Gazebo、CRANE+ V2、ROS 2起動
├── table_with_camera.sdf            # テーブルと俯瞰カメラを含むワールド
├── pink_ball.sdf                    # ピンクボールのモデル
└── ai_command/
    ├── ai_command_model.py          # 日本語指示分類モデルの学習・単体推論
    └── command_model.joblib         # 学習済みモデル
```

## 実行環境

- Ubuntu 22.04（Dockerコンテナ）
- ROS 2 Humble、Gazebo Fortress（Ignition Gazebo）
- CRANE+ V2用 ROS 2 パッケージ群（`crane_plus_gazebo`、`crane_plus_description`、`crane_plus_control`、`crane_plus_moveit_config` など）
- `ros_gz_bridge`、`ros_gz_sim`、`ros2_control` 関連パッケージ
- Python 3、`scikit-learn`、`joblib`、`opencv-python` 相当のOpenCV（`cv2`）、`numpy`、`rclpy`、`cv_bridge`

既存のROS 2・Gazebo環境を前提としています。Dockerイメージや外部のCRANE+パッケージ本体は、このリポジトリに同梱していません。

## 配置・起動方法

既存のDocker環境で、各ファイルを以下の場所に配置します。これは**現行コード中のパス設定に対応した配置**です。

```text
/home/ubuntu/pai_ws/pink_command.py
/home/ubuntu/pai_ws/detect_pink_ball_ros.py
/home/ubuntu/pai_ws/flick_ball_vision_demo.py
/home/ubuntu/pai_ws/ai_command/ai_command_model.py
/home/ubuntu/pai_ws/ai_command/command_model.joblib
/home/ubuntu/airobot_ws/crane_plus_with_camera.launch.py
/home/ubuntu/airobot_ws/table_with_camera.sdf
/tmp/pink_ball.sdf
```

### 1. シミュレータを起動（ターミナルA）

```bash
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
ros2 launch ~/airobot_ws/crane_plus_with_camera.launch.py
```

### 2. カメラトピックをROS 2へ橋渡し（ターミナルB）

```bash
source /opt/ros/humble/setup.bash
ros2 run ros_gz_bridge parameter_bridge '/camera/image@sensor_msgs/msg/Image[ignition.msgs.Image'
```

### 3. ピンクボールを配置（ターミナルC）

```bash
ign service -s /world/default/create \
  --reqtype ignition.msgs.EntityFactory \
  --reptype ignition.msgs.Boolean \
  --timeout 5000 \
  --req 'sdf_filename: "/tmp/pink_ball.sdf", name: "pink_ball", pose: {position: {x: 0.15, y: 0, z: 1.045}, orientation: {w: 1}}'
```

ボールは重複生成せず、テーブル上の所定位置に1個配置します。

### 4. 画像認識を起動（ターミナルD）

```bash
source /opt/ros/humble/setup.bash
python3 ~/pai_ws/detect_pink_ball_ros.py
```

画像認識が成功すると `/pink_ball/center_px` に画面内の中心座標が配信され、画面に検出結果が表示されます。

### 5. 日本語指示で動作（ターミナルE）

```bash
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
python3 ~/pai_ws/pink_command.py
```

入力例：

```text
ピンクの丸いやつをやっつけろ！
ピンクのボールを探して
何もしないで
```

`FLICK` の場合、カメラが新しく検出したボール中心座標が `x=290〜350 px`、`y=180〜240 px` の範囲内にあることを確認してから、グリッパを使った所定動作を実行します。検出できない場合や範囲外では動作を中止します。

## AIモデルの再学習・単体テスト

```bash
python3 -m pip install --user scikit-learn joblib
python3 ~/pai_ws/ai_command/ai_command_model.py --train
python3 ~/pai_ws/ai_command/ai_command_model.py 'ピンクの丸いやつをやっつけろ！'
```

学習データは `ai_command_model.py` 内に定義されています。`--train` で `command_model.joblib` が生成・上書きされます。

## 実装上の制約

- ボールの色と初期位置、カメラの設置位置、アームの動作軌道は、今回のGazeboワールド向けに調整しています。
- カメラのピクセル座標による許可範囲チェックは、シミュレーション専用の簡易な動作条件です。実機向けの安全機構ではありません。
- 言語分類器の信頼度は少数の訓練例に基づくものであり、未知の日本語に対する精度を保証するものではありません。
- `.joblib` はPythonオブジェクトのシリアライズ形式です。信頼できない第三者が提供したモデルファイルは読み込まないでください。

## 使用ソフトウェアの情報

- [ROS 2 Humble](https://docs.ros.org/en/humble/)
- [CRANE+ 関連パッケージ](https://github.com/rt-net/crane_plus)

`crane_plus_with_camera.launch.py` の既存の著作権・Apache License表記は保持しています。
