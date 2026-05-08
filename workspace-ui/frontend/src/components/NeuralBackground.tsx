import { useEffect, useRef } from 'react'

/* ─────────────────────────────────────────────────────────────────────────────
   NEURAL BACKGROUND
   Organic neural network simulation. Two neuron classes:
   - Hub neurons   (large soma, many connections, visible dendrites)
   - Leaf neurons  (small, fewer connections, clustered near hubs)
   Signals travel as action potentials along curved bezier axons.
   Color palette: amber, matching the LAIA brand.
───────────────────────────────────────────────────────────────────────────── */

interface Neuron {
  /* position — origin drifts slowly, displayed pos lerps toward origin */
  ox: number; oy: number
  x: number; y: number
  /* depth in 0…1 — affects size and opacity (parallax illusion) */
  z: number
  /* visual radius before depth scaling */
  baseR: number
  isHub: boolean
  /* firing state */
  fireAmt: number      // 0→1, decays after fired
  firePhase: number    // oscillation phase when firing
  activity: number     // recent incoming pulse memory; grows and fades over time
  pulseLoad: number    // short impact swell from very recent pulses
  outboundAmt: number  // outgoing launch ripple; expands and fades after launch
  shapeSeed: number    // stable seed for organic soma outline
  /* drift */
  driftAngle: number
  driftSpeed: number
  /* connections: indices of neighbor neurons in the array */
  neighbors: number[]
}

interface Pulse {
  from: number          // neuron index
  to: number            // neuron index
  /* bezier control point offset (normalized, applied at render) */
  cpDx: number; cpDy: number
  t: number             // 0→1 travel progress
  speed: number         // progress per ms
  /* signal color type */
  kind: 'excite' | 'inhibit' | 'warm'
  /* fade-in/out opacity */
  alpha: number
  active: boolean
  /* tail: previous positions for glow trail */
  trail: { x: number; y: number }[]
}

/* ── Palette ──────────────────────────────────────────────────────────────── */
const COL = {
  excite:  { r: 235, g: 177, b: 72  },   // muted brand amber
  inhibit: { r: 184, g: 124, b: 34  },   // deep amber
  warm:    { r: 255, g: 213, b: 128 },   // light amber flash
  teal:    { r: 245, g: 158, b: 11  },   // orange amber
  nodeBase:{ r: 118, g: 81,  b: 24  },   // node body base
  hubBase: { r: 210, g: 145, b: 46  },   // hub body
}

/* bezier point at parameter t (quadratic) */
function qBez(p0: number, p1: number, p2: number, t: number) {
  const mt = 1 - t
  return mt * mt * p0 + 2 * mt * t * p1 + t * t * p2
}

