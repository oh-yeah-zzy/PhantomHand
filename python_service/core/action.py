"""
动作执行模块
将手势事件转换为系统操作（鼠标、键盘、媒体控制等）
"""

import time
from typing import Callable, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading

# Windows 平台相关
import platform
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes

    # Windows API 常量
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_ABSOLUTE = 0x8000

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_EXTENDEDKEY = 0x0001

    # 虚拟键码
    VK_VOLUME_UP = 0xAF
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_MUTE = 0xAD
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_LWIN = 0x5B
    VK_TAB = 0x09
    VK_MENU = 0x12  # Alt key

    # INPUT 结构体定义
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT)
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", wintypes.DWORD),
            ("union", INPUT_UNION)
        ]

    # 加载 user32.dll
    user32 = ctypes.windll.user32


class ActionType(Enum):
    """动作类型"""
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    MOUSE_SCROLL = "mouse_scroll"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"
    MEDIA_PLAY_PAUSE = "media_play_pause"
    MEDIA_NEXT = "media_next"
    MEDIA_PREV = "media_prev"
    SWITCH_WINDOW = "switch_window"
    SCREENSHOT = "screenshot"
    CUSTOM = "custom"


@dataclass
class ActionConfig:
    """动作配置"""
    # 相对定位模式（类似触摸板）
    mouse_mode: str = "relative"       # "relative" 或 "absolute"
    mouse_speed: float = 2.0           # 鼠标速度增益
    mouse_delta_smoothing: float = 0.5 # 位移平滑系数 (0-1, 越大越平滑但延迟越高)
    mouse_deadzone: float = 0.003      # 死区阈值（归一化坐标）
    # 旧的绝对定位参数（保留兼容）
    mouse_sensitivity: float = 1.5     # 鼠标灵敏度（绝对模式）
    mouse_smoothing: float = 0.7       # 鼠标平滑系数（绝对模式）
    scroll_speed: int = 3              # 滚动速度
    screen_width: int = 1920           # 屏幕宽度
    screen_height: int = 1080          # 屏幕高度


