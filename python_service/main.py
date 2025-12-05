#!/usr/bin/env python3
"""
PhantomHand - 手势控制系统
主入口文件

用法:
    python main.py              # 启动 WebSocket 服务器
    python main.py --debug      # 启动调试预览窗口
    python main.py --test       # 运行测试模式
"""

import argparse
import asyncio
import sys
import cv2

from config.settings import Config, default_config


def run_debug_mode(config: Config):
    """
    调试模式：显示预览窗口，不启动 WebSocket 服务器
    用于测试手势识别效果
    """
    from core.capture import CameraCapture
    from core.detector import HandDetector
    from core.gesture import GestureClassifier
    from core.state_machine import GestureStateMachine, GestureEvent, GestureState
    from core.action import ActionExecutor

    print("=" * 50)
    print("PhantomHand 调试模式")
    print("=" * 50)
    print("按 'q' 退出")
    print("按 'a' 激活/停用控制")
    print("=" * 50)

    # 初始化组件
    camera = CameraCapture(
        device_id=config.camera.device_id,
        width=config.camera.width,
        height=config.camera.height,
        fps=config.camera.fps,
        mirror=config.camera.mirror
    )

    detector = HandDetector()
    classifier = GestureClassifier()
    state_machine = GestureStateMachine()
    action_executor = ActionExecutor()

    # 事件回调
    def on_gesture_event(event: GestureEvent):
        print(f"[EVENT] {event.event_type}: {event.gesture} "
              f"(hand={event.hand_id}, duration={event.hold_duration:.0f}ms)")

        # 获取手部位置
        hand_pos = None
        if hasattr(on_gesture_event, 'last_detection'):
            for hand in on_gesture_event.last_detection.hands:
                if hand.hand_id == event.hand_id:
                    hand_pos = (hand.landmarks[8][0], hand.landmarks[8][1])
                    break

        # 执行动作
        action_executor.execute_gesture(
            gesture=event.gesture,
            event_type=event.event_type,
            hand_pos=hand_pos,
            meta=event.meta
        )

    state_machine.register_callback(on_gesture_event)

    # 启动摄像头
    if not camera.start():
        print("[ERROR] 无法启动摄像头")
        return

    try:
        for frame in camera.read_generator():
            # 检测
            result = detector.detect(
                frame.image,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp
            )
            on_gesture_event.last_detection = result

            # 绘制骨骼
            output = detector.draw_landmarks(frame.image, result)

            # 处理每只手
            for hand in result.hands:
                # 分类
                gesture_proba = classifier.classify(hand)

                # 状态机更新
                state_machine.update(
                    hand.hand_id,
                    gesture_proba,
                    frame.timestamp
                )

                # 检测滑动
                slide = classifier.detect_slide(hand)
                if slide:
                    direction, distance = slide
                    action_executor.execute_slide(direction, distance)
                    cv2.putText(output, f"SLIDE: {direction}", (50, 150),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

                # 显示手势信息
                state = state_machine.get_state(hand.hand_id)
                wrist_pos = hand.landmarks_pixel[0]

                if state:
                    # 手势名称
                    gesture_text = f"{state.gesture}"
                    if state.state == GestureState.HELD:
                        gesture_text += f" ({state.hold_duration:.0f}ms)"

                    # 颜色根据状态
                    if state.state == GestureState.HELD:
                        color = (0, 255, 0)  # 绿色 - 保持中
                    elif state.state == GestureState.ENTERING:
                        color = (0, 255, 255)  # 黄色 - 进入中
                    else:
                        color = (128, 128, 128)  # 灰色 - 空闲

                    cv2.putText(output, gesture_text, (wrist_pos[0], wrist_pos[1] + 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                    # 显示概率
                    proba_text = f"{gesture_proba.dominant_gesture}: {gesture_proba.dominant_score:.2f}"
                    cv2.putText(output, proba_text, (wrist_pos[0], wrist_pos[1] + 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            # 显示状态信息
            info_lines = [
                f"FPS: {camera.actual_fps:.1f}",
                f"Hands: {result.num_hands}",
                f"Inference: {result.inference_time_ms:.1f}ms",
                f"Active: {'YES' if action_executor.is_active() else 'NO'}"
            ]

            y_offset = 30
            for line in info_lines:
                color = (0, 255, 0) if "Active: YES" in line else (255, 255, 255)
                cv2.putText(output, line, (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 25

            # 显示控制提示
            cv2.putText(output, "Press 'a' to activate | 'q' to quit",
                       (10, output.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            cv2.imshow("PhantomHand Debug", output)

            # 键盘控制
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('a'):
                # 切换激活状态
                new_state = not action_executor.is_active()
                action_executor.set_active(new_state)
                print(f"[DEBUG] 控制{'激活' if new_state else '停用'}")

    finally:
        camera.stop()
        detector.close()
        cv2.destroyAllWindows()
        print("[DEBUG] 调试模式结束")


def run_server_mode(config: Config):
    """
    服务器模式：启动 WebSocket 服务器
    """
    from server import PhantomHandServer

    print("=" * 50)
    print("PhantomHand 服务器模式")
    print("=" * 50)

    server = PhantomHandServer(config)

    try:
        asyncio.run(server.run(
            host=config.server.host,
            port=config.server.port
        ))
    except KeyboardInterrupt:
        print("\n[SERVER] 收到中断信号")


def run_test_mode():
    """
    测试模式：运行各模块的单元测试
    """
    print("=" * 50)
    print("PhantomHand 测试模式")
    print("=" * 50)

    # 测试摄像头
    print("\n[TEST] 测试摄像头模块...")
    from core.capture import CameraCapture

    camera = CameraCapture()
    if camera.start():
        frame = camera.read(timeout=2.0)
        if frame:
            print(f"  ✓ 摄像头正常: {frame.width}x{frame.height}")
        else:
            print("  ✗ 无法读取帧")
        camera.stop()
    else:
        print("  ✗ 无法启动摄像头")

    # 测试检测器
    print("\n[TEST] 测试检测器模块...")
    from core.detector import HandDetector
    import numpy as np

    detector = HandDetector()
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(test_image)
    print(f"  ✓ 检测器正常: inference_time={result.inference_time_ms:.1f}ms")
    detector.close()

    # 测试分类器
    print("\n[TEST] 测试分类器模块...")
    from core.gesture import GestureClassifier

    classifier = GestureClassifier()
    print("  ✓ 分类器初始化成功")

    # 测试状态机
    print("\n[TEST] 测试状态机模块...")
    from core.state_machine import GestureStateMachine
    from core.gesture import GestureProba

    sm = GestureStateMachine()
    test_proba = GestureProba.from_dict({"open": 0.9, "fist": 0.1})
    event = sm.update("test_hand", test_proba, 0)
    print("  ✓ 状态机正常")

    # 测试动作执行器
    print("\n[TEST] 测试动作执行器模块...")
    from core.action import ActionExecutor
    import platform

    executor = ActionExecutor()
    print(f"  ✓ 动作执行器正常 (平台: {platform.system()})")
    print(f"    屏幕尺寸: {executor.config.screen_width}x{executor.config.screen_height}")

    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PhantomHand - 手势控制系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python main.py                  启动 WebSocket 服务器
    python main.py --debug          启动调试预览窗口
    python main.py --test           运行测试
    python main.py --port 9000      指定端口号
        """
    )

    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="启动调试模式（预览窗口）"
    )

    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="运行测试模式"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="服务器主机地址 (默认: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="服务器端口 (默认: 8765)"
    )

    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=0,
        help="摄像头设备 ID (默认: 0)"
    )

    args = parser.parse_args()

    # 创建配置
    config = Config()
    config.server.host = args.host
    config.server.port = args.port
    config.camera.device_id = args.camera

    # 根据参数选择模式
    if args.test:
        run_test_mode()
    elif args.debug:
        run_debug_mode(config)
    else:
        run_server_mode(config)


if __name__ == "__main__":
    main()
