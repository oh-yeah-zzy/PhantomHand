/**
 * PhantomHand 主应用组件
 */

import { useEffect } from 'react'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom } from '@react-three/postprocessing'

import { HandVisualization } from './canvas/HandVisualization'
import { StatusPanel } from './components/StatusPanel'
import { ControlPanel } from './components/ControlPanel'
import { CameraPreview } from './components/CameraPreview'
import { useHandStore } from './stores/handStore'

function App() {
  const { connect, disconnect, isConnected } = useHandStore()

  // 连接 WebSocket
  useEffect(() => {
    connect('ws://127.0.0.1:8765')

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return (
    <div className="app-container">
      {/* 3D 可视化画布 */}
      <Canvas
        camera={{ position: [0, 0, 2], fov: 50 }}
        style={{ background: '#0a0a0f' }}
      >
        {/* 环境光 */}
        <ambientLight intensity={0.2} />
        <pointLight position={[10, 10, 10]} intensity={0.5} />

        {/* 手部可视化 */}
        <HandVisualization />

        {/* 后处理效果 - 发光 */}
        <EffectComposer>
          <Bloom
            intensity={1.5}
            luminanceThreshold={0.1}
            luminanceSmoothing={0.9}
          />
        </EffectComposer>
      </Canvas>

      {/* UI 覆盖层 */}
      <div className="ui-overlay">
        {/* 状态面板 */}
        <StatusPanel />

        {/* 控制面板 */}
        <ControlPanel />

        {/* 摄像头预览 */}
        <CameraPreview />

        {/* 连接状态指示器 */}
        <div className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          <span className="dot" />
          <span className="text">
            {isConnected ? '已连接' : '未连接'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default App
