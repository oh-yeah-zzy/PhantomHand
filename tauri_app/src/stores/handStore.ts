/**
 * 手部状态管理 (Zustand)
 * 使用 mutable 模式避免不必要的重渲染
 */

import { create } from 'zustand'
import { Vector3 } from 'three'
import { HandLandmarks, FrameData, GestureEvent } from '../types'

// 将 2D 归一化坐标转换为 3D 空间坐标
function convertLandmarksTo3D(landmarks: number[][]): Vector3[] {
  return landmarks.map(([x, y, z]) => {
    // 将 0-1 归一化坐标转换为 -1 到 1 的范围
    // x: 0->1 映射到 -1->1 (后端已镜像，这里不再取反)
    // y: 0->1 映射到 1->-1 (上下翻转，因为屏幕坐标系 y 向下)
    // z: 保持原值，稍微放大
    return new Vector3(
      (x - 0.5) * 2,
      -(y - 0.5) * 2,
      -z * 0.5
    )
  })
}

interface HandState {
  landmarks: Vector3[]
  gesture: string
  gestureScore: number
  state: string
}

interface HandStore {
  // 连接状态
  isConnected: boolean
  wsUrl: string
  ws: WebSocket | null

  // 手部数据 (mutable，不触发重渲染)
  leftHand: HandState | null
  rightHand: HandState | null

  // 统计信息
  fps: number
  inferenceTime: number
  isActive: boolean

  // 最近的手势事件
  lastEvent: GestureEvent | null

  // 方法
  connect: (url: string) => void
  disconnect: () => void
  setActive: (active: boolean) => void

  // 直接获取手部数据（用于渲染循环）
  getLeftHand: () => HandState | null
  getRightHand: () => HandState | null
}

export const useHandStore = create<HandStore>((set, get) => ({
  // 初始状态
  isConnected: false,
  wsUrl: '',
  ws: null,
  leftHand: null,
  rightHand: null,
  fps: 0,
  inferenceTime: 0,
  isActive: false,
  lastEvent: null,

  // 连接 WebSocket
  connect: (url: string) => {
    const currentWs = get().ws
    if (currentWs) {
      currentWs.close()
    }

    console.log('[WS] 正在连接:', url)
    const ws = new WebSocket(url)

    ws.onopen = () => {
      console.log('[WS] 已连接')
      set({ isConnected: true, wsUrl: url })
    }

    ws.onclose = () => {
      console.log('[WS] 已断开')
      set({ isConnected: false, ws: null })

      // 自动重连
      setTimeout(() => {
        if (!get().isConnected) {
          console.log('[WS] 尝试重连...')
          get().connect(url)
        }
      }, 3000)
    }

    ws.onerror = (error) => {
      console.error('[WS] 错误:', error)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        handleMessage(message, set, get)
      } catch (e) {
        console.error('[WS] 解析消息失败:', e)
      }
    }

    set({ ws })
  },

  // 断开连接
  disconnect: () => {
    const ws = get().ws
    if (ws) {
      ws.close()
      set({ ws: null, isConnected: false })
    }
  },

  // 设置激活状态
  setActive: (active: boolean) => {
    const ws = get().ws
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'set_active',
        data: { active }
      }))
    }
    set({ isActive: active })
  },

  // 直接获取方法（用于渲染循环，避免订阅）
  getLeftHand: () => get().leftHand,
  getRightHand: () => get().rightHand,
}))

// 处理 WebSocket 消息
function handleMessage(
  message: { type: string; timestamp: number; data: Record<string, unknown> },
  set: (state: Partial<HandStore>) => void,
  get: () => HandStore
) {
  switch (message.type) {
    case 'connected':
      console.log('[WS] 收到欢迎消息:', message.data)
      break

    case 'frame_data': {
      // Backend uses snake_case, need to map to camelCase
      const rawData = message.data as Record<string, unknown>
      const hands = rawData.hands as Array<Record<string, unknown>> || []

      // 更新手部数据
      let leftHand: HandState | null = null
      let rightHand: HandState | null = null

      for (const hand of hands) {
        const handState: HandState = {
          landmarks: convertLandmarksTo3D(hand.landmarks as number[][]),
          gesture: hand.gesture as string,
          gestureScore: (hand.gesture_score as number) || 0,
          state: hand.state as string
        }

        if (hand.handedness === 'Left') {
          leftHand = handState
        } else {
          rightHand = handState
        }
      }

      // 直接修改状态对象，避免重渲染
      const store = get()
      store.leftHand = leftHand
      store.rightHand = rightHand

      // 只更新统计信息（这会触发订阅了这些值的组件重渲染）
      set({
        inferenceTime: (rawData.inference_time_ms as number) || 0,
        isActive: (rawData.active as boolean) || false
      })
      break
    }

    case 'gesture_event': {
      // Backend uses snake_case, map to camelCase
      const rawEvent = message.data as Record<string, unknown>
      const event: GestureEvent = {
        eventType: rawEvent.event_type as GestureEvent['eventType'],
        gesture: rawEvent.gesture as string,
        handId: rawEvent.hand_id as string,
        timestamp: rawEvent.timestamp as number,
        holdDuration: rawEvent.hold_duration as number,
        confidence: rawEvent.confidence as number,
        meta: rawEvent.meta as Record<string, unknown>
      }
      console.log('[EVENT]', event.eventType, event.gesture)
      set({ lastEvent: event })
      break
    }

    case 'pong':
      // 心跳响应
      break

    default:
      console.log('[WS] 未知消息类型:', message.type)
  }
}

// 心跳定时器
setInterval(() => {
  const store = useHandStore.getState()
  if (store.ws && store.ws.readyState === WebSocket.OPEN) {
    store.ws.send(JSON.stringify({
      type: 'ping',
      timestamp: Date.now()
    }))
  }
}, 5000)
