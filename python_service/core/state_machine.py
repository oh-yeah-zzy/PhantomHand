"""
手势状态机模块
负责手势的稳定化、去抖动和事件生成
"""

import time
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import numpy as np

from .gesture import GestureProba


class GestureState(Enum):
    """手势状态枚举"""
    IDLE = "idle"           # 空闲状态
    ENTERING = "entering"   # 正在进入手势
    HELD = "held"           # 手势保持中
    EXITING = "exiting"     # 正在退出手势


@dataclass
class GestureEvent:
    """手势事件"""
    event_type: str          # "enter" | "hold" | "exit"
    gesture: str             # 手势类型
    hand_id: str             # 手部 ID
    timestamp: float         # 时间戳
    hold_duration: float     # 保持时长（毫秒）
    confidence: float        # 置信度
    meta: Dict = field(default_factory=dict)  # 附加信息（如滑动方向）

    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type,
            "gesture": self.gesture,
            "hand_id": self.hand_id,
            "timestamp": self.timestamp,
            "hold_duration": self.hold_duration,
            "confidence": self.confidence,
            "meta": self.meta
        }


@dataclass
class HandGestureState:
    """单手的手势状态"""
    state: GestureState = GestureState.IDLE
    gesture: str = "idle"
    enter_time: float = 0.0
    last_update_time: float = 0.0
    hold_duration: float = 0.0
    confidence: float = 0.0

    # 用于平滑的历史概率
    proba_history: deque = field(default_factory=lambda: deque(maxlen=10))

    # EMA 平滑值
    smoothed_proba: Dict[str, float] = field(default_factory=dict)


