/**
 * 手部 3D 可视化组件
 * 使用 React Three Fiber 渲染手部骨骼和特效
 */

import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line, Trail } from '@react-three/drei'
import * as THREE from 'three'

import { useHandStore } from '../stores/handStore'
import { HAND_CONNECTIONS, FINGER_TIPS, GESTURE_COLORS } from '../types'

// 单手渲染组件
function Hand({ side }: { side: 'left' | 'right' }) {
  const groupRef = useRef<THREE.Group>(null)
  const lineRefs = useRef<THREE.Line[]>([])
  const pointRefs = useRef<THREE.Mesh[]>([])

  // 获取手部数据的方法
  const getHand = side === 'left'
    ? useHandStore.getState().getLeftHand
    : useHandStore.getState().getRightHand

  // 初始化点的位置
  const initialPoints = useMemo(() => {
    return Array(21).fill(null).map(() => new THREE.Vector3(0, 0, 0))
  }, [])

  // 颜色状态
  const colorRef = useRef(new THREE.Color('#00ffff'))

  // 每帧更新
  useFrame(() => {
    const hand = getHand()

    if (!hand || !groupRef.current) {
      // 没有检测到手，隐藏
      if (groupRef.current) {
        groupRef.current.visible = false
      }
      return
    }

    groupRef.current.visible = true

    // 更新颜色
    const targetColor = GESTURE_COLORS[hand.gesture] || '#00ffff'
    colorRef.current.lerp(new THREE.Color(targetColor), 0.1)

    // 更新关键点位置
    hand.landmarks.forEach((pos, i) => {
      if (pointRefs.current[i]) {
        pointRefs.current[i].position.copy(pos)

        // 指尖用不同颜色
        const material = pointRefs.current[i].material as THREE.MeshBasicMaterial
        if (FINGER_TIPS.includes(i)) {
          material.color.set('#00ff88')
        } else {
          material.color.copy(colorRef.current)
        }
      }
    })
  })

  return (
    <group ref={groupRef} visible={false}>
      {/* 骨骼连线 */}
      {HAND_CONNECTIONS.map(([start, end], index) => (
        <HandBone
          key={`bone-${index}`}
          startIndex={start}
          endIndex={end}
          side={side}
          colorRef={colorRef}
        />
      ))}

      {/* 关键点 */}
      {initialPoints.map((_, index) => (
        <mesh
          key={`point-${index}`}
          ref={(ref) => {
            if (ref) pointRefs.current[index] = ref
          }}
        >
          <sphereGeometry args={[FINGER_TIPS.includes(index) ? 0.025 : 0.015, 16, 16]} />
          <meshBasicMaterial color="#00ffff" />
        </mesh>
      ))}

      {/* 指尖拖尾效果 */}
      {FINGER_TIPS.map((tipIndex) => (
        <FingerTrail
          key={`trail-${tipIndex}`}
          fingerIndex={tipIndex}
          side={side}
        />
      ))}
    </group>
  )
}

// 骨骼连线组件
function HandBone({
  startIndex,
  endIndex,
  side,
  colorRef
}: {
  startIndex: number
  endIndex: number
  side: 'left' | 'right'
  colorRef: React.MutableRefObject<THREE.Color>
}) {
  const lineRef = useRef<THREE.Line>(null)

  const getHand = side === 'left'
    ? useHandStore.getState().getLeftHand
    : useHandStore.getState().getRightHand

  // 线条几何体
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const positions = new Float32Array(6) // 2 points * 3 coords
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    return geo
  }, [])

  useFrame(() => {
    const hand = getHand()
    if (!hand || !lineRef.current) return

    const positions = geometry.attributes.position.array as Float32Array
    const start = hand.landmarks[startIndex]
    const end = hand.landmarks[endIndex]

    positions[0] = start.x
    positions[1] = start.y
    positions[2] = start.z
    positions[3] = end.x
    positions[4] = end.y
    positions[5] = end.z

    geometry.attributes.position.needsUpdate = true

    // 更新颜色
    const material = lineRef.current.material as THREE.LineBasicMaterial
    material.color.copy(colorRef.current)
  })

  return (
    <line ref={lineRef} geometry={geometry}>
      <lineBasicMaterial color="#00ffff" linewidth={2} />
    </line>
  )
}

// 指尖拖尾组件
function FingerTrail({
  fingerIndex,
  side
}: {
  fingerIndex: number
  side: 'left' | 'right'
}) {
  const meshRef = useRef<THREE.Mesh>(null)

  const getHand = side === 'left'
    ? useHandStore.getState().getLeftHand
    : useHandStore.getState().getRightHand

  useFrame(() => {
    const hand = getHand()
    if (!hand || !meshRef.current) return

    const pos = hand.landmarks[fingerIndex]
    meshRef.current.position.copy(pos)
  })

  return (
    <Trail
      width={1}
      length={6}
      color="#ff00ff"
      attenuation={(t) => t * t}
    >
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.01, 8, 8]} />
        <meshBasicMaterial color="#ff00ff" transparent opacity={0} />
      </mesh>
    </Trail>
  )
}

// 背景粒子效果
function BackgroundParticles() {
  const particlesRef = useRef<THREE.Points>(null)

  const particleCount = 200
  const positions = useMemo(() => {
    const pos = new Float32Array(particleCount * 3)
    for (let i = 0; i < particleCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 4
      pos[i * 3 + 1] = (Math.random() - 0.5) * 4
      pos[i * 3 + 2] = (Math.random() - 0.5) * 2
    }
    return pos
  }, [])

  useFrame((state) => {
    if (!particlesRef.current) return

    // 缓慢旋转
    particlesRef.current.rotation.y = state.clock.elapsedTime * 0.02
    particlesRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.01) * 0.1
  })

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particleCount}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.02}
        color="#00ffff"
        transparent
        opacity={0.3}
        sizeAttenuation
      />
    </points>
  )
}

// 主可视化组件
export function HandVisualization() {
  return (
    <group>
      {/* 背景粒子 */}
      <BackgroundParticles />

      {/* 左手 */}
      <Hand side="left" />

      {/* 右手 */}
      <Hand side="right" />
    </group>
  )
}
