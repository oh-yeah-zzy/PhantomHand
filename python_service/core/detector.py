"""
手部检测模块
使用 MediaPipe Hands 进行手部关键点检测
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import IntEnum


class LandmarkIndex(IntEnum):
    """MediaPipe 手部 21 个关键点索引"""
    WRIST = 0

    # 大拇指
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4

    # 食指
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8

    # 中指
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12

    # 无名指
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16

    # 小指
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


# 手指定义：(指尖, DIP, PIP, MCP)
FINGER_INDICES = {
    "thumb": (4, 3, 2, 1),
    "index": (8, 7, 6, 5),
    "middle": (12, 11, 10, 9),
    "ring": (16, 15, 14, 13),
    "pinky": (20, 19, 18, 17)
}

# 骨骼连接定义（用于绘制）
HAND_CONNECTIONS = [
    # 手掌
    (0, 1), (1, 2), (2, 3), (3, 4),      # 大拇指
    (0, 5), (5, 6), (6, 7), (7, 8),      # 食指
    (0, 9), (9, 10), (10, 11), (11, 12), # 中指
    (0, 13), (13, 14), (14, 15), (15, 16), # 无名指
    (0, 17), (17, 18), (18, 19), (19, 20), # 小指
    # 手掌横向连接
    (5, 9), (9, 13), (13, 17)
]


@dataclass
class HandLandmarks:
    """单手关键点数据"""
    hand_id: str                           # 手的标识符 (left/right/uuid)
    handedness: str                        # 左手/右手
    landmarks: np.ndarray                  # 21x3 关键点坐标 (归一化)
    landmarks_pixel: np.ndarray            # 21x2 像素坐标
    confidence: float                      # 检测置信度
    image_width: int                       # 原图宽度
    image_height: int                      # 原图高度

    @property
    def wrist(self) -> np.ndarray:
        """手腕位置"""
        return self.landmarks[LandmarkIndex.WRIST]

    @property
    def palm_center(self) -> np.ndarray:
        """手掌中心（使用 MCP 关节的平均位置）"""
        mcp_indices = [5, 9, 13, 17]
        return np.mean(self.landmarks[mcp_indices], axis=0)

    @property
    def hand_scale(self) -> float:
        """手掌大小（食指MCP到小指MCP的距离，用于归一化）"""
        return np.linalg.norm(
            self.landmarks[LandmarkIndex.INDEX_MCP][:2] -
            self.landmarks[LandmarkIndex.PINKY_MCP][:2]
        )

    def get_finger_tip(self, finger: str) -> np.ndarray:
        """获取指尖位置"""
        tip_idx = FINGER_INDICES[finger][0]
        return self.landmarks[tip_idx]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "id": self.hand_id,
            "handedness": self.handedness,
            "landmarks": self.landmarks.tolist(),
            "landmarks_pixel": self.landmarks_pixel.tolist(),
            "confidence": self.confidence
        }


@dataclass
class DetectionResult:
    """检测结果"""
    hands: List[HandLandmarks] = field(default_factory=list)
    frame_id: int = 0
    timestamp: float = 0.0
    inference_time_ms: float = 0.0

    @property
    def num_hands(self) -> int:
        return len(self.hands)

    @property
    def has_hands(self) -> bool:
        return len(self.hands) > 0


class HandDetector:
    """
    手部检测器
    封装 MediaPipe Hands，提供统一的检测接口
    """

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1
    ):
        """
        初始化检测器

        Args:
            max_num_hands: 最大检测手数
            min_detection_confidence: 检测置信度阈值
            min_tracking_confidence: 追踪置信度阈值
            model_complexity: 模型复杂度 (0=lite, 1=full)
        """
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity

        # 初始化 MediaPipe
        self._mp_hands = mp.solutions.hands
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles

        # 创建检测器实例
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=model_complexity
        )

        # 手部追踪 ID 计数器
        self._hand_counter = 0
        self._prev_hands: Dict[str, np.ndarray] = {}

    def detect(
        self,
        image: np.ndarray,
        frame_id: int = 0,
        timestamp: float = 0.0
    ) -> DetectionResult:
        """
        检测手部关键点

        Args:
            image: BGR 格式图像
            frame_id: 帧序号
            timestamp: 时间戳

        Returns:
            DetectionResult 对象
        """
        import time
        start_time = time.time()

        # 转换颜色空间 BGR -> RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_height, image_width = image.shape[:2]

        # MediaPipe 处理
        results = self._hands.process(image_rgb)

        hands = []

        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness_info in zip(
                results.multi_hand_landmarks,
                results.multi_handedness
            ):
                # 提取手性信息
                handedness = handedness_info.classification[0].label
                confidence = handedness_info.classification[0].score

                # 提取 21 个关键点
                landmarks = np.array([
                    [lm.x, lm.y, lm.z]
                    for lm in hand_landmarks.landmark
                ])

                # 计算像素坐标
                landmarks_pixel = np.array([
                    [int(lm.x * image_width), int(lm.y * image_height)]
                    for lm in hand_landmarks.landmark
                ])

                # 生成手部 ID（基于手性和位置）
                hand_id = self._assign_hand_id(handedness, landmarks)

                hand = HandLandmarks(
                    hand_id=hand_id,
                    handedness=handedness,
                    landmarks=landmarks,
                    landmarks_pixel=landmarks_pixel,
                    confidence=confidence,
                    image_width=image_width,
                    image_height=image_height
                )
                hands.append(hand)

        inference_time = (time.time() - start_time) * 1000

        return DetectionResult(
            hands=hands,
            frame_id=frame_id,
            timestamp=timestamp,
            inference_time_ms=inference_time
        )

    def _assign_hand_id(self, handedness: str, landmarks: np.ndarray) -> str:
        """
        分配手部 ID
        简单实现：使用手性作为 ID
        高级实现可以基于位置追踪
        """
        return handedness.lower()  # "left" 或 "right"

    def draw_landmarks(
        self,
        image: np.ndarray,
        result: DetectionResult,
        draw_connections: bool = True,
        color: Tuple[int, int, int] = (0, 255, 255),  # 青色
        thickness: int = 2,
        circle_radius: int = 4
    ) -> np.ndarray:
        """
        在图像上绘制手部关键点

        Args:
            image: 原始图像
            result: 检测结果
            draw_connections: 是否绘制骨骼连线
            color: 颜色 (BGR)
            thickness: 线条粗细
            circle_radius: 关键点圆圈半径

        Returns:
            绘制后的图像
        """
        output = image.copy()

        for hand in result.hands:
            # 绘制连线
            if draw_connections:
                for start_idx, end_idx in HAND_CONNECTIONS:
                    start_point = tuple(hand.landmarks_pixel[start_idx])
                    end_point = tuple(hand.landmarks_pixel[end_idx])
                    cv2.line(output, start_point, end_point, color, thickness)

            # 绘制关键点
            for i, point in enumerate(hand.landmarks_pixel):
                # 指尖用不同颜色
                if i in [4, 8, 12, 16, 20]:
                    point_color = (0, 255, 0)  # 绿色
                    radius = circle_radius + 2
                else:
                    point_color = color
                    radius = circle_radius

                cv2.circle(output, tuple(point), radius, point_color, -1)

            # 显示手性标签
            wrist_pos = tuple(hand.landmarks_pixel[0])
            label = f"{hand.handedness} ({hand.confidence:.2f})"
            cv2.putText(output, label, (wrist_pos[0], wrist_pos[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return output

    def close(self):
        """释放资源"""
        self._hands.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# 测试代码
if __name__ == "__main__":
    from capture import CameraCapture

    print("测试手部检测模块...")

    with CameraCapture(mirror=True) as camera, HandDetector() as detector:
        for frame in camera.read_generator():
            # 检测
            result = detector.detect(
                frame.image,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp
            )

            # 绘制结果
            output = detector.draw_landmarks(frame.image, result)

            # 显示信息
            info_text = f"Hands: {result.num_hands} | Inference: {result.inference_time_ms:.1f}ms"
            cv2.putText(output, info_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("PhantomHand - Detection Test", output)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    print("测试完成")
