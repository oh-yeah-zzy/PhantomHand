/**
 * Camera Preview Component
 * Displays MJPEG stream from backend in a small draggable window
 */

import { useState, useRef, useEffect } from 'react'

interface CameraPreviewProps {
  streamUrl?: string
}

export function CameraPreview({ streamUrl = 'http://127.0.0.1:8766/stream' }: CameraPreviewProps) {
  const [isMinimized, setIsMinimized] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [position, setPosition] = useState({ x: 20, y: 20 })
  const [isDragging, setIsDragging] = useState(false)
  const dragOffset = useRef({ x: 0, y: 0 })

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    // Only drag from header
    if ((e.target as HTMLElement).classList.contains('preview-header')) {
      setIsDragging(true)
      dragOffset.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y
      }
    }
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        setPosition({
          x: e.clientX - dragOffset.current.x,
          y: e.clientY - dragOffset.current.y
        })
      }
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  const handleRetry = () => {
    setHasError(false)
  }

  return (
    <div
      className="camera-preview"
      style={{
        left: position.x,
        top: position.y
      }}
      onMouseDown={handleMouseDown}
    >
      <div className="preview-header">
        <span className="preview-title">Camera</span>
        <button
          className="preview-toggle"
          onClick={() => setIsMinimized(!isMinimized)}
        >
          {isMinimized ? '+' : '-'}
        </button>
      </div>

      {!isMinimized && (
        <div className="preview-content">
          {hasError ? (
            <div className="preview-error">
              <span>Stream unavailable</span>
              <button onClick={handleRetry}>Retry</button>
            </div>
          ) : (
            <img
              src={streamUrl}
              alt="Camera Preview"
              onError={() => setHasError(true)}
            />
          )}
        </div>
      )}
    </div>
  )
}
