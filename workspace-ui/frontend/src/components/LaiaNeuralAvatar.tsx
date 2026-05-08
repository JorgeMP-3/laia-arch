/**
 * LaiaNeuralAvatar
 *
 * Animated avatar for the Laia assistant.
 * Currently a minimal placeholder — replace the canvas drawing logic
 * inside `draw()` with your full organic neural-cluster animation.
 *
 * Props:
 *   size     — diameter in px (default 28)
 *   state    — 'idle' | 'thinking' | 'streaming'
 *              idle:      slow gentle pulse
 *              thinking:  faster, tighter oscillation (agent processing)
 *              streaming: smooth outward expansion (text flowing)
 *
 * To implement the full animation, edit only the section marked
 * ── ANIMATION CORE ── below. The component contract (props, sizing,
 * cleanup) stays the same.
 */

import { useEffect, useRef } from 'react'

export type AvatarState = 'idle' | 'thinking' | 'streaming'

interface LaiaNeuralAvatarProps {
  size?: number
  state?: AvatarState
}

// ─────────────────────────────────────────────────────────────────────────────
// Config per state — tweak or extend when you replace the animation core
// ─────────────────────────────────────────────────────────────────────────────
const STATE_CONFIG: Record<AvatarState, {
  speed: number       // animation speed multiplier
  nodeCount: number   // number of nodes in the cluster
  radius: number      // cluster radius (0–1, relative to canvas half)
  glow: string        // ambient glow color
}> = {
  idle:      { speed: 0.4,  nodeCount: 7,  radius: 0.52, glow: 'rgba(255,196,90,0.25)' },
  thinking:  { speed: 1.6,  nodeCount: 11, radius: 0.44, glow: 'rgba(255,140,30,0.40)' },
  streaming: { speed: 0.9,  nodeCount: 9,  radius: 0.60, glow: 'rgba(255,220,100,0.35)' },
}

export function LaiaNeuralAvatar({ size = 28, state = 'idle' }: LaiaNeuralAvatarProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)
  const tRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio ?? 1, 2)
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const cx = size / 2
    const cy = size / 2

    // ── ANIMATION CORE ────────────────────────────────────────────────────────
    // Replace everything inside this section with your organic neural-cluster
    // animation. The variables `cx`, `cy`, `size`, `config` and `t` are
    // available. `t` is time in seconds, scaled by config.speed.
    //
    // Suggested approach for the full animation:
    //   - Spawn N nodes with (x, y) positions drifting via Perlin/simplex noise
    //   - Draw edges between nodes closer than a threshold distance
    //   - Vary edge opacity by distance
    //   - Pulse node radii with sin(t + phase_offset)
    //   - In 'thinking' state: tighten cluster + increase edge flicker
    //   - In 'streaming' state: expand radius + add outward particle drift
    // ─────────────────────────────────────────────────────────────────────────

    function draw(timestamp: number) {
      const config = STATE_CONFIG[state]
      tRef.current = timestamp
      const elapsed = timestamp / 1000

      ctx.clearRect(0, 0, size, size)

      // Clip to circle
      ctx.save()
      ctx.beginPath()
      ctx.arc(cx, cy, size / 2, 0, Math.PI * 2)
      ctx.clip()

      // Background
      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2)
      bg.addColorStop(0, 'rgba(30,20,5,1)')
      bg.addColorStop(1, 'rgba(10,8,2,1)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, size, size)

      const t = elapsed * config.speed
      const r = (size / 2) * config.radius

      // Build node positions
      const nodes: { x: number; y: number; phase: number }[] = []
      for (let i = 0; i < config.nodeCount; i++) {
        const baseAngle = (i / config.nodeCount) * Math.PI * 2
        const wobble = Math.sin(t * 1.1 + i * 2.3) * 0.18
        const angle = baseAngle + wobble
        const radiusNoise = 1 + Math.sin(t * 0.7 + i * 1.7) * 0.15
        nodes.push({
          x: cx + Math.cos(angle) * r * radiusNoise,
          y: cy + Math.sin(angle) * r * radiusNoise,
          phase: i * (Math.PI * 2 / config.nodeCount),
        })
      }

      // Draw edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist > r * 1.4) continue
          const alpha = (1 - dist / (r * 1.4)) * 0.55
          const pulse = 0.6 + Math.sin(t * 1.8 + i + j) * 0.4
          ctx.beginPath()
          ctx.moveTo(nodes[i].x, nodes[i].y)
          ctx.lineTo(nodes[j].x, nodes[j].y)
          ctx.strokeStyle = `rgba(255,196,90,${alpha * pulse})`
          ctx.lineWidth = 0.6
          ctx.stroke()
        }
      }

      // Draw nodes
      nodes.forEach((n, _i) => {
        const pulse = 0.7 + Math.sin(t * 2.2 + n.phase) * 0.3
        const nr = (size * 0.045) * pulse

        // Glow
        const grd = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, nr * 3)
        grd.addColorStop(0, `rgba(255,210,80,${0.5 * pulse})`)
        grd.addColorStop(1, 'rgba(255,196,90,0)')
        ctx.beginPath()
        ctx.arc(n.x, n.y, nr * 3, 0, Math.PI * 2)
        ctx.fillStyle = grd
        ctx.fill()

        // Core dot
        ctx.beginPath()
        ctx.arc(n.x, n.y, nr, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255,220,100,${0.85 * pulse})`
        ctx.fill()
      })

      // Center node — always present
      const centerPulse = 0.8 + Math.sin(t * 1.4) * 0.2
      const cr = size * 0.065 * centerPulse
      const cgrd = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr * 4)
      cgrd.addColorStop(0, 'rgba(255,230,120,0.7)')
      cgrd.addColorStop(1, 'rgba(255,196,90,0)')
      ctx.beginPath()
      ctx.arc(cx, cy, cr * 4, 0, Math.PI * 2)
      ctx.fillStyle = cgrd
      ctx.fill()
      ctx.beginPath()
      ctx.arc(cx, cy, cr, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(255,235,130,0.95)'
      ctx.fill()

      ctx.restore()

      rafRef.current = requestAnimationFrame(draw)
    }

    // ── END ANIMATION CORE ────────────────────────────────────────────────────

    tRef.current = performance.now()
    rafRef.current = requestAnimationFrame(draw)

    return () => cancelAnimationFrame(rafRef.current)
  }, [size, state])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, borderRadius: '50%', display: 'block' }}
    />
  )
}