class GestureStateMachine:
    """
    手势状态机
    处理多手的手势状态转换，提供稳定的手势事件
    """

    def __init__(
        self,
        # 概率阈值
        p_high: float = 0.7,
        p_hold: float = 0.5,
        p_low: float = 0.3,
        # 时间阈值（毫秒）
        t_enter: int = 120,
        t_exit: int = 120,
        t_cooldown: int = 200,
        # 平滑参数
        ema_alpha: float = 0.3,
        median_window: int = 5,
        # 手势优先级
        gesture_priority: Optional[Dict[str, int]] = None
    ):
        self.p_high = p_high
        self.p_hold = p_hold
        self.p_low = p_low
        self.t_enter = t_enter
        self.t_exit = t_exit
        self.t_cooldown = t_cooldown
        self.ema_alpha = ema_alpha
        self.median_window = median_window

        # 默认手势优先级
        # open 和 fist 用于激活/停用控制，需要最高优先级
        self.gesture_priority = gesture_priority or {
            "open": 6,
            "fist": 5,
            "pinch": 4,
            "point": 3,
            "victory": 3,
            "ok": 3,
            "idle": 0
        }

        # 各手的状态
        self._hand_states: Dict[str, HandGestureState] = {}

        # 冷却时间记录
        self._cooldown_until: Dict[str, float] = {}

        # 事件回调
        self._callbacks: List[Callable[[GestureEvent], None]] = []

    def register_callback(self, callback: Callable[[GestureEvent], None]):
        """注册事件回调"""
        self._callbacks.append(callback)

    def _emit_event(self, event: GestureEvent):
        """发送事件"""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"[WARN] 事件回调异常: {e}")

    def update(
        self,
        hand_id: str,
        proba: GestureProba,
        timestamp: Optional[float] = None
    ) -> Optional[GestureEvent]:
        """
        更新手势状态

        Args:
            hand_id: 手部标识符
            proba: 手势概率分布
            timestamp: 时间戳（毫秒），默认使用当前时间

        Returns:
            如果产生了事件则返回 GestureEvent，否则返回 None
        """
        if timestamp is None:
            timestamp = time.time() * 1000

        # 获取或创建手部状态
        if hand_id not in self._hand_states:
            self._hand_states[hand_id] = HandGestureState()

        hs = self._hand_states[hand_id]

        # 检查冷却
        if hand_id in self._cooldown_until:
            if timestamp < self._cooldown_until[hand_id]:
                return None
            else:
                del self._cooldown_until[hand_id]

        # 平滑概率
        smoothed = self._smooth_proba(hs, proba.probabilities)

        # 找到最高优先级的候选手势
        candidate_gesture, candidate_score = self._get_best_gesture(smoothed)

        # 调试：每秒打印一次候选手势（避免刷屏）
        import time
        current_sec = int(time.time())
        if not hasattr(self, '_last_debug_sec') or self._last_debug_sec != current_sec:
            self._last_debug_sec = current_sec
            print(f"[DEBUG] 候选手势={candidate_gesture}, 分数={candidate_score:.2f}, 阈值={self.p_high}", flush=True)

        # 状态机转换
        event = None

        if hs.state == GestureState.IDLE:
            # 空闲状态：检测手势进入
            if candidate_score > self.p_high:
                hs.state = GestureState.ENTERING
                hs.gesture = candidate_gesture
                hs.enter_time = timestamp
                hs.confidence = candidate_score
                print(f"[STATE] {candidate_gesture} 进入 ENTERING 状态", flush=True)

        elif hs.state == GestureState.ENTERING:
            # 进入中：检查是否稳定进入
            if candidate_gesture == hs.gesture and candidate_score > self.p_high:
                # 持续保持
                if timestamp - hs.enter_time >= self.t_enter:
                    # 正式进入
                    hs.state = GestureState.HELD
                    hs.hold_duration = 0

                    event = GestureEvent(
                        event_type="enter",
                        gesture=hs.gesture,
                        hand_id=hand_id,
                        timestamp=timestamp,
                        hold_duration=0,
                        confidence=candidate_score
                    )
                    print(f"[STATE] 触发 enter 事件: {hs.gesture}", flush=True)
                    self._emit_event(event)
            else:
                # 切换或退出
                hs.state = GestureState.IDLE
                hs.gesture = "idle"

        elif hs.state == GestureState.HELD:
            # 保持中：检查是否退出或切换
            current_score = smoothed.get(hs.gesture, 0)

            if current_score >= self.p_hold:
                # 继续保持
                hs.hold_duration = timestamp - hs.enter_time
                hs.confidence = current_score

                # 发送 hold 事件（通过回调触发，用于鼠标移动等持续动作）
                event = GestureEvent(
                    event_type="hold",
                    gesture=hs.gesture,
                    hand_id=hand_id,
                    timestamp=timestamp,
                    hold_duration=hs.hold_duration,
                    confidence=current_score
                )
                self._emit_event(event)

            elif current_score < self.p_low:
                # 开始退出
                hs.state = GestureState.EXITING
                hs.last_update_time = timestamp

            elif candidate_gesture != hs.gesture and candidate_score > self.p_high:
                # 手势切换
                # 先退出当前手势
                exit_event = GestureEvent(
                    event_type="exit",
                    gesture=hs.gesture,
                    hand_id=hand_id,
                    timestamp=timestamp,
                    hold_duration=hs.hold_duration,
                    confidence=current_score
                )
                self._emit_event(exit_event)

                # 进入新手势
                hs.state = GestureState.ENTERING
                hs.gesture = candidate_gesture
                hs.enter_time = timestamp
                hs.confidence = candidate_score

        elif hs.state == GestureState.EXITING:
            # 退出中：检查是否恢复或确认退出
            current_score = smoothed.get(hs.gesture, 0)

            if current_score >= self.p_hold:
                # 恢复保持
                hs.state = GestureState.HELD
            elif timestamp - hs.last_update_time >= self.t_exit:
                # 确认退出
                event = GestureEvent(
                    event_type="exit",
                    gesture=hs.gesture,
                    hand_id=hand_id,
                    timestamp=timestamp,
                    hold_duration=hs.hold_duration,
                    confidence=current_score
                )
                self._emit_event(event)

                # 进入冷却
                self._cooldown_until[hand_id] = timestamp + self.t_cooldown

                # 重置状态
                hs.state = GestureState.IDLE
                hs.gesture = "idle"
                hs.hold_duration = 0

        hs.last_update_time = timestamp

        return event

    def _smooth_proba(
        self,
        hs: HandGestureState,
        proba: Dict[str, float]
    ) -> Dict[str, float]:
        """
        平滑概率值

        使用 EMA（指数移动平均）+ 中值滤波
        """
        # 更新历史
        hs.proba_history.append(proba.copy())

        # EMA 平滑
        for gesture, p in proba.items():
            if gesture in hs.smoothed_proba:
                hs.smoothed_proba[gesture] = (
                    self.ema_alpha * p +
                    (1 - self.ema_alpha) * hs.smoothed_proba[gesture]
                )
            else:
                hs.smoothed_proba[gesture] = p

        # 中值滤波（对历史数据）
        if len(hs.proba_history) >= self.median_window:
            result = {}
            for gesture in proba.keys():
                values = [h.get(gesture, 0) for h in list(hs.proba_history)[-self.median_window:]]
                result[gesture] = float(np.median(values))
            return result

        return hs.smoothed_proba.copy()

    def _get_best_gesture(self, proba: Dict[str, float]) -> tuple:
        """
        根据概率和优先级选择最佳手势

        选择策略：
        1. 筛选出分数超过 p_high 阈值的候选手势
        2. 在这些候选中，选择优先级最高的
        3. 如果没有超过阈值的，选择分数最高的

        Returns:
            (手势名, 概率)
        """
        candidates = []
        for gesture, score in proba.items():
            priority = self.gesture_priority.get(gesture, 0)
            candidates.append((gesture, score, priority))

        if not candidates:
            return "idle", 0.0

        # 筛选出分数超过阈值的候选
        high_score_candidates = [c for c in candidates if c[1] >= self.p_high]

        if high_score_candidates:
            # 在高分候选中，优先级优先，其次是分数
            high_score_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
            return high_score_candidates[0][0], high_score_candidates[0][1]
        else:
            # 没有高分候选，按分数选择
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0], candidates[0][1]

    def get_state(self, hand_id: str) -> Optional[HandGestureState]:
        """获取指定手的状态"""
        return self._hand_states.get(hand_id)

    def get_all_states(self) -> Dict[str, HandGestureState]:
        """获取所有手的状态"""
        return self._hand_states.copy()

    def reset(self, hand_id: Optional[str] = None):
        """
        重置状态

        Args:
            hand_id: 指定手部 ID，为 None 时重置所有
        """
        if hand_id:
            if hand_id in self._hand_states:
                self._hand_states[hand_id] = HandGestureState()
        else:
            self._hand_states.clear()
            self._cooldown_until.clear()


