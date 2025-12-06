"""
WebSocket 服务模块
提供与前端的实时通信接口
"""

import asyncio
import json
import time
import threading
import socketserver
from typing import Set, Optional, Dict, Any
from dataclasses import dataclass, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import websockets
from websockets.server import WebSocketServerProtocol
import cv2
import numpy as np

from core.capture import CameraCapture, Frame
from core.detector import HandDetector, DetectionResult
from core.gesture import GestureClassifier, GestureProba
from core.state_machine import GestureStateMachine, GestureEvent
from core.action import ActionExecutor
from config.settings import Config, default_config


# Global reference for MJPEG stream
_current_frame: Optional[np.ndarray] = None
_frame_lock = threading.Lock()


def set_current_frame(frame: np.ndarray):
    """Set current frame for MJPEG streaming"""
    global _current_frame
    with _frame_lock:
        _current_frame = frame.copy()


def get_current_frame() -> Optional[np.ndarray]:
    """Get current frame for MJPEG streaming"""
    global _current_frame
    with _frame_lock:
        return _current_frame.copy() if _current_frame is not None else None


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server to handle multiple clients"""
    daemon_threads = True
    allow_reuse_address = True


class MJPEGHandler(BaseHTTPRequestHandler):
    """MJPEG stream HTTP handler"""

    def log_message(self, format, *args):
        # Suppress default logging
        pass

    def do_GET(self):
        if self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            try:
                while True:
                    frame = get_current_frame()
                    if frame is not None:
                        # Encode frame as JPEG
                        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        if ret:
                            self.wfile.write(b'--frame\r\n')
                            self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                            self.wfile.write(jpeg.tobytes())
                            self.wfile.write(b'\r\n')
                            self.wfile.flush()
                    time.sleep(0.033)  # ~30 FPS
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()


def run_mjpeg_server(host: str, port: int):
    """Run MJPEG HTTP server in a separate thread"""
    server = ThreadingHTTPServer((host, port), MJPEGHandler)
    print(f"[MJPEG] Stream available at http://{host}:{port}/stream")
    server.serve_forever()


@dataclass
class WebSocketMessage:
    """WebSocket 消息结构"""
    type: str
    timestamp: float
    data: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        data = json.loads(json_str)
        return cls(**data)


class PhantomHandServer:
    """
    PhantomHand WebSocket 服务器
    整合摄像头采集、手势识别和动作执行
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or default_config

        # 初始化组件
        self.camera: Optional[CameraCapture] = None
        self.detector: Optional[HandDetector] = None
        self.classifier: Optional[GestureClassifier] = None
        self.state_machine: Optional[GestureStateMachine] = None
        self.action_executor: Optional[ActionExecutor] = None

        # WebSocket 连接
        self._clients: Set[WebSocketServerProtocol] = set()

        # 运行状态
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None

        # 统计信息
        self._frame_count = 0
        self._start_time = 0.0

    async def start(self):
        """启动服务"""
        print("[SERVER] 正在初始化组件...")

        # 初始化摄像头
        self.camera = CameraCapture(
            device_id=self.config.camera.device_id,
            width=self.config.camera.width,
            height=self.config.camera.height,
            fps=self.config.camera.fps,
            mirror=self.config.camera.mirror
        )

        if not self.camera.start():
            raise RuntimeError("无法启动摄像头")

        # 初始化检测器
        self.detector = HandDetector(
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )

        # 初始化分类器
        self.classifier = GestureClassifier(
            finger_extended_angle=self.config.gesture.finger_extended_angle,
            finger_bent_angle=self.config.gesture.finger_bent_angle,
            pinch_distance_ratio=self.config.gesture.pinch_distance_ratio,
            fist_tip_wrist_ratio=self.config.gesture.fist_tip_wrist_ratio,
            open_spread_ratio=self.config.gesture.open_spread_ratio
        )

        # 初始化状态机
        self.state_machine = GestureStateMachine(
            p_high=self.config.state_machine.p_high,
            p_hold=self.config.state_machine.p_hold,
            p_low=self.config.state_machine.p_low,
            t_enter=self.config.state_machine.t_enter,
            t_exit=self.config.state_machine.t_exit,
            t_cooldown=self.config.state_machine.t_cooldown
        )

        # 注册手势事件回调
        self.state_machine.register_callback(self._on_gesture_event)

        # 初始化动作执行器
        self.action_executor = ActionExecutor()

        self._running = True
        self._start_time = time.time()

        print("[SERVER] 组件初始化完成")

    async def stop(self):
        """停止服务"""
        print("[SERVER] 正在停止服务...")

        self._running = False

        # 停止处理任务
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        # 关闭连接
        for client in self._clients.copy():
            await client.close()

        # 释放资源
        if self.camera:
            self.camera.stop()

        if self.detector:
            self.detector.close()

        print("[SERVER] 服务已停止")

    def _on_gesture_event(self, event: GestureEvent):
        """手势事件回调"""
        # 获取手部位置用于鼠标控制
        hand_pos = None
        if self.detector and hasattr(self, '_last_detection'):
            for hand in self._last_detection.hands:
                if hand.hand_id == event.hand_id:
                    # 使用食指指尖位置
                    hand_pos = (
                        hand.landmarks[8][0],  # x
                        hand.landmarks[8][1]   # y
                    )
                    break

        # 执行动作
        if self.action_executor:
            self.action_executor.execute_gesture(
                gesture=event.gesture,
                event_type=event.event_type,
                hand_pos=hand_pos,
                meta=event.meta
            )

        # 广播事件
        asyncio.create_task(self._broadcast_event(event))

    async def _broadcast_event(self, event: GestureEvent):
        """广播手势事件到所有客户端"""
        if not self._clients:
            return

        message = WebSocketMessage(
            type="gesture_event",
            timestamp=event.timestamp,
            data=event.to_dict()
        )

        await self._broadcast(message.to_json())

    async def _broadcast(self, message: str):
        """广播消息到所有客户端"""
        if not self._clients:
            return

        # 并发发送
        await asyncio.gather(
            *[client.send(message) for client in self._clients.copy()],
            return_exceptions=True
        )

    async def _process_frames(self):
        """帧处理主循环"""
        print("[SERVER] 开始帧处理...")

        while self._running:
            # 读取帧
            frame = self.camera.read(timeout=0.1)
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            self._frame_count += 1

            # 检测手部
            detection = self.detector.detect(
                frame.image,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp
            )
            self._last_detection = detection

            # 绘制骨骼并更新 MJPEG 流
            output_frame = self.detector.draw_landmarks(frame.image, detection)
            set_current_frame(output_frame)

            # 处理每只手
            hands_data = []
            for hand in detection.hands:
                # 分类手势
                gesture_proba = self.classifier.classify(hand)

                # 更新状态机
                self.state_machine.update(
                    hand.hand_id,
                    gesture_proba,
                    frame.timestamp
                )

                # 检测滑动
                slide = self.classifier.detect_slide(hand)
                if slide:
                    direction, distance = slide
                    if self.action_executor:
                        self.action_executor.execute_slide(direction, distance)

                    # 广播滑动事件
                    slide_event = GestureEvent(
                        event_type="slide",
                        gesture=f"slide_{direction}",
                        hand_id=hand.hand_id,
                        timestamp=frame.timestamp,
                        hold_duration=0,
                        confidence=1.0,
                        meta={"direction": direction, "distance": distance}
                    )
                    await self._broadcast_event(slide_event)

                # 获取当前状态
                state = self.state_machine.get_state(hand.hand_id)

                # 构建手部数据
                hand_data = {
                    "id": hand.hand_id,
                    "handedness": hand.handedness,
                    "landmarks": hand.landmarks.tolist(),
                    "gesture": gesture_proba.dominant_gesture,
                    "gesture_score": gesture_proba.dominant_score,
                    "state": state.state.value if state else "idle"
                }
                hands_data.append(hand_data)

            # 广播帧数据
            message = WebSocketMessage(
                type="frame_data",
                timestamp=frame.timestamp,
                data={
                    "frame_id": frame.frame_id,
                    "hands": hands_data,
                    "inference_time_ms": detection.inference_time_ms,
                    "active": self.action_executor.is_active() if self.action_executor else False
                }
            )

            await self._broadcast(message.to_json())

            # 控制帧率
            await asyncio.sleep(0.001)

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理客户端连接"""
        client_id = id(websocket)
        print(f"[SERVER] 客户端已连接: {client_id}")

        self._clients.add(websocket)

        # 发送欢迎消息
        welcome = WebSocketMessage(
            type="connected",
            timestamp=time.time() * 1000,
            data={
                "message": "Welcome to PhantomHand",
                "version": "0.1.0",
                "config": {
                    "camera": {
                        "width": self.config.camera.width,
                        "height": self.config.camera.height
                    }
                }
            }
        )
        await websocket.send(welcome.to_json())

        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[SERVER] 客户端已断开: {client_id}")

    async def _handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "ping":
                # 心跳响应
                pong = WebSocketMessage(
                    type="pong",
                    timestamp=time.time() * 1000,
                    data={}
                )
                await websocket.send(pong.to_json())

            elif msg_type == "set_active":
                # 设置激活状态
                active = data.get("data", {}).get("active", False)
                if self.action_executor:
                    self.action_executor.set_active(active)
                    print(f"[SERVER] 控制状态: {'激活' if active else '停用'}")

            elif msg_type == "config_update":
                # 更新配置
                # TODO: 实现配置更新逻辑
                pass

        except json.JSONDecodeError:
            print(f"[WARN] 无效的 JSON 消息: {message}")
        except Exception as e:
            print(f"[ERROR] 处理消息异常: {e}")

    async def run(self, host: str = "127.0.0.1", port: int = 8765, mjpeg_port: int = 8766):
        """运行服务器"""
        await self.start()

        # 启动 MJPEG 流服务器（在单独线程中）
        mjpeg_thread = threading.Thread(
            target=run_mjpeg_server,
            args=(host, mjpeg_port),
            daemon=True
        )
        mjpeg_thread.start()

        # 启动帧处理任务
        self._processing_task = asyncio.create_task(self._process_frames())

        print(f"[SERVER] WebSocket 服务器启动: ws://{host}:{port}")

        async with websockets.serve(self.handle_client, host, port):
            # 保持运行
            while self._running:
                await asyncio.sleep(1)

                # 打印统计信息
                if self._frame_count > 0:
                    elapsed = time.time() - self._start_time
                    fps = self._frame_count / elapsed if elapsed > 0 else 0
                    print(f"[STATS] 帧数: {self._frame_count}, FPS: {fps:.1f}, "
                          f"客户端: {len(self._clients)}")


async def main():
    """主函数"""
    server = PhantomHandServer()

    try:
        await server.run()
    except KeyboardInterrupt:
        print("\n[SERVER] 收到中断信号")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