export function NeuralBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })!

    /* ── Configuración visual básica ─────────────────────────────────────────
       Sube/baja estos valores para ajustar la "vida" del fondo sin tocar
       la lógica de dibujo. Las velocidades son pequeñas porque se aplican
       por milisegundo dentro del loop de animación.
    */
    const CFG = {
      /* Cantidad de nodos */
      hubCount: 50,
      // Nodos principales: más grandes, con más conexiones.
      leafCount: 110,
      // Nodos secundarios: más pequeños, agrupados alrededor de los hubs.

      /* Conexiones */
      connDist: 200,
      // Distancia máxima para conectar nodos normales. Más alto = red más densa.
      hubConnDist: 280,
      // Distancia máxima para hubs. Más alto = hubs con enlaces más largos.
      maxNeighbors: 8,
      // Máximo de conexiones por nodo. Más alto = más líneas visibles.

      /* Pulsos */
      pulseCount: 22,
      // Reserva total de pulsos. No todos viajan a la vez.
      maxActivePulses: 9,
      // Límite real de pulsos moviéndose simultáneamente.
      pulseLaunchSpacingMs: 300,
      // Separación inicial entre lanzamientos. Más alto = arranque más calmado.
      pulseSpeedNear: 0.00016,
      // Velocidad de pulsos entre nodos cercanos.
      pulseSpeedFar: 0.00056,
      // Velocidad de pulsos entre nodos lejanos.
      pulseSpeedJitter: 0.00027,
      // Variación aleatoria de velocidad. Más alto = movimiento menos uniforme.

      /* Movimiento orgánico */
      ease: 0.014,
      // Suavidad con la que cada nodo vuelve a su posición objetivo.
      driftMax: 0.18,
      // Desplazamiento máximo de deriva. Actualmente reservado para ajuste fino.
      mouseRadius: 260,
      // Radio de influencia del cursor.
      mouseStrength: 45,
      // Fuerza con la que el cursor atrae los nodos.

      /* Decaimiento de luz/actividad */
      fireDecay: 0.0015,
      // Velocidad a la que se apaga el brillo al recibir un pulso.
      activityDecay: 0.00013,
      // Velocidad a la que un nodo pierde actividad si no recibe pulsos.
      pulseLoadDecay: 0.0028,
      // Velocidad a la que desaparece la pequeña hinchazón por impacto reciente.
      outboundDecay: 0.00085,
      // Velocidad a la que se apaga la onda suave al lanzar un pulso.
    }

    let W = 0, H = 0
    let neurons: Neuron[] = []
    let pulses: Pulse[] = []
    let rafId = 0
    let lastTime = 0
    const mouse = { x: -9999, y: -9999, active: false }

    /* ── Build neuron array ───────────────────────────────────────────────── */
    function buildNeurons() {
      neurons = []
      const total = CFG.hubCount + CFG.leafCount

      /* hubs — distributed via quasi-random grid for natural spacing */
      const cols = Math.ceil(Math.sqrt(CFG.hubCount * (W / H)))
      const rows = Math.ceil(CFG.hubCount / cols)
      let hi = 0
      for (let r = 0; r < rows && hi < CFG.hubCount; r++) {
        for (let c = 0; c < cols && hi < CFG.hubCount; c++) {
          const ox = (c + 0.3 + Math.random() * 0.4) * (W / cols)
          const oy = (r + 0.3 + Math.random() * 0.4) * (H / rows)
          const z = 0.4 + Math.random() * 0.6
          neurons.push({
            ox, oy, x: ox, y: oy, z,
            baseR: 3.2 + Math.random() * 2.1,
            isHub: true,
            fireAmt: 0, firePhase: Math.random() * Math.PI * 2,
            activity: 0.25 + Math.random() * 0.18,
            pulseLoad: 0,
            outboundAmt: 0,
            shapeSeed: Math.random() * 1000,
            driftAngle: Math.random() * Math.PI * 2,
            driftSpeed: 0.04 + Math.random() * 0.08,
            neighbors: [],
          })
          hi++
        }
      }

      /* leaves — clustered loosely around hubs */
      for (let i = 0; i < CFG.leafCount; i++) {
        const hub = neurons[Math.floor(Math.random() * CFG.hubCount)]
        const angle = Math.random() * Math.PI * 2
        const dist  = 30 + Math.random() * 160
        const ox = Math.max(10, Math.min(W - 10, hub.ox + Math.cos(angle) * dist))
        const oy = Math.max(10, Math.min(H - 10, hub.oy + Math.sin(angle) * dist))
        const z = 0.15 + Math.random() * 0.75
        neurons.push({
          ox, oy, x: ox, y: oy, z,
          baseR: 1.55 + Math.random() * 1.25,
          isHub: false,
          fireAmt: 0, firePhase: Math.random() * Math.PI * 2,
          activity: Math.random() * 0.14,
          pulseLoad: 0,
          outboundAmt: 0,
          shapeSeed: Math.random() * 1000,
          driftAngle: Math.random() * Math.PI * 2,
          driftSpeed: 0.02 + Math.random() * 0.06,
          neighbors: [],
        })
      }

      /* Connect neighbors */
      for (let i = 0; i < total; i++) {
        const a = neurons[i]
        const maxD = a.isHub ? CFG.hubConnDist : CFG.connDist
        const candidates: { idx: number; dist: number }[] = []
        for (let j = 0; j < total; j++) {
          if (i === j) continue
          const d = Math.hypot(a.ox - neurons[j].ox, a.oy - neurons[j].oy)
          if (d < maxD) candidates.push({ idx: j, dist: d })
        }
        candidates.sort((x, y) => x.dist - y.dist)
        const max = a.isHub ? CFG.maxNeighbors : Math.ceil(CFG.maxNeighbors * 0.55)
        a.neighbors = candidates.slice(0, max).map(c => c.idx)
      }
    }

    /* ── Build initial pulses ─────────────────────────────────────────────── */
    function buildPulses() {
      pulses = []
      for (let i = 0; i < CFG.pulseCount; i++) {
        pulses.push(makePulse(250 + i * CFG.pulseLaunchSpacingMs))
      }
    }

    function makePulse(delay = 0): Pulse {
      /* prefer hub sources */
      const srcPool = neurons.filter(n => n.isHub && n.neighbors.length > 0)
      const src = srcPool.length > 0
        ? srcPool[Math.floor(Math.random() * srcPool.length)]
        : neurons[Math.floor(Math.random() * neurons.length)]
      const fromIdx = neurons.indexOf(src)
      const toIdx = src.neighbors.length > 0
        ? src.neighbors[Math.floor(Math.random() * src.neighbors.length)]
        : (fromIdx + 1) % neurons.length

      /* control point: perpendicular offset for organic curve */
      const dx = neurons[toIdx].ox - src.ox
      const dy = neurons[toIdx].oy - src.oy
      const len = Math.hypot(dx, dy) || 1
      const perp = (Math.random() - 0.5) * len * 0.5
      const cpDx = dx * 0.5 - (dy / len) * perp
      const cpDy = dy * 0.5 + (dx / len) * perp
      const distanceFactor = Math.min(1, len / CFG.hubConnDist)
      const speed =
        CFG.pulseSpeedNear +
        (CFG.pulseSpeedFar - CFG.pulseSpeedNear) * distanceFactor +
        Math.random() * CFG.pulseSpeedJitter

      const roll = Math.random()
      const kind: Pulse['kind'] = roll < 0.08 ? 'warm' : roll < 0.42 ? 'inhibit' : 'excite'

      return {
        from: fromIdx, to: toIdx,
        cpDx, cpDy,
        t: delay > 0 ? -delay / 1000 : 0,
        speed,
        kind,
        alpha: 1,
        active: delay <= 0,
        trail: []
      }
    }

    function markPulseLaunch(p: Pulse) {
      const src = neurons[p.from]
      if (!src) return
      src.outboundAmt = 1
      src.activity = Math.min(1.6, src.activity + 0.08)
      src.pulseLoad = Math.min(1, src.pulseLoad + 0.16)
    }

    /* ── Update ───────────────────────────────────────────────────────────── */
    function update(dt: number) {
      for (const n of neurons) {
        /* slow organic drift */
        n.driftAngle += 0.002 * (0.5 - Math.random() * 0.15)
        n.ox += Math.cos(n.driftAngle) * n.driftSpeed
        n.oy += Math.sin(n.driftAngle) * n.driftSpeed
        /* keep in bounds with soft bounce */
        if (n.ox < 20)      { n.driftAngle = 0;          n.ox = 20 }
        if (n.ox > W - 20)  { n.driftAngle = Math.PI;    n.ox = W - 20 }
        if (n.oy < 20)      { n.driftAngle = Math.PI / 2; n.oy = 20 }
        if (n.oy > H - 20)  { n.driftAngle = -Math.PI / 2; n.oy = H - 20 }

        /* mouse attraction */
        let tx = n.ox, ty = n.oy
        if (mouse.active) {
          const mdx = mouse.x - n.ox, mdy = mouse.y - n.oy
          const md = Math.hypot(mdx, mdy)
          if (md < CFG.mouseRadius) {
            const str = (1 - md / CFG.mouseRadius) * CFG.mouseStrength * n.z
            tx = n.ox + (mdx / md) * str
            ty = n.oy + (mdy / md) * str
          }
        }
        n.x += (tx - n.x) * CFG.ease
        n.y += (ty - n.y) * CFG.ease

        /* fire decay */
        if (n.fireAmt > 0) {
          n.fireAmt = Math.max(0, n.fireAmt - CFG.fireDecay * dt)
        }
        n.activity = Math.max(0, n.activity - CFG.activityDecay * dt)
        n.pulseLoad = Math.max(0, n.pulseLoad - CFG.pulseLoadDecay * dt)
        n.outboundAmt = Math.max(0, n.outboundAmt - CFG.outboundDecay * dt)
        n.firePhase += 0.012 + n.activity * 0.025
      }

      /* pulses */
      let activePulses = pulses.reduce(
        (count, pulse) => count + (pulse.active && pulse.t >= 0 && pulse.t <= 1 ? 1 : 0),
        0,
      )
      for (let i = 0; i < pulses.length; i++) {
        const p = pulses[i]
        if (!p.active) {
          p.t += p.speed * dt
          if (p.t >= 0) {
            if (activePulses < CFG.maxActivePulses) {
              p.t = 0
              p.active = true
              activePulses++
              markPulseLaunch(p)
            } else {
              p.t = -(250 + Math.random() * 500) / 1000
            }
          }
          continue
        }
        const prevT = p.t
        p.t += p.speed * dt
        if (prevT <= 0 && p.t > 0) markPulseLaunch(p)

        /* store trail (every ~4 frames worth of t) */
        const src = neurons[p.from], tgt = neurons[p.to]
        const cpX = src.x + p.cpDx, cpY = src.y + p.cpDy
        const px = qBez(src.x, cpX, tgt.x, p.t)
        const py = qBez(src.y, cpY, tgt.y, p.t)
        if (p.trail.length === 0 || Math.hypot(px - p.trail[p.trail.length - 1].x, py - p.trail[p.trail.length - 1].y) > 3) {
          p.trail.push({ x: px, y: py })
          if (p.trail.length > 18) p.trail.shift()
        }

        if (p.t >= 1) {
          /* fire target neuron */
          const tgtN = neurons[p.to]
          const incoming = p.kind === 'warm' ? 0.38 : p.kind === 'excite' ? 0.28 : 0.2
          tgtN.activity = Math.min(1.6, tgtN.activity + incoming)
          tgtN.pulseLoad = Math.min(1, tgtN.pulseLoad + incoming * 1.2)
          tgtN.fireAmt = Math.max(tgtN.fireAmt, 1.0)
          tgtN.firePhase = 0
          /* respawn pulse */
          pulses[i] = makePulse(700 + Math.random() * 1600)
          activePulses = Math.max(0, activePulses - 1)
        }
      }
    }

    function drawOrganicBlob(
      x: number,
      y: number,
      r: number,
      seed: number,
      phase: number,
      activity: number,
    ) {
      const points = 12
      const wobble = 0.025 + activity * 0.035
      const verts: { x: number; y: number }[] = []

      for (let i = 0; i < points; i++) {
        const a = (i / points) * Math.PI * 2
        const wave =
          Math.sin(seed + i * 1.73 + phase) * 0.55 +
          Math.sin(seed * 0.7 + i * 2.41 - phase * 0.7) * 0.35
        const rr = r * (1 + wave * wobble)
        verts.push({ x: x + Math.cos(a) * rr, y: y + Math.sin(a) * rr })
      }

      ctx.beginPath()
      const first = verts[0]
      const last = verts[verts.length - 1]
      ctx.moveTo((last.x + first.x) / 2, (last.y + first.y) / 2)
      for (let i = 0; i < verts.length; i++) {
        const current = verts[i]
        const next = verts[(i + 1) % verts.length]
        ctx.quadraticCurveTo(current.x, current.y, (current.x + next.x) / 2, (current.y + next.y) / 2)
      }
      ctx.closePath()
    }

    /* ── Draw ─────────────────────────────────────────────────────────────── */
    function draw() {
      ctx.clearRect(0, 0, W, H)

      /* ambient depth fog */
      const fog = ctx.createRadialGradient(W * 0.4, H * 0.35, 0, W * 0.5, H * 0.5, Math.max(W, H) * 0.7)
      fog.addColorStop(0, 'rgba(20, 60, 100, 0.018)')
      fog.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = fog
      ctx.fillRect(0, 0, W, H)

      /* ── Axon connections ── */
      for (let i = 0; i < neurons.length; i++) {
        const a = neurons[i]
        for (const j of a.neighbors) {
          if (j <= i) continue
          const b = neurons[j]
          const dist = Math.hypot(a.x - b.x, a.y - b.y)
          const maxD = a.isHub || b.isHub ? CFG.hubConnDist : CFG.connDist
          if (dist > maxD) continue
          const strength = (1 - dist / maxD)
          const alpha = strength * 0.09 * ((a.z + b.z) / 2)
          /* slight bezier curve on axons too */
          const mx = (a.x + b.x) / 2 + (Math.random() - 0.5) * 4
          const my = (a.y + b.y) / 2 + (Math.random() - 0.5) * 4
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.quadraticCurveTo(mx, my, b.x, b.y)
          /* gradient: amber to deep amber */
          const grad = ctx.createLinearGradient(a.x, a.y, b.x, b.y)
          grad.addColorStop(0, `rgba(${COL.excite.r},${COL.excite.g},${COL.excite.b},${alpha})`)
          grad.addColorStop(1, `rgba(${COL.inhibit.r},${COL.inhibit.g},${COL.inhibit.b},${alpha * 0.7})`)
          ctx.strokeStyle = grad
          ctx.lineWidth = a.isHub || b.isHub ? 0.8 : 0.5
          ctx.stroke()
        }
      }

      /* ── Neuron bodies ── */
      for (const n of neurons) {
        const baseR = n.baseR * (0.5 + n.z * 0.5)
        const activity = Math.min(1, n.activity)
        const swell = activity * (n.isHub ? 0.22 : 0.28) + n.pulseLoad * 0.07
        const breath = 1 + Math.sin(n.firePhase + n.shapeSeed) * (0.01 + activity * 0.012)
        const r = baseR * (1 + swell) * breath
        const idleAlpha = n.isHub ? 0.12 + n.z * 0.12 : 0.05 + n.z * 0.1
        const coreAlpha = Math.min(0.95, idleAlpha + activity * 0.5 + n.fireAmt * 0.22)

        /* outgoing launch wave */
        if (n.outboundAmt > 0.01) {
          const age = 1 - n.outboundAmt
          const c = n.isHub ? COL.hubBase : COL.warm
          const waveR = r * (1.05 + age * 1.75)
          const waveGrad = ctx.createRadialGradient(n.x, n.y, r * 0.65, n.x, n.y, waveR)
          waveGrad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},${0.08 * n.outboundAmt})`)
          waveGrad.addColorStop(0.52, `rgba(${c.r},${c.g},${c.b},${0.045 * n.outboundAmt})`)
          waveGrad.addColorStop(1, 'rgba(0,0,0,0)')
          drawOrganicBlob(n.x, n.y, waveR, n.shapeSeed + 23, n.firePhase * 0.25, activity * 0.5)
          ctx.fillStyle = waveGrad
          ctx.fill()
        }

        /* fire glow */
        if (n.fireAmt > 0.01 || activity > 0.04) {
          const fi = Math.max(n.fireAmt, activity * 0.55) * (0.7 + 0.3 * Math.sin(n.firePhase))
          const glowR = r * (1.8 + 3.2 * fi)
          const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, glowR)
          const c = n.isHub ? COL.hubBase : COL.excite
          grad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},${0.42 * fi})`)
          grad.addColorStop(0.45, `rgba(${c.r},${c.g},${c.b},${0.14 * fi})`)
          grad.addColorStop(1, 'rgba(0,0,0,0)')
          drawOrganicBlob(n.x, n.y, glowR, n.shapeSeed, n.firePhase * 0.45, activity)
          ctx.fillStyle = grad
          ctx.fill()
        }

        /* soma core: irregular membrane that grows with recent incoming pulses */
        const c = n.isHub ? COL.hubBase : COL.warm
        drawOrganicBlob(n.x, n.y, r, n.shapeSeed, n.firePhase, activity)
        ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${coreAlpha})`
        ctx.fill()

        /* soft inner nucleus */
        if (n.isHub || activity > 0.2) {
          drawOrganicBlob(n.x, n.y, r * (n.isHub ? 0.42 : 0.34), n.shapeSeed + 17, -n.firePhase * 0.8, activity)
          ctx.fillStyle = `rgba(255, 229, 178, ${0.06 + activity * 0.24 + n.fireAmt * 0.14})`
          ctx.fill()
        }
      }

      /* ── Action potential pulses ── */
      for (const p of pulses) {
        if (!p.active || p.t < 0 || p.t > 1) continue
        const src = neurons[p.from], tgt = neurons[p.to]
        const cpX = src.x + p.cpDx, cpY = src.y + p.cpDy

        const px = qBez(src.x, cpX, tgt.x, p.t)
        const py = qBez(src.y, cpY, tgt.y, p.t)

        const col = COL[p.kind]
        const depthA = 0.5 + (src.z + tgt.z) * 0.25

        /* glowing trail */
        if (p.trail.length >= 2) {
          for (let ti = 1; ti < p.trail.length; ti++) {
            const ta = (ti / p.trail.length)
            const trailAlpha = ta * ta * 0.55 * depthA
            const trailW = 1.5 * ta
            ctx.beginPath()
            ctx.moveTo(p.trail[ti - 1].x, p.trail[ti - 1].y)
            ctx.lineTo(p.trail[ti].x, p.trail[ti].y)
            ctx.strokeStyle = `rgba(${col.r},${col.g},${col.b},${trailAlpha})`
            ctx.lineWidth = trailW
            ctx.stroke()
          }
        }

        /* pulse head — outer glow */
        const headGrad = ctx.createRadialGradient(px, py, 0, px, py, 7)
        headGrad.addColorStop(0, `rgba(${col.r},${col.g},${col.b},${0.7 * depthA})`)
        headGrad.addColorStop(0.4, `rgba(${col.r},${col.g},${col.b},${0.2 * depthA})`)
        headGrad.addColorStop(1, 'rgba(0,0,0,0)')
        ctx.beginPath()
        ctx.arc(px, py, 7, 0, Math.PI * 2)
        ctx.fillStyle = headGrad
        ctx.fill()

        /* pulse head — bright core */
        ctx.beginPath()
        ctx.arc(px, py, 2, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(255,255,255,${0.85 * depthA})`
        ctx.fill()
      }
    }

    /* ── Resize ───────────────────────────────────────────────────────────── */
    function resize() {
      W = canvas!.width = window.innerWidth
      H = canvas!.height = window.innerHeight
      buildNeurons()
      buildPulses()
    }

    /* ── Animation loop ───────────────────────────────────────────────────── */
    function loop(time: number) {
      const dt = Math.min(time - lastTime, 48) // cap dt to ~2 frames
      lastTime = time
      update(dt)
      draw()
      rafId = requestAnimationFrame(loop)
    }

    resize()
    rafId = requestAnimationFrame(t => { lastTime = t; loop(t) })

    const onResize = () => resize()
    const onMove = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true }
    const onOut  = () => { mouse.active = false }

    window.addEventListener('resize', onResize)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseout', onOut)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseout', onOut)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0, left: 0,
        width: '100%', height: '100%',
        zIndex: -1,
        pointerEvents: 'none',
        background: '#000',
      }}
    />
  )
}
