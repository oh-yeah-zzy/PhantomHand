"""
PhantomHand 配置文件
包含手势识别阈值、状态机参数、服务器配置等
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class GestureThresholds:
    """手势识别阈值配置"""

    # 手指伸展判定阈值（角度，弧度制）
    finger_extended_angle: float = 2.5  # 小于此角度认为伸直
    finger_bent_angle: float = 1.8      # 大于此角度认为弯曲

    # 捏合手势阈值（相对于手掌宽度的比例）
    pinch_distance_ratio: float = 0.25  # 拇指-食指距离小于此比例为捏合
    pinch_release_ratio: float = 0.35   # 大于此比例为松开

    # 握拳判定：指尖到手腕距离占手长比例
    fist_tip_wrist_ratio: float = 0.5   # 小于此比例为握拳

    # 张开手掌：指尖间距占手掌宽度比例
    open_spread_ratio: float = 0.8      # 大于此比例为张开

    # 滑动检测阈值（相对于屏幕宽度的比例）
    slide_min_distance: float = 0.1     # 最小滑动距离
    slide_max_z_change: float = 0.05    # 最大Z轴变化（防止前后移动误判）


@dataclass
class StateMachineConfig:
    """状态机配置"""

    # 概率阈值
    p_high: float = 0.4      # 进入手势的高阈值
    p_hold: float = 0.3      # 保持手势的阈值
    p_low: float = 0.2       # 退出手势的低阈值

    # 时间窗口（毫秒）
    t_enter: int = 120       # 进入手势需要的持续时间
    t_exit: int = 120        # 退出手势需要的持续时间
    t_cooldown: int = 200    # 手势之间的冷却时间

    # 滤波参数
    ema_alpha: float = 0.3   # 指数移动平均系数
    median_window: int = 5   # 中值滤波窗口大小

    # 手势优先级（数字越大优先级越高）
    gesture_priority: Dict[str, int] = field(default_factory=lambda: {
        "pinch": 5,
        "fist": 4,
        "point": 3,
        "open": 2,
        "slide": 1,
        "idle": 0
    })


@dataclass
class ActionMapping:
    """手势到动作的映射配置"""

    # 鼠标控制
    mouse_sensitivity: float = 1.5      # 鼠标灵敏度
    mouse_smoothing: float = 0.7        # 鼠标平滑系数

    # 默认手势映射
    mappings: Dict[str, str] = field(default_factory=lambda: {
        "open": "activate",              # 张开手掌：激活控制
        "fist": "media_pause",           # 握拳：暂停/静音
        "pinch": "mouse_click",          # 捏合：鼠标点击
        "point": "mouse_move",           # 指向：鼠标移动
        "slide_left": "switch_window",   # 左滑：切换窗口
        "slide_right": "switch_window",  # 右滑：切换窗口
        "slide_up": "volume_up",         # 上滑：音量增加
        "slide_down": "volume_down",     # 下滑：音量减少
    })


@dataclass
class ServerConfig:
    """WebSocket 服务器配置"""

    host: str = "127.0.0.1"
    port: int = 8765

    # 心跳配置
    heartbeat_interval: int = 5000   # 心跳间隔（毫秒）
    connection_timeout: int = 30000  # 连接超时（毫秒）


@dataclass
class CameraConfig:
    """摄像头配置"""

    device_id: int = 0               # 摄像头设备ID
    width: int = 640                 # 分辨率宽度
    height: int = 480                # 分辨率高度
    fps: int = 30                    # 帧率
    mirror: bool = True              # 是否镜像（自拍模式）


@dataclass
class Config:
    """主配置类，整合所有配置"""

    gesture: GestureThresholds = field(default_factory=GestureThresholds)
    state_machine: StateMachineConfig = field(default_factory=StateMachineConfig)
    action: ActionMapping = field(default_factory=ActionMapping)
    server: ServerConfig = field(default_factory=ServerConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)

    # 调试选项
    debug: bool = True
    show_preview: bool = True        # 显示调试预览窗口
    log_level: str = "INFO"


# 创建默认配置实例
default_config = Config()
