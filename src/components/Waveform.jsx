import { useEffect, useRef, useState } from 'react'
import { computePeaks } from '../lib/audio'

const HANDLE_WIDTH = 28

export default function Waveform({ audioBuffer, start, end, onChange }) {
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const [width, setWidth] = useState(300)
  const duration = audioBuffer.duration

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      setWidth(entries[0].contentRect.width)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || width === 0) return
    const dpr = window.devicePixelRatio || 1
    const height = 120
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, width, height)

    const peaks = computePeaks(audioBuffer, Math.max(1, Math.floor(width)))
    const mid = height / 2
    ctx.fillStyle = '#94a3b8'
    peaks.forEach(([min, max], i) => {
      const y1 = mid + min * mid
      const y2 = mid + max * mid
      ctx.fillRect(i, y1, 1, Math.max(1, y2 - y1))
    })

    const startX = (start / duration) * width
    const endX = (end / duration) * width
    ctx.fillStyle = 'rgba(99, 102, 241, 0.25)'
    ctx.fillRect(startX, 0, endX - startX, height)
  }, [audioBuffer, width, start, end, duration])

  function beginDrag(which) {
    return (pointerDownEvent) => {
      pointerDownEvent.preventDefault()
      const container = containerRef.current
      const rect = container.getBoundingClientRect()

      function handleMove(e) {
        const clientX = e.touches ? e.touches[0].clientX : e.clientX
        const x = Math.min(rect.width, Math.max(0, clientX - rect.left))
        const t = (x / rect.width) * duration
        if (which === 'start') {
          onChange(Math.min(t, end - 0.1), end)
        } else {
          onChange(start, Math.max(t, start + 0.1))
        }
      }
      function handleUp() {
        window.removeEventListener('pointermove', handleMove)
        window.removeEventListener('pointerup', handleUp)
      }
      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', handleUp)
    }
  }

  const startPct = (start / duration) * 100
  const endPct = (end / duration) * 100

  return (
    <div className="waveform" ref={containerRef}>
      <canvas ref={canvasRef} />
      <div
        className="waveform-handle waveform-handle-start"
        style={{ left: `calc(${startPct}% - ${HANDLE_WIDTH / 2}px)`, width: HANDLE_WIDTH }}
        onPointerDown={beginDrag('start')}
      >
        <span />
      </div>
      <div
        className="waveform-handle waveform-handle-end"
        style={{ left: `calc(${endPct}% - ${HANDLE_WIDTH / 2}px)`, width: HANDLE_WIDTH }}
        onPointerDown={beginDrag('end')}
      >
        <span />
      </div>
    </div>
  )
}
