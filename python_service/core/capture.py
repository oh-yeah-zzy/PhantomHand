"""
摄像头采集模块
负责从摄像头获取视频帧，并进行基础预处理
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Generator
from dataclasses import dataclass
import threading
import queue
import time


@dataclass
class Frame:
    """视频帧数据结构"""
    image: np.ndarray           # BGR 图像数据
    frame_id: int               # 帧序号
    timestamp: float            # 时间戳（毫秒）
    width: int                  # 图像宽度
    height: int                 # 图像高度


class CameraCapture:
    """
    摄像头采集类
    支持多线程异步采集，减少主线程阻塞
    """

    def __init__(
        self,
        device_id: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        mirror: bool = True,
        buffer_size: int = 2
    ):
        """
        初始化摄像头

        Args:
            device_id: 摄像头设备ID
            width: 分辨率宽度
            height: 分辨率高度
            fps: 目标帧率
            mirror: 是否水平翻转（镜像模式）
            buffer_size: 帧缓冲区大小
        """
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.mirror = mirror
        self.buffer_size = buffer_size

        # 内部状态
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._start_time = 0.0

    def start(self) -> bool:
        """
        启动摄像头采集

        Returns:
            是否成功启动
        """
        if self._running:
            return True

        # 初始化摄像头
        self._cap = cv2.VideoCapture(self.device_id)
        if not self._cap.isOpened():
            print(f"[ERROR] 无法打开摄像头 {self.device_id}")
            return False

        # 设置摄像头参数
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        # 读取实际参数（可能与设置不同）
        actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        print(f"[INFO] 摄像头已启动: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")

        # 启动采集线程
        self._running = True
        self._start_time = time.time() * 1000
        self._frame_count = 0
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        return True

    def stop(self):
        """停止摄像头采集"""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if self._cap:
            self._cap.release()
            self._cap = None

        # 清空队列
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        print("[INFO] 摄像头已停止")

    def _capture_loop(self):
        """采集线程主循环"""
        while self._running and self._cap and self._cap.isOpened():
            ret, image = self._cap.read()

            if not ret:
                print("[WARN] 读取帧失败")
                continue

            # 镜像翻转
            if self.mirror:
                image = cv2.flip(image, 1)

            # 创建帧对象
            self._frame_count += 1
            timestamp = time.time() * 1000 - self._start_time

            frame = Frame(
                image=image,
                frame_id=self._frame_count,
                timestamp=timestamp,
                width=image.shape[1],
                height=image.shape[0]
            )

            # 放入队列（如果满了则丢弃旧帧）
            try:
                if self._frame_queue.full():
                    self._frame_queue.get_nowait()  # 丢弃旧帧
                self._frame_queue.put_nowait(frame)
            except queue.Full:
                pass

    def read(self, timeout: float = 0.1) -> Optional[Frame]:
        """
        读取一帧图像

        Args:
            timeout: 超时时间（秒）

        Returns:
            Frame 对象，如果无可用帧则返回 None
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_generator(self) -> Generator[Frame, None, None]:
        """
        帧生成器，用于迭代读取

        Yields:
            Frame 对象
        """
        while self._running:
            frame = self.read()
            if frame:
                yield frame

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    @property
    def actual_fps(self) -> float:
        """计算实际帧率"""
        if self._frame_count == 0 or self._start_time == 0:
            return 0.0
        elapsed = (time.time() * 1000 - self._start_time) / 1000
        return self._frame_count / elapsed if elapsed > 0 else 0.0

    def __enter__(self):
        """支持 with 语句"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句"""
        self.stop()
        return False


# 测试代码
if __name__ == "__main__":
    print("测试摄像头采集模块...")

    with CameraCapture(mirror=True) as camera:
        for frame in camera.read_generator():
            # 显示帧率
            fps_text = f"FPS: {camera.actual_fps:.1f}"
            cv2.putText(frame.image, fps_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("PhantomHand - Camera Test", frame.image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    print("测试完成")
