// AGORA · Neural background — organic canvas simulation.
// Hubs + leaves, curved axons, action-potential pulses with trails.
// Color reads from --acc at runtime, so it follows the brand tweak.

(function () {
  function NeuralBg() {
    const canvasRef = React.useRef(null);

    React.useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d", { alpha: true });

      const CFG = {
        hubCount: 28,
        leafCount: 78,
        connDist: 180,
        hubConnDist: 260,
        // Hard caps so the canvas doesn't read as a spider web
        hubMaxNeighbors: 4,
        leafMaxNeighbors: 2,
        pulseCount: 34,
        maxActivePulses: 14,
        pulseLaunchSpacingMs: 380,
        pulseSpeedNear: 0.000055,
        pulseSpeedFar: 0.00018,
        pulseSpeedJitter: 0.00009,
        ease: 0.008,
        mouseRadius: 260,
        mouseStrength: 38,
        fireDecay: 0.00045,
        activityDecay: 0.00009,
        pulseLoadDecay: 0.0018,
        outboundDecay: 0.00038,
      };

      let edges = []; // [{ a, b, cp1, cp2, len }]  cubic Bezier offsets
      let edgeIdx = new Map(); // "a-b" -> edges index

      let W = 0, H = 0;
      let neurons = [];
      let pulses = [];
      let rafId = 0;
      let lastTime = 0;
      const mouse = { x: -9999, y: -9999, active: false };

      function hexToRGB(v) {
        if (!v) return null;
        v = String(v).trim();
        if (!v.startsWith("#")) return null;
        const hex = v.replace("#", "");
        const h = hex.length === 3
          ? hex.split("").map(c => c + c).join("")
          : hex;
        if (!/^[0-9a-fA-F]{6}$/.test(h.slice(0, 6))) return null;
        const num = parseInt(h.slice(0, 6), 16);
        return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
      }
      // read accent color (rgb) from CSS var
      function getAccentRGB() {
        const cs = getComputedStyle(document.documentElement);
        return hexToRGB(cs.getPropertyValue("--acc").trim()) || { r: 255, g: 90, b: 60 };
      }
      // optional override for the pulse/energy color
      function getPulseRGB() {
        const cs = getComputedStyle(document.documentElement);
        return hexToRGB(cs.getPropertyValue("--pulse-color").trim());
      }
      // shade helper
      function shade(c, amt) {
        const v = (n) => Math.max(0, Math.min(255, Math.round(n + amt)));
        return { r: v(c.r), g: v(c.g), b: v(c.b) };
      }
      function lighten(c, amt) {
        const mix = (n) => Math.round(n + (255 - n) * amt);
        return { r: mix(c.r), g: mix(c.g), b: mix(c.b) };
      }
      let COL;
      function refreshPalette() {
        const a = getAccentRGB();
        const p = getPulseRGB();
        // ENERGY = the dominant color of the network. Pulse override wins;
        // otherwise we follow the brand accent. Everything (nodes, edges,
        // pulses, halos) is derived from this single hue so the network
        // reads as one organism.
        const energy = p || a;
        COL = {
          excite:   energy,
          inhibit:  shade(energy, -30),
          warm:     lighten(energy, 0.45),
          nodeBase: shade(energy, -110),
          hubBase:  shade(energy, -30),
        };
      }
      refreshPalette();
      // observe accent changes (style attr on <html>)
      const obs = new MutationObserver(refreshPalette);
      obs.observe(document.documentElement, { attributes: true, attributeFilter: ["style", "data-mode"] });

      function qBez(p0, p1, p2, t) {
        const mt = 1 - t;
        return mt * mt * p0 + 2 * mt * t * p1 + t * t * p2;
      }

      function buildNeurons() {
        neurons = [];
        const cols = Math.ceil(Math.sqrt(CFG.hubCount * (W / H)));
        const rows = Math.ceil(CFG.hubCount / cols);
        let hi = 0;
        for (let r = 0; r < rows && hi < CFG.hubCount; r++) {
          for (let c = 0; c < cols && hi < CFG.hubCount; c++) {
            const ox = (c + 0.3 + Math.random() * 0.4) * (W / cols);
            const oy = (r + 0.3 + Math.random() * 0.4) * (H / rows);
            const z = 0.4 + Math.random() * 0.6;
            neurons.push({
              ox, oy, x: ox, y: oy, z,
              baseR: 2.6, isHub: true,
              fireAmt: 0, firePhase: Math.random() * Math.PI * 2,
              activity: 0.2 + Math.random() * 0.18,
              pulseLoad: 0, outboundAmt: 0,
              shapeSeed: Math.random() * 1000,
              driftAngle: Math.random() * Math.PI * 2,
              driftSpeed: 0.006 + Math.random() * 0.018,
              neighbors: [],
            });
            hi++;
          }
        }
        for (let i = 0; i < CFG.leafCount; i++) {
          const hub = neurons[Math.floor(Math.random() * CFG.hubCount)];
          const angle = Math.random() * Math.PI * 2;
          const dist = 30 + Math.random() * 160;
          const ox = Math.max(10, Math.min(W - 10, hub.ox + Math.cos(angle) * dist));
          const oy = Math.max(10, Math.min(H - 10, hub.oy + Math.sin(angle) * dist));
          const z = 0.15 + Math.random() * 0.75;
          neurons.push({
            ox, oy, x: ox, y: oy, z,
            baseR: 2.6, isHub: false,
            fireAmt: 0, firePhase: Math.random() * Math.PI * 2,
            activity: Math.random() * 0.12,
            pulseLoad: 0, outboundAmt: 0,
            shapeSeed: Math.random() * 1000,
            driftAngle: Math.random() * Math.PI * 2,
            driftSpeed: 0.003 + Math.random() * 0.012,
            neighbors: [],
          });
        }
        const total = neurons.length;
        edges = [];
        edgeIdx = new Map();
        // Build edges with strict caps. Process hubs first (priority for
        // long-range scaffolding), then leaves. Each node gets at most its
        // own cap; the connecting node's cap is also respected.
        const order = [];
        for (let i = 0; i < total; i++) if (neurons[i].isHub) order.push(i);
        for (let i = 0; i < total; i++) if (!neurons[i].isHub) order.push(i);

        for (const i of order) {
          const a = neurons[i];
          const cap = a.isHub ? CFG.hubMaxNeighbors : CFG.leafMaxNeighbors;
          if (a.neighbors.length >= cap) continue;
          const maxD = a.isHub ? CFG.hubConnDist : CFG.connDist;
          const cands = [];
          for (let j = 0; j < total; j++) {
            if (i === j) continue;
            if (a.neighbors.includes(j)) continue;
            const b = neurons[j];
            const otherCap = b.isHub ? CFG.hubMaxNeighbors : CFG.leafMaxNeighbors;
            if (b.neighbors.length >= otherCap) continue;
            const d = Math.hypot(a.ox - b.ox, a.oy - b.oy);
            if (d < maxD) cands.push({ idx: j, dist: d });
          }
          // bias toward shorter, varied connections (don't always take the closest)
          cands.sort((x, y) => x.dist - y.dist);
          const slots = cap - a.neighbors.length;
          // Pick from a slightly randomised window so the topology feels organic
          const pool = cands.slice(0, Math.min(cands.length, slots * 3));
          while (a.neighbors.length < cap && pool.length) {
            const k = Math.floor(Math.random() * Math.min(pool.length, 3));
            const pick = pool.splice(k, 1)[0];
            const b = neurons[pick.idx];
            const bCap = b.isHub ? CFG.hubMaxNeighbors : CFG.leafMaxNeighbors;
            if (b.neighbors.length >= bCap) continue;
            // create the edge
            a.neighbors.push(pick.idx);
            b.neighbors.push(i);
            const dx = b.ox - a.ox, dy = b.oy - a.oy;
            const len = Math.hypot(dx, dy) || 1;
            const nx = -dy / len, ny = dx / len;       // normal
            const amp = len * (0.012 + Math.random() * 0.022) * (Math.random() < 0.5 ? -1 : 1);
            const amp2 = amp * (0.55 + Math.random() * 0.3) * (Math.random() < 0.4 ? -1 : 1);
            // Two control points along the line, offset along the normal,
            // for an S-curve with smooth tangents at both ends.
            const cp1 = { ox: dx * 0.30 + nx * amp,  oy: dy * 0.30 + ny * amp  };
            const cp2 = { ox: dx * 0.70 + nx * amp2, oy: dy * 0.70 + ny * amp2 };
            const eIdx = edges.length;
            edges.push({ a: i, b: pick.idx, cp1, cp2, len });
            edgeIdx.set(i + "-" + pick.idx, eIdx);
            edgeIdx.set(pick.idx + "-" + i, eIdx);
          }
        }
      }

      // ── Pulse plumbing ────────────────────────────────────────────────
      // Pulses ONLY traverse pre-built edges. Each pulse remembers its
      // recent path and avoids backtracking. If the host has no fresh
      // neighbor it backtracks (pop one) and tries from there; if that
      // also fails the pulse retires.

      // cubic Bezier point
      function cBez(p0, p1, p2, p3, t) {
        const mt = 1 - t;
        return mt*mt*mt*p0 + 3*mt*mt*t*p1 + 3*mt*t*t*p2 + t*t*t*p3;
      }

      // Resolve a directed traversal: returns { x1,y1,x2,y2,c1x,c1y,c2x,c2y, len }
      // pulling the curve from the stored edge but flipping cp order if needed.
      function edgeCurve(fromIdx, toIdx) {
        const key = fromIdx + "-" + toIdx;
        const e = edges[edgeIdx.get(key)];
        if (!e) return null;
        const A = neurons[fromIdx], B = neurons[toIdx];
        // The stored cps are offsets from edge.a. If we're going from .a to .b,
        // use cp1 then cp2; otherwise reverse so the curve enters the correct way.
        const reverse = e.a !== fromIdx;
        const baseX = neurons[e.a].x, baseY = neurons[e.a].y;
        const c1 = reverse
          ? { x: baseX + e.cp2.ox, y: baseY + e.cp2.oy }
          : { x: baseX + e.cp1.ox, y: baseY + e.cp1.oy };
        const c2 = reverse
          ? { x: baseX + e.cp1.ox, y: baseY + e.cp1.oy }
          : { x: baseX + e.cp2.ox, y: baseY + e.cp2.oy };
        return { A, B, c1, c2, len: e.len };
      }

      function hopSpeed(len) {
        const distF = Math.min(1, len / CFG.hubConnDist);
        return CFG.pulseSpeedNear + (CFG.pulseSpeedFar - CFG.pulseSpeedNear) * distF
             + Math.random() * CFG.pulseSpeedJitter;
      }

      // Choose next neighbor not in path. No edge creation — strictly
      // honors the network's topology. Returns -1 if dead-end.
      function pickNextHop(p, cur) {
        const host = neurons[cur];
        if (!host.neighbors.length) return -1;
        const fresh = host.neighbors.filter(j => !p.path.includes(j));
        if (!fresh.length) return -1;
        // Prefer hubs slightly so flows trend toward backbone
        const hubs  = fresh.filter(j => neurons[j].isHub);
        const pool  = (hubs.length && Math.random() < 0.6) ? hubs : fresh;
        return pool[Math.floor(Math.random() * pool.length)];
      }

      function makePulse(delay = 0) {
        const hubs = neurons.filter(n => n.isHub && n.neighbors.length > 0);
        const src = hubs.length
          ? hubs[Math.floor(Math.random() * hubs.length)]
          : neurons.find(n => n.neighbors.length > 0)
            || neurons[Math.floor(Math.random() * neurons.length)];
        const fromIdx = neurons.indexOf(src);
        const toIdx = src.neighbors.length
          ? src.neighbors[Math.floor(Math.random() * src.neighbors.length)]
          : -1;
        if (toIdx < 0) {
          return { path: [fromIdx], from: fromIdx, to: fromIdx,
                   t: -(delay / 1000), speed: 0.0001, maxHops: 1,
                   active: false, trail: [], dead: true };
        }
        const c = edgeCurve(fromIdx, toIdx);
        return {
          path: [fromIdx, toIdx],
          from: fromIdx, to: toIdx,
          t: delay > 0 ? -delay / 1000 : 0,
          speed: hopSpeed(c ? c.len : 200),
          maxHops: 7 + Math.floor(Math.random() * 8), // 7–14 hops
          active: delay <= 0,
          trail: [],
        };
      }
      function buildPulses() {
        pulses = [];
        for (let i = 0; i < CFG.pulseCount; i++) {
          pulses.push(makePulse(500 + i * CFG.pulseLaunchSpacingMs));
        }
      }
      function markPulseLaunch(p) {
        const src = neurons[p.from]; if (!src) return;
        src.outboundAmt = 1.4;
        src.activity   = Math.min(1.8, src.activity + 0.45);
        src.pulseLoad  = Math.min(1, src.pulseLoad + 0.55);
        src.fireAmt    = Math.max(src.fireAmt, 1.25);
        src.firePhase  = 0;
      }

      function update(dt) {
        for (const n of neurons) {
          n.driftAngle += 0.0006 * (0.5 - Math.random() * 0.15);
          n.ox += Math.cos(n.driftAngle) * n.driftSpeed;
          n.oy += Math.sin(n.driftAngle) * n.driftSpeed;
          if (n.ox < 20)     { n.driftAngle = 0;            n.ox = 20; }
          if (n.ox > W - 20) { n.driftAngle = Math.PI;      n.ox = W - 20; }
          if (n.oy < 20)     { n.driftAngle = Math.PI / 2;  n.oy = 20; }
          if (n.oy > H - 20) { n.driftAngle = -Math.PI / 2; n.oy = H - 20; }
          let tx = n.ox, ty = n.oy;
          if (mouse.active) {
            const mdx = mouse.x - n.ox, mdy = mouse.y - n.oy;
            const md = Math.hypot(mdx, mdy);
            if (md < CFG.mouseRadius) {
              const str = (1 - md / CFG.mouseRadius) * CFG.mouseStrength * n.z;
              tx = n.ox + (mdx / md) * str;
              ty = n.oy + (mdy / md) * str;
            }
          }
          n.x += (tx - n.x) * CFG.ease;
          n.y += (ty - n.y) * CFG.ease;
          n.fireAmt = Math.max(0, n.fireAmt - CFG.fireDecay * dt);
          n.activity = Math.max(0, n.activity - CFG.activityDecay * dt);
          n.pulseLoad = Math.max(0, n.pulseLoad - CFG.pulseLoadDecay * dt);
          n.outboundAmt = Math.max(0, n.outboundAmt - CFG.outboundDecay * dt);
          n.firePhase += 0.0028 + n.activity * 0.008;
        }
        let active = pulses.reduce((c, p) => c + (p.active && p.t >= 0 && p.t <= 1 ? 1 : 0), 0);
        for (let i = 0; i < pulses.length; i++) {
          const p = pulses[i];
          if (p.dead) { pulses[i] = makePulse(900 + Math.random() * 1800); continue; }
          if (!p.active) {
            p.t += p.speed * dt;
            if (p.t >= 0) {
              if (active < CFG.maxActivePulses) {
                p.t = 0; p.active = true; active++; markPulseLaunch(p);
              } else { p.t = -(500 + Math.random() * 800) / 1000; }
            }
            continue;
          }
          const prevT = p.t;
          p.t += p.speed * dt;
          if (prevT <= 0 && p.t > 0) markPulseLaunch(p);
          const c = edgeCurve(p.from, p.to);
          if (!c) {
            pulses[i] = makePulse(800 + Math.random() * 1400);
            active = Math.max(0, active - 1);
            continue;
          }
          const px = cBez(c.A.x, c.c1.x, c.c2.x, c.B.x, p.t);
          const py = cBez(c.A.y, c.c1.y, c.c2.y, c.B.y, p.t);
          if (p.trail.length === 0 ||
              Math.hypot(px - p.trail[p.trail.length - 1].x, py - p.trail[p.trail.length - 1].y) > 3) {
            p.trail.push({ x: px, y: py });
            if (p.trail.length > 22) p.trail.shift();
          }
          if (p.t >= 1) {
            const tgtN = neurons[p.to];
            tgtN.activity    = Math.min(1.8, tgtN.activity + 0.6);
            tgtN.pulseLoad   = Math.min(1, tgtN.pulseLoad + 0.7);
            tgtN.fireAmt     = Math.max(tgtN.fireAmt, 1.6);
            tgtN.outboundAmt = Math.max(tgtN.outboundAmt, 0.9);
            tgtN.firePhase   = 0;

            if (p.path.length >= p.maxHops) {
              pulses[i] = makePulse(900 + Math.random() * 1800);
              active = Math.max(0, active - 1);
              continue;
            }
            // Try forward; if dead-end, backtrack ONCE before retiring.
            let next = pickNextHop(p, p.to);
            if (next < 0) {
              if (p.path.length > 1) {
                const back = p.path[p.path.length - 2];
                next = back;
              } else {
                pulses[i] = makePulse(900 + Math.random() * 1800);
                active = Math.max(0, active - 1);
                continue;
              }
            }
            markPulseLaunch({ from: p.to });
            const nc = edgeCurve(p.to, next);
            p.from  = p.to;
            p.to    = next;
            p.speed = hopSpeed(nc ? nc.len : 200);
            p.t     = 0;
            if (!p.path.includes(next)) p.path.push(next);
          }
        }
      }

      function drawOrganicBlob(x, y, r, seed, phase, activity) {
        const points = 12;
        const wobble = 0.025 + activity * 0.035;
        const verts = [];
        for (let i = 0; i < points; i++) {
          const a = (i / points) * Math.PI * 2;
          const wave = Math.sin(seed + i * 1.73 + phase) * 0.55 +
                       Math.sin(seed * 0.7 + i * 2.41 - phase * 0.7) * 0.35;
          const rr = r * (1 + wave * wobble);
          verts.push({ x: x + Math.cos(a) * rr, y: y + Math.sin(a) * rr });
        }
        ctx.beginPath();
        const first = verts[0], last = verts[verts.length - 1];
        ctx.moveTo((last.x + first.x) / 2, (last.y + first.y) / 2);
        for (let i = 0; i < verts.length; i++) {
          const cur = verts[i], nxt = verts[(i + 1) % verts.length];
          ctx.quadraticCurveTo(cur.x, cur.y, (cur.x + nxt.x) / 2, (cur.y + nxt.y) / 2);
        }
        ctx.closePath();
      }

      function draw() {
        ctx.clearRect(0, 0, W, H);
        // axons — organic curved connections (cubic Bezier, stored per edge)
        for (const e of edges) {
          const A = neurons[e.a], B = neurons[e.b];
          const baseX = A.x, baseY = A.y;
          const c1x = baseX + e.cp1.ox, c1y = baseY + e.cp1.oy;
          const c2x = baseX + e.cp2.ox, c2y = baseY + e.cp2.oy;
          const heat = Math.max(A.activity, B.activity);
          const depth = (A.z + B.z) / 2;
          const baseA = 0.18 + depth * 0.12;
          ctx.beginPath();
          ctx.moveTo(A.x, A.y);
          ctx.bezierCurveTo(c1x, c1y, c2x, c2y, B.x, B.y);
          ctx.strokeStyle = `rgba(${COL.excite.r},${COL.excite.g},${COL.excite.b},${baseA})`;
          ctx.lineWidth = (A.isHub || B.isHub ? 0.9 : 0.55);
          ctx.lineCap = "round";
          ctx.stroke();
        }
        // bodies
        for (const n of neurons) {
          const baseR = n.baseR * (0.5 + n.z * 0.5);
          const activity = Math.min(1, n.activity);
          const swell = activity * (n.isHub ? 0.22 : 0.28) + n.pulseLoad * 0.07;
          const breath = 1 + Math.sin(n.firePhase + n.shapeSeed) * (0.01 + activity * 0.012);
          const r = baseR * (1 + swell) * breath;
          const idleAlpha = n.isHub ? 0.18 + n.z * 0.14 : 0.08 + n.z * 0.12;
          const coreAlpha = Math.min(0.95, idleAlpha + activity * 0.5 + n.fireAmt * 0.22);
          if (n.outboundAmt > 0.01) {
            const c = n.isHub ? COL.hubBase : COL.warm;
            const waveR = r * (1.05 + (1 - n.outboundAmt) * 1.75);
            const waveGrad = ctx.createRadialGradient(n.x, n.y, r * 0.65, n.x, n.y, waveR);
            waveGrad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},${0.08 * n.outboundAmt})`);
            waveGrad.addColorStop(0.52, `rgba(${c.r},${c.g},${c.b},${0.045 * n.outboundAmt})`);
            waveGrad.addColorStop(1, "rgba(0,0,0,0)");
            drawOrganicBlob(n.x, n.y, waveR, n.shapeSeed + 23, n.firePhase * 0.25, activity * 0.5);
            ctx.fillStyle = waveGrad; ctx.fill();
          }
          if (n.fireAmt > 0.01 || activity > 0.04) {
            const fi = Math.max(n.fireAmt, activity * 0.55) * (0.7 + 0.3 * Math.sin(n.firePhase));
            const glowR = r * (1.8 + 3.2 * fi);
            const c = n.isHub ? COL.hubBase : COL.excite;
            const grad = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, glowR);
            grad.addColorStop(0, `rgba(${c.r},${c.g},${c.b},${0.42 * fi})`);
            grad.addColorStop(0.45, `rgba(${c.r},${c.g},${c.b},${0.14 * fi})`);
            grad.addColorStop(1, "rgba(0,0,0,0)");
            drawOrganicBlob(n.x, n.y, glowR, n.shapeSeed, n.firePhase * 0.45, activity);
            ctx.fillStyle = grad; ctx.fill();
          }
          const c = n.isHub ? COL.hubBase : COL.warm;
          drawOrganicBlob(n.x, n.y, r, n.shapeSeed, n.firePhase, activity);
          ctx.fillStyle = `rgba(${c.r},${c.g},${c.b},${coreAlpha})`;
          ctx.fill();
          if (n.isHub || activity > 0.2) {
            drawOrganicBlob(n.x, n.y, r * (n.isHub ? 0.42 : 0.34), n.shapeSeed + 17, -n.firePhase * 0.8, activity);
            const w = lighten(COL.warm, 0.4);
            ctx.fillStyle = `rgba(${w.r},${w.g},${w.b},${0.06 + activity * 0.24 + n.fireAmt * 0.14})`;
            ctx.fill();
          }
        }
        // pulses
        for (const p of pulses) {
          if (!p.active || p.t < 0 || p.t > 1 || p.dead) continue;
          const c = edgeCurve(p.from, p.to);
          if (!c) continue;
          const px = cBez(c.A.x, c.c1.x, c.c2.x, c.B.x, p.t);
          const py = cBez(c.A.y, c.c1.y, c.c2.y, c.B.y, p.t);
          const col = COL.excite;
          const depthA = 0.5 + (c.A.z + c.B.z) * 0.25;
          // glowing trail
          if (p.trail.length >= 2) {
            for (let ti = 1; ti < p.trail.length; ti++) {
              const ta = ti / p.trail.length;
              ctx.beginPath();
              ctx.moveTo(p.trail[ti - 1].x, p.trail[ti - 1].y);
              ctx.lineTo(p.trail[ti].x, p.trail[ti].y);
              ctx.strokeStyle = `rgba(${col.r},${col.g},${col.b},${ta * ta * 0.85 * depthA})`;
              ctx.lineWidth = 2.4 * ta;
              ctx.lineCap = "round";
              ctx.stroke();
            }
          }
          // outer halo
          const haloR = 22;
          const halo = ctx.createRadialGradient(px, py, 0, px, py, haloR);
          halo.addColorStop(0,    `rgba(${col.r},${col.g},${col.b},${0.55 * depthA})`);
          halo.addColorStop(0.35, `rgba(${col.r},${col.g},${col.b},${0.22 * depthA})`);
          halo.addColorStop(0.7,  `rgba(${col.r},${col.g},${col.b},${0.06 * depthA})`);
          halo.addColorStop(1, "rgba(0,0,0,0)");
          ctx.beginPath(); ctx.arc(px, py, haloR, 0, Math.PI * 2);
          ctx.fillStyle = halo; ctx.fill();
          // inner energy ball
          const ballR = 9;
          const ball = ctx.createRadialGradient(px, py, 0, px, py, ballR);
          ball.addColorStop(0,   `rgba(255,255,255,${0.95 * depthA})`);
          ball.addColorStop(0.3, `rgba(${Math.min(255, col.r + 80)},${Math.min(255, col.g + 80)},${Math.min(255, col.b + 80)},${0.85 * depthA})`);
          ball.addColorStop(1,   `rgba(${col.r},${col.g},${col.b},0)`);
          ctx.beginPath(); ctx.arc(px, py, ballR, 0, Math.PI * 2);
          ctx.fillStyle = ball; ctx.fill();
          // bright core
          ctx.beginPath(); ctx.arc(px, py, 2.4, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(255,255,255,${0.95 * depthA})`; ctx.fill();
        }
      }

      function resize() {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = window.innerWidth; H = window.innerHeight;
        canvas.width = W * dpr; canvas.height = H * dpr;
        canvas.style.width = W + "px"; canvas.style.height = H + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        buildNeurons(); buildPulses();
      }
      function loop(time) {
        const dt = Math.min(time - lastTime, 48);
        lastTime = time;
        update(dt); draw();
        rafId = requestAnimationFrame(loop);
      }
      resize();
      rafId = requestAnimationFrame((t) => { lastTime = t; loop(t); });
      const onResize = () => resize();
      const onMove = (e) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true; };
      const onOut  = () => { mouse.active = false; };
      window.addEventListener("resize", onResize);
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseout", onOut);
      return () => {
        cancelAnimationFrame(rafId);
        obs.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseout", onOut);
      };
    }, []);

    return (
      <canvas ref={canvasRef}
        style={{
          position: "fixed", inset: 0, width: "100%", height: "100%",
          zIndex: 0, pointerEvents: "none",
          opacity: "var(--bg-strength, 0.55)",
          mixBlendMode: "var(--bg-blend, normal)",
        }}/>
    );
  }
  window.NeuralBg = NeuralBg;
})();
