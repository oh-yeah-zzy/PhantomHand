"""
手势识别模块
基于手部关键点进行手势分类
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

from .detector import HandLandmarks, LandmarkIndex, FINGER_INDICES


class GestureType(Enum):
    """手势类型枚举"""
    IDLE = "idle"           # 无手势/未识别
    OPEN = "open"           # 张开手掌
    FIST = "fist"           # 握拳
    PINCH = "pinch"         # 捏合（拇指+食指）
    POINT = "point"         # 指向（食指伸出）
    VICTORY = "victory"     # 剪刀手/V手势
    OK = "ok"               # OK手势
    THUMBS_UP = "thumbs_up" # 竖大拇指


@dataclass
class GestureProba:
    """手势概率分布"""
    probabilities: Dict[str, float]
    dominant_gesture: str
    dominant_score: float

    @classmethod
    def from_dict(cls, proba_dict: Dict[str, float]) -> "GestureProba":
        """从概率字典创建"""
        if not proba_dict:
            return cls({}, "idle", 0.0)

        dominant = max(proba_dict.items(), key=lambda x: x[1])
        return cls(
            probabilities=proba_dict,
            dominant_gesture=dominant[0],
            dominant_score=dominant[1]
        )


class GestureClassifier:
    """
    手势分类器
    使用基于规则的方法识别手势
    """

    def __init__(
        self,
        # 手指伸展阈值
        finger_extended_angle: float = 2.5,
        finger_bent_angle: float = 1.8,
        # 捏合阈值
        pinch_distance_ratio: float = 0.25,
        # 握拳阈值
        fist_tip_wrist_ratio: float = 0.5,
        # 张开阈值
        open_spread_ratio: float = 0.8,
    ):
        self.finger_extended_angle = finger_extended_angle
        self.finger_bent_angle = finger_bent_angle
        self.pinch_distance_ratio = pinch_distance_ratio
        self.fist_tip_wrist_ratio = fist_tip_wrist_ratio
        self.open_spread_ratio = open_spread_ratio

        # 滑动检测状态
        self._prev_positions: Dict[str, np.ndarray] = {}
        self._position_history: Dict[str, list] = {}

    def classify(self, hand: HandLandmarks) -> GestureProba:
        """
        对手部关键点进行手势分类

        Args:
            hand: 手部关键点数据

        Returns:
            GestureProba 手势概率分布
        """
        lm = hand.landmarks
        hand_scale = hand.hand_scale

        # 避免除零
        if hand_scale < 0.001:
            return GestureProba.from_dict({"idle": 1.0})

        # 计算各手指伸展状态
        finger_states = self._get_finger_states(lm)

        # 计算各手势的概率/得分
        proba = {}

        # 1. 张开手掌检测
        proba["open"] = self._calc_open_score(lm, finger_states, hand_scale)

        # 2. 握拳检测
        proba["fist"] = self._calc_fist_score(lm, finger_states, hand_scale)

        # 3. 捏合检测
        proba["pinch"] = self._calc_pinch_score(lm, finger_states, hand_scale)

        # 4. 指向检测
        proba["point"] = self._calc_point_score(lm, finger_states)

        # 5. 剪刀手/V手势检测
        proba["victory"] = self._calc_victory_score(lm, finger_states)

        # 6. OK手势检测
        proba["ok"] = self._calc_ok_score(lm, finger_states, hand_scale)

        # 归一化（使用 softmax 风格的归一化）
        proba = self._normalize_scores(proba)

        return GestureProba.from_dict(proba)

    def _get_finger_states(self, lm: np.ndarray) -> Dict[str, bool]:
        """
        判断每个手指的伸展状态

        Returns:
            字典，键为手指名，值为是否伸展
        """
        states = {}

        for finger_name, indices in FINGER_INDICES.items():
            tip_idx, dip_idx, pip_idx, mcp_idx = indices

            if finger_name == "thumb":
                # 大拇指使用不同的判断方式
                # 比较 tip 到手掌中心的距离
                palm_center = np.mean(lm[[5, 9, 13, 17]], axis=0)
                tip_dist = np.linalg.norm(lm[tip_idx][:2] - palm_center[:2])
                mcp_dist = np.linalg.norm(lm[mcp_idx][:2] - palm_center[:2])
                states[finger_name] = tip_dist > mcp_dist * 1.2
            else:
                # 其他手指：比较 tip-pip 和 mcp-pip 向量的夹角
                v1 = lm[tip_idx] - lm[pip_idx]
                v2 = lm[mcp_idx] - lm[pip_idx]

                # 计算夹角
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
                cos_angle = np.clip(cos_angle, -1, 1)
                angle = math.acos(cos_angle)

                # 伸直时夹角接近 π（180度）
                states[finger_name] = angle > self.finger_extended_angle

        return states

    def _calc_open_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool],
        hand_scale: float
    ) -> float:
        """计算张开手掌的得分"""
        # 所有手指都要伸展
        extended_count = sum(finger_states.values())

        # 计算指尖间距
        tips = [4, 8, 12, 16, 20]
        spread_distances = []
        for i in range(len(tips) - 1):
            dist = np.linalg.norm(lm[tips[i]][:2] - lm[tips[i+1]][:2])
            spread_distances.append(dist / hand_scale)

        avg_spread = np.mean(spread_distances)

        # 综合评分
        extension_score = extended_count / 5.0
        spread_score = min(avg_spread / self.open_spread_ratio, 1.0)

        return extension_score * 0.6 + spread_score * 0.4

    def _calc_fist_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool],
        hand_scale: float
    ) -> float:
        """计算握拳的得分"""
        # 除大拇指外的手指都要弯曲
        bent_fingers = ["index", "middle", "ring", "pinky"]
        bent_count = sum(1 for f in bent_fingers if not finger_states[f])

        # 计算指尖到手腕的距离
        wrist = lm[LandmarkIndex.WRIST][:2]
        tip_indices = [8, 12, 16, 20]
        tip_distances = []
        for idx in tip_indices:
            dist = np.linalg.norm(lm[idx][:2] - wrist) / hand_scale
            tip_distances.append(dist)

        avg_tip_dist = np.mean(tip_distances)

        # 综合评分
        bent_score = bent_count / 4.0
        distance_score = max(0, 1.0 - avg_tip_dist / self.fist_tip_wrist_ratio)

        return bent_score * 0.5 + distance_score * 0.5

    def _calc_pinch_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool],
        hand_scale: float
    ) -> float:
        """计算捏合的得分"""
        # 拇指和食指指尖距离
        thumb_tip = lm[LandmarkIndex.THUMB_TIP][:2]
        index_tip = lm[LandmarkIndex.INDEX_TIP][:2]
        pinch_dist = np.linalg.norm(thumb_tip - index_tip) / hand_scale

        # 距离越小得分越高
        distance_score = max(0, 1.0 - pinch_dist / self.pinch_distance_ratio)

        # 其他手指状态（中指、无名指、小指弯曲则更可能是捏合）
        other_bent = sum(1 for f in ["middle", "ring", "pinky"] if not finger_states[f])
        other_score = other_bent / 3.0

        return distance_score * 0.7 + other_score * 0.3

    def _calc_point_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool]
    ) -> float:
        """计算指向的得分"""
        # 食指伸展，其他手指弯曲
        index_extended = finger_states["index"]
        others_bent = sum(1 for f in ["middle", "ring", "pinky"] if not finger_states[f])

        if not index_extended:
            return 0.0

        return (others_bent / 3.0) * 0.7 + 0.3

    def _calc_victory_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool]
    ) -> float:
        """计算剪刀手/V手势的得分"""
        # 食指和中指伸展，其他弯曲
        index_extended = finger_states["index"]
        middle_extended = finger_states["middle"]
        others_bent = sum(1 for f in ["ring", "pinky"] if not finger_states[f])

        if not (index_extended and middle_extended):
            return 0.0

        # 检查食指和中指是否分开
        index_tip = lm[LandmarkIndex.INDEX_TIP][:2]
        middle_tip = lm[LandmarkIndex.MIDDLE_TIP][:2]
        spread = np.linalg.norm(index_tip - middle_tip)

        index_mcp = lm[LandmarkIndex.INDEX_MCP][:2]
        middle_mcp = lm[LandmarkIndex.MIDDLE_MCP][:2]
        base_spread = np.linalg.norm(index_mcp - middle_mcp)

        spread_ratio = spread / (base_spread + 1e-6)

        if spread_ratio < 1.5:  # 手指没有分开
            return 0.0

        return (others_bent / 2.0) * 0.5 + 0.5

    def _calc_ok_score(
        self,
        lm: np.ndarray,
        finger_states: Dict[str, bool],
        hand_scale: float
    ) -> float:
        """计算OK手势的得分"""
        # 拇指和食指形成圆圈，其他手指伸展
        thumb_tip = lm[LandmarkIndex.THUMB_TIP][:2]
        index_tip = lm[LandmarkIndex.INDEX_TIP][:2]
        circle_dist = np.linalg.norm(thumb_tip - index_tip) / hand_scale

        # 拇指食指要接触
        circle_score = max(0, 1.0 - circle_dist / 0.2)

        # 其他手指要伸展
        others_extended = sum(1 for f in ["middle", "ring", "pinky"] if finger_states[f])
        others_score = others_extended / 3.0

        return circle_score * 0.6 + others_score * 0.4

    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        """归一化分数"""
        total = sum(scores.values())
        if total < 0.001:
            return {"idle": 1.0}

        normalized = {k: v / total for k, v in scores.items()}

        # 如果所有分数都很低，添加 idle
        max_score = max(normalized.values())
        if max_score < 0.3:
            normalized["idle"] = 1.0 - max_score
            # 重新归一化
            total = sum(normalized.values())
            normalized = {k: v / total for k, v in normalized.items()}

        return normalized

    def detect_slide(
        self,
        hand: HandLandmarks,
        min_distance: float = 0.1,
        max_z_change: float = 0.05
    ) -> Optional[Tuple[str, float]]:
        """
        检测滑动手势

        Args:
            hand: 手部关键点
            min_distance: 最小滑动距离（相对于图像宽度）
            max_z_change: 最大 Z 轴变化

        Returns:
            (方向, 距离) 或 None
        """
        hand_id = hand.hand_id
        current_pos = hand.palm_center

        # 初始化历史记录
        if hand_id not in self._position_history:
            self._position_history[hand_id] = []

        history = self._position_history[hand_id]
        history.append(current_pos.copy())

        # 保持最近 10 帧
        if len(history) > 10:
            history.pop(0)

        if len(history) < 5:
            return None

        # 计算位移
        start_pos = history[0]
        end_pos = history[-1]
        delta = end_pos - start_pos

        # 检查 Z 轴变化
        if abs(delta[2]) > max_z_change:
            return None

        # 计算 XY 平面位移
        xy_distance = np.linalg.norm(delta[:2])

        if xy_distance < min_distance:
            return None

        # 判断方向
        if abs(delta[0]) > abs(delta[1]):
            direction = "right" if delta[0] > 0 else "left"
        else:
            direction = "down" if delta[1] > 0 else "up"

        # 清除历史（滑动完成）
        self._position_history[hand_id] = []

        return (direction, xy_distance)


# 测试代码
if __name__ == "__main__":
    from capture import CameraCapture
    from detector import HandDetector

    print("测试手势识别模块...")

    with CameraCapture(mirror=True) as camera, HandDetector() as detector:
        classifier = GestureClassifier()

        for frame in camera.read_generator():
            # 检测手部
            result = detector.detect(
                frame.image,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp
            )

            # 绘制关键点
            output = detector.draw_landmarks(frame.image, result)

            # 对每只手进行手势识别
            for hand in result.hands:
                gesture = classifier.classify(hand)

                # 显示手势
                wrist_pos = hand.landmarks_pixel[0]
                text = f"{gesture.dominant_gesture}: {gesture.dominant_score:.2f}"
                cv2.putText(output, text, (wrist_pos[0], wrist_pos[1] + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # 检测滑动
                slide = classifier.detect_slide(hand)
                if slide:
                    direction, distance = slide
                    cv2.putText(output, f"SLIDE: {direction}", (50, 100),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

            # 显示信息
            info = f"Hands: {result.num_hands} | FPS: {camera.actual_fps:.1f}"
            cv2.putText(output, info, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("PhantomHand - Gesture Test", output)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    print("测试完成")