# 测试代码
if __name__ == "__main__":
    from capture import CameraCapture
    from detector import HandDetector
    from gesture import GestureClassifier
    import cv2

    print("测试状态机模块...")

    # 事件回调
    def on_gesture_event(event: GestureEvent):
        print(f"[EVENT] {event.event_type}: {event.gesture} "
              f"(hand={event.hand_id}, duration={event.hold_duration:.0f}ms)")

    with CameraCapture(mirror=True) as camera, HandDetector() as detector:
        classifier = GestureClassifier()
        state_machine = GestureStateMachine()
        state_machine.register_callback(on_gesture_event)

        for frame in camera.read_generator():
            # 检测
            result = detector.detect(
                frame.image,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp
            )

            output = detector.draw_landmarks(frame.image, result)

            # 处理每只手
            for hand in result.hands:
                # 分类
                gesture_proba = classifier.classify(hand)

                # 状态机更新
                event = state_machine.update(
                    hand.hand_id,
                    gesture_proba,
                    frame.timestamp
                )

                # 获取当前状态
                state = state_machine.get_state(hand.hand_id)

                # 显示
                wrist_pos = hand.landmarks_pixel[0]
                if state:
                    text = f"{state.gesture} [{state.state.value}]"
                    color = (0, 255, 0) if state.state == GestureState.HELD else (0, 255, 255)
                    cv2.putText(output, text, (wrist_pos[0], wrist_pos[1] + 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # 显示信息
            info = f"Hands: {result.num_hands} | FPS: {camera.actual_fps:.1f}"
            cv2.putText(output, info, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("PhantomHand - StateMachine Test", output)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()
    print("测试完成")
