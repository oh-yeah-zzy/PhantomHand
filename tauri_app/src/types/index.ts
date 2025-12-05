/**
 * PhantomHand 类型定义
 */

import { Vector3 } from 'three'

// 手部关键点数据
export interface HandLandmarks {
  id: string              // 手部 ID (left/right)
  handedness: string      // 左手/右手
  landmarks: number[][]   // 21x3 关键点坐标 (归一化 0-1)
  gesture: string         // 当前手势
  gestureScore: number    // 手势置信度
  state: string           // 状态 (idle/entering/held/exiting)
}

// 帧数据消息
export interface FrameData {
  frameId: number
  hands: HandLandmarks[]
  inferenceTimeMs: number
  active: boolean
}

// 手势事件
export interface GestureEvent {
  eventType: 'enter' | 'hold' | 'exit' | 'slide'
  gesture: string
  handId: string
  timestamp: number
  holdDuration: number
  confidence: number
  meta?: Record<string, unknown>
}

// WebSocket 消息
export interface WebSocketMessage {
  type: string
  timestamp: number
  data: Record<string, unknown>
}

// 手部可视化状态
export interface HandVisualState {
  landmarks: Vector3[]
  gesture: string
  gestureScore: number
  state: string
  isActive: boolean
}

// 应用配置
export interface AppConfig {
  wsUrl: string
  showDebugInfo: boolean
  visualEffects: {
    glowIntensity: number
    trailLength: number
    particleCount: number
  }
}

// 手指连接定义
export const HAND_CONNECTIONS: [number, number][] = [
  // 大拇指
  [0, 1], [1, 2], [2, 3], [3, 4],
  // 食指
  [0, 5], [5, 6], [6, 7], [7, 8],
  // 中指
  [0, 9], [9, 10], [10, 11], [11, 12],
  // 无名指
  [0, 13], [13, 14], [14, 15], [15, 16],
  // 小指
  [0, 17], [17, 18], [18, 19], [19, 20],
  // 手掌横向
  [5, 9], [9, 13], [13, 17]
]

// 指尖索引
export const FINGER_TIPS = [4, 8, 12, 16, 20]

// 手势颜色映射
export const GESTURE_COLORS: Record<string, string> = {
  idle: '#666666',
  open: '#00ffff',
  fist: '#ff6600',
  pinch: '#00ff00',
  point: '#ffff00',
  victory: '#ff00ff',
  ok: '#00ff88'
}