class ActionExecutor:
    """
    动作执行器
    将手势映射到系统操作
    """

    def __init__(self, config: Optional[ActionConfig] = None):
        self.config = config or ActionConfig()

        # 获取屏幕尺寸
        if platform.system() == "Windows":
            self.config.screen_width = user32.GetSystemMetrics(0)
            self.config.screen_height = user32.GetSystemMetrics(1)

        # 鼠标状态
        self._mouse_pressed = False
        self._last_mouse_pos: Optional[Tuple[float, float]] = None
        self._smoothed_pos: Optional[Tuple[float, float]] = None

        # 相对定位状态
        self._rel_last_pos: Optional[Tuple[float, float]] = None
        self._rel_smoothed_delta: Tuple[float, float] = (0.0, 0.0)
        self._rel_is_lifted = True  # 初始为抬起状态

        # 动作映射（open 和 fist 单独处理，不在此映射中）
        self._gesture_action_map: Dict[str, ActionType] = {
            "pinch": ActionType.MOUSE_CLICK,
            "point": ActionType.MOUSE_MOVE,
            "victory": ActionType.SCREENSHOT,
            "ok": ActionType.VOLUME_MUTE,
        }

        # 滑动方向映射
        self._slide_action_map: Dict[str, ActionType] = {
            "left": ActionType.SWITCH_WINDOW,
            "right": ActionType.SWITCH_WINDOW,
            "up": ActionType.VOLUME_UP,
            "down": ActionType.VOLUME_DOWN,
        }

        # 控制是否激活
        self._active = False
        self._action_lock = threading.Lock()

        # 激活状态变更回调（用于通知 server 广播状态）
        self._on_active_changed: Optional[Callable[[bool], None]] = None

    def set_on_active_changed(self, callback: Callable[[bool], None]):
        """设置激活状态变更回调"""
        self._on_active_changed = callback

    def set_active(self, active: bool, notify: bool = True):
        """
        设置是否激活控制

        Args:
            active: 是否激活
            notify: 是否触发回调通知（前端调用时为 False 避免循环）
        """
        if self._active == active:
            return

        self._active = active
        if not active:
            # 释放可能的按键
            self._release_all()
        # 重置相对定位状态
        self._rel_last_pos = None
        self._rel_smoothed_delta = (0.0, 0.0)
        self._rel_is_lifted = True

        # 通知状态变更
        if notify and self._on_active_changed:
            self._on_active_changed(active)

    def is_active(self) -> bool:
        """是否激活"""
        return self._active

    def execute_gesture(
        self,
        gesture: str,
        event_type: str,
        hand_pos: Optional[Tuple[float, float]] = None,
        meta: Optional[Dict] = None
    ):
        """
        执行手势对应的动作

        Args:
            gesture: 手势类型
            event_type: 事件类型 (enter/hold/exit)
            hand_pos: 手部位置 (归一化 0-1)
            meta: 附加信息
        """
        # open 手势用于激活控制（无论当前是否激活都可以触发）
        if gesture == "open":
            print(f"[ACTION] 收到 open 手势, event_type={event_type}, active={self._active}")
            if event_type == "enter" and not self._active:
                self.set_active(True)
                print("[ACTION] 控制已激活 (open 手势)")
            return

        # fist 手势用于停用控制（无论当前是否激活都可以触发）
        if gesture == "fist":
            if event_type == "enter" and self._active:
                self.set_active(False)
                print("[ACTION] 控制已停用 (fist 手势)")
            return

        # 其他手势需要激活状态才能执行
        if not self._active:
            return

        with self._action_lock:
            # 根据手势执行动作
            action = self._gesture_action_map.get(gesture)
            if not action:
                return

            if action == ActionType.MOUSE_MOVE:
                if hand_pos and event_type in ("enter", "hold"):
                    self._move_mouse(hand_pos)
                elif event_type == "exit":
                    # 手势退出时重置追踪（相当于"抬手"）
                    self.reset_mouse_tracking()

            elif action == ActionType.MOUSE_CLICK:
                if event_type == "enter":
                    self._mouse_down()
                elif event_type == "exit":
                    self._mouse_up()

            elif action == ActionType.VOLUME_MUTE:
                if event_type == "enter":
                    self._volume_mute()

            elif action == ActionType.SCREENSHOT:
                if event_type == "enter":
                    self._screenshot()

    def execute_slide(self, direction: str, distance: float):
        """
        执行滑动动作

        Args:
            direction: 滑动方向 (left/right/up/down)
            distance: 滑动距离
        """
        if not self._active:
            return

        with self._action_lock:
            action = self._slide_action_map.get(direction)
            if not action:
                return

            if action == ActionType.SWITCH_WINDOW:
                self._switch_window(direction == "right")

            elif action == ActionType.VOLUME_UP:
                self._volume_change(up=True)

            elif action == ActionType.VOLUME_DOWN:
                self._volume_change(up=False)

    # ========== Windows 平台实现 ==========

    def _move_mouse(self, pos: Tuple[float, float]):
        """移动鼠标"""
        if platform.system() != "Windows":
            return

        if self.config.mouse_mode == "relative":
            self._move_mouse_relative(pos)
        else:
            self._move_mouse_absolute(pos)

    def _move_mouse_relative(self, pos: Tuple[float, float]):
        """相对定位模式（类似触摸板）"""
        # 如果是抬起状态或没有上一个位置，初始化参考点
        if self._rel_is_lifted or self._rel_last_pos is None:
            self._rel_last_pos = pos
            self._rel_smoothed_delta = (0.0, 0.0)
            self._rel_is_lifted = False
            return

        # 计算本帧位移（归一化坐标）
        dx_raw = pos[0] - self._rel_last_pos[0]
        dy_raw = pos[1] - self._rel_last_pos[1]
        self._rel_last_pos = pos

        # 位移平滑 (EMA)
        alpha = self.config.mouse_delta_smoothing
        self._rel_smoothed_delta = (
            alpha * self._rel_smoothed_delta[0] + (1 - alpha) * dx_raw,
            alpha * self._rel_smoothed_delta[1] + (1 - alpha) * dy_raw,
        )

        # 死区检测
        if (abs(self._rel_smoothed_delta[0]) < self.config.mouse_deadzone and
            abs(self._rel_smoothed_delta[1]) < self.config.mouse_deadzone):
            return

        # 归一化位移 -> 像素位移，应用速度增益
        dx_px = int(self._rel_smoothed_delta[0] * self.config.screen_width * self.config.mouse_speed)
        dy_px = int(self._rel_smoothed_delta[1] * self.config.screen_height * self.config.mouse_speed)

        if dx_px == 0 and dy_px == 0:
            return

        # 发送相对移动
        self._send_mouse_move_relative(dx_px, dy_px)

    def _send_mouse_move_relative(self, dx: int, dy: int):
        """发送相对鼠标移动"""
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.union.mi.dx = dx
        inp.union.mi.dy = dy
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _move_mouse_absolute(self, pos: Tuple[float, float]):
        """绝对定位模式"""
        # 位置平滑
        if self._smoothed_pos is None:
            self._smoothed_pos = pos
        else:
            alpha = self.config.mouse_smoothing
            self._smoothed_pos = (
                alpha * self._smoothed_pos[0] + (1 - alpha) * pos[0],
                alpha * self._smoothed_pos[1] + (1 - alpha) * pos[1]
            )

        # 转换为屏幕坐标
        x = int(self._smoothed_pos[0] * self.config.screen_width)
        y = int(self._smoothed_pos[1] * self.config.screen_height)

        # 应用灵敏度
        x = int(x * self.config.mouse_sensitivity)
        y = int(y * self.config.mouse_sensitivity)

        # 限制在屏幕范围内
        x = max(0, min(x, self.config.screen_width - 1))
        y = max(0, min(y, self.config.screen_height - 1))

        # 移动鼠标
        user32.SetCursorPos(x, y)

    def reset_mouse_tracking(self):
        """重置鼠标追踪状态（用于抬手重新定位）"""
        self._rel_last_pos = None
        self._rel_smoothed_delta = (0.0, 0.0)
        self._rel_is_lifted = True
        self._smoothed_pos = None

    def _mouse_down(self):
        """鼠标按下"""
        if platform.system() != "Windows" or self._mouse_pressed:
            return

        self._mouse_pressed = True
        self._send_mouse_event(MOUSEEVENTF_LEFTDOWN)
        print("[ACTION] 鼠标按下")

    def _mouse_up(self):
        """鼠标释放"""
        if platform.system() != "Windows" or not self._mouse_pressed:
            return

        self._mouse_pressed = False
        self._send_mouse_event(MOUSEEVENTF_LEFTUP)
        print("[ACTION] 鼠标释放")

    def _send_mouse_event(self, flags: int, data: int = 0):
        """发送鼠标事件"""
        if platform.system() != "Windows":
            return

        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.union.mi.dwFlags = flags
        inp.union.mi.mouseData = data
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _send_key(self, vk: int, up: bool = False):
        """发送键盘事件"""
        if platform.system() != "Windows":
            return

        inp = INPUT()
        inp.type = 1  # INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _press_key(self, vk: int):
        """按下并释放按键"""
        self._send_key(vk, up=False)
        time.sleep(0.05)
        self._send_key(vk, up=True)

    def _volume_change(self, up: bool):
        """调节音量"""
        if platform.system() != "Windows":
            return

        vk = VK_VOLUME_UP if up else VK_VOLUME_DOWN
        self._press_key(vk)
        print(f"[ACTION] 音量{'增加' if up else '减少'}")

    def _volume_mute(self):
        """静音切换"""
        if platform.system() != "Windows":
            return

        self._press_key(VK_VOLUME_MUTE)
        print("[ACTION] 静音切换")

    def _media_play_pause(self):
        """播放/暂停"""
        if platform.system() != "Windows":
            return

        self._press_key(VK_MEDIA_PLAY_PAUSE)
        print("[ACTION] 播放/暂停")

    def _switch_window(self, forward: bool = True):
        """切换窗口 (Alt+Tab)"""
        if platform.system() != "Windows":
            return

        # Alt + Tab
        self._send_key(VK_MENU, up=False)
        time.sleep(0.05)
        self._press_key(VK_TAB)
        time.sleep(0.05)
        self._send_key(VK_MENU, up=True)
        print(f"[ACTION] 切换窗口 ({'前进' if forward else '后退'})")

    def _screenshot(self):
        """截屏 (Win + Shift + S)"""
        if platform.system() != "Windows":
            return

        # Win + Shift + S
        self._send_key(VK_LWIN, up=False)
        time.sleep(0.02)
        self._send_key(0x10, up=False)  # Shift
        time.sleep(0.02)
        self._press_key(0x53)  # S
        time.sleep(0.02)
        self._send_key(0x10, up=True)
        self._send_key(VK_LWIN, up=True)
        print("[ACTION] 截屏")

    def _release_all(self):
        """释放所有按键"""
        if self._mouse_pressed:
            self._mouse_up()
        self._smoothed_pos = None


# 测试代码
if __name__ == "__main__":
    print("测试动作执行模块...")
    print(f"当前平台: {platform.system()}")

    executor = ActionExecutor()
    print(f"屏幕尺寸: {executor.config.screen_width}x{executor.config.screen_height}")

    if platform.system() == "Windows":
        print("\n测试动作（3秒后开始）...")
        time.sleep(3)

        # 测试音量
        print("测试音量增加...")
        executor.set_active(True)
        executor._volume_change(up=True)
        time.sleep(1)

        print("测试音量减少...")
        executor._volume_change(up=False)
        time.sleep(1)

        print("测试完成")
    else:
        print("非 Windows 平台，跳过动作测试")
