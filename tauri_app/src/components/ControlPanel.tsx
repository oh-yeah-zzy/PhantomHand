/**
 * 控制面板组件
 * 提供手动控制选项
 */

import { useState } from 'react'
import { useHandStore } from '../stores/handStore'

export function ControlPanel() {
  const { isActive, setActive, isConnected } = useHandStore()
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`control-panel ${expanded ? 'expanded' : ''}`}>
      {/* 展开/收起按钮 */}
      <button
        className="toggle-btn"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? '收起' : '设置'}
      </button>

      {expanded && (
        <div className="panel-content">
          {/* 激活控制 */}
          <div className="control-item">
            <label>手势控制</label>
            <button
              className={`toggle-switch ${isActive ? 'on' : 'off'}`}
              onClick={() => setActive(!isActive)}
              disabled={!isConnected}
            >
              {isActive ? 'ON' : 'OFF'}
            </button>
          </div>

          {/* 灵敏度调节 */}
          <div className="control-item">
            <label>鼠标灵敏度</label>
            <input
              type="range"
              min="0.5"
              max="3"
              step="0.1"
              defaultValue="1.5"
              className="slider"
            />
          </div>

          {/* 视觉效果 */}
          <div className="control-item">
            <label>发光强度</label>
            <input
              type="range"
              min="0"
              max="3"
              step="0.1"
              defaultValue="1.5"
              className="slider"
            />
          </div>

          {/* 重置按钮 */}
          <button className="reset-btn">
            重置设置
          </button>
        </div>
      )}
    </div>
  )
}
