/**
 * 状态面板组件
 * 显示连接状态、FPS、手势信息等
 */

import { useHandStore } from '../stores/handStore'
import { GESTURE_COLORS } from '../types'

export function StatusPanel() {
  const {
    isConnected,
    inferenceTime,
    isActive,
    lastEvent,
    leftHand,
    rightHand
  } = useHandStore()

  // 获取当前手势
  const currentGesture = leftHand?.gesture || rightHand?.gesture || 'idle'
  const gestureColor = GESTURE_COLORS[currentGesture] || '#666666'

  return (
    <div className="status-panel">
      <h2 className="panel-title">PhantomHand</h2>

      <div className="status-grid">
        {/* 连接状态 */}
        <div className="status-item">
          <span className="label">连接</span>
          <span className={`value ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '已连接' : '未连接'}
          </span>
        </div>

        {/* 推理时间 */}
        <div className="status-item">
          <span className="label">延迟</span>
          <span className="value">{(inferenceTime ?? 0).toFixed(1)} ms</span>
        </div>

        {/* 控制状态 */}
        <div className="status-item">
          <span className="label">控制</span>
          <span className={`value ${isActive ? 'active' : ''}`}>
            {isActive ? '已激活' : '未激活'}
          </span>
        </div>

        {/* 当前手势 */}
        <div className="status-item">
          <span className="label">手势</span>
          <span
            className="value gesture"
            style={{ color: gestureColor }}
          >
            {currentGesture.toUpperCase()}
          </span>
        </div>
      </div>

      {/* 最近事件 */}
      {lastEvent && (
        <div className="last-event">
          <span className="event-type">{lastEvent.eventType}</span>
          <span className="event-gesture">{lastEvent.gesture}</span>
        </div>
      )}

      {/* 手势提示 */}
      <div className="gesture-hints">
        <div className="hint">
          <span className="gesture-icon">🖐️</span>
          <span>张开手掌 - 激活控制</span>
        </div>
        <div className="hint">
          <span className="gesture-icon">👆</span>
          <span>指向 - 移动鼠标</span>
        </div>
        <div className="hint">
          <span className="gesture-icon">🤏</span>
          <span>捏合 - 点击</span>
        </div>
        <div className="hint">
          <span className="gesture-icon">✊</span>
          <span>握拳 - 播放/暂停</span>
        </div>
      </div>
    </div>
  )
}
