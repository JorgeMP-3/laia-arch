// Renders the LaiaNeuralAvatar canvas logic to a 1024x1024 PNG icon
import { createCanvas } from 'canvas'
import { writeFileSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SIZE = 1024
const canvas = createCanvas(SIZE, SIZE)
const ctx = canvas.getContext('2d')

const cx = SIZE / 2
const cy = SIZE / 2

// Same STATE_CONFIG as the React component — idle state
const config = { speed: 0.4, nodeCount: 7, radius: 0.52 }

// t = a nice mid-animation moment
const t = 1.2

// ── Background — full black square, no clip ───────────────────────────────────
const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, SIZE * 0.7)
bg.addColorStop(0, 'rgba(30,20,5,1)')
bg.addColorStop(1, 'rgba(0,0,0,1)')
ctx.fillStyle = bg
ctx.fillRect(0, 0, SIZE, SIZE)

// ── Node positions ────────────────────────────────────────────────────────────
const r = (SIZE / 2) * config.radius
const nodes = []
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

// ── Edges ─────────────────────────────────────────────────────────────────────
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
    ctx.lineWidth = 2.5
    ctx.stroke()
  }
}

// ── Peripheral nodes ──────────────────────────────────────────────────────────
nodes.forEach((n) => {
  const pulse = 0.7 + Math.sin(t * 2.2 + n.phase) * 0.3
  const nr = (SIZE * 0.045) * pulse

  const grd = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, nr * 3)
  grd.addColorStop(0, `rgba(255,210,80,${0.5 * pulse})`)
  grd.addColorStop(1, 'rgba(255,196,90,0)')
  ctx.beginPath()
  ctx.arc(n.x, n.y, nr * 3, 0, Math.PI * 2)
  ctx.fillStyle = grd
  ctx.fill()

  ctx.beginPath()
  ctx.arc(n.x, n.y, nr, 0, Math.PI * 2)
  ctx.fillStyle = `rgba(255,220,100,${0.85 * pulse})`
  ctx.fill()
})

// ── Center node ───────────────────────────────────────────────────────────────
const centerPulse = 0.8 + Math.sin(t * 1.4) * 0.2
const cr = SIZE * 0.065 * centerPulse

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

// ── Save ──────────────────────────────────────────────────────────────────────
const outDir = join(__dirname, '../src-tauri/icons')
mkdirSync(outDir, { recursive: true })
const outPath = join(outDir, 'app-icon-source.png')
writeFileSync(outPath, canvas.toBuffer('image/png'))
console.log(`Icon saved to ${outPath}`)
