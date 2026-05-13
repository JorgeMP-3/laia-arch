// AGORA · Variación 2 "Operador"
// Full dark, command-centric, monospace-leaning, dense.
// Exports: <OperatorShell view onView/>.

const opStyles = {
  root: {
    display: "flex", flexDirection: "column", height: "100%",
    background: "transparent",
    color: "var(--d-ink)",
    fontFamily: "var(--f-sans)",
  },
  // top bar — minimal
  topbar: {
    display: "flex", alignItems: "center", gap: 14,
    height: 44, padding: "0 18px",
    borderBottom: "1px solid var(--d-line)",
    background: "linear-gradient(to bottom, rgba(255,255,255,.02), transparent)",
  },
  brand: { display: "flex", alignItems: "center", gap: 8 },
  brandMark: {
    width: 22, height: 22, borderRadius: 6,
    background: "var(--acc)", color: "var(--acc-ink)",
    display: "grid", placeItems: "center",
    fontWeight: 700, fontSize: 11.5,
  },
  pathSeg: { color: "var(--d-muted)", fontFamily: "var(--f-mono)", fontSize: 12 },
  pathCur: { color: "var(--d-ink)", fontFamily: "var(--f-mono)", fontSize: 12 },

  navBtn: (active) => ({
    height: 26, padding: "0 10px", borderRadius: 6,
    background: active ? "rgba(255,255,255,.06)" : "transparent",
    border: active ? "1px solid var(--d-line-2)" : "1px solid transparent",
    color: active ? "var(--d-ink)" : "var(--d-ink-2)",
    fontSize: 12, cursor: "pointer", fontFamily: "var(--f-mono)",
    display: "inline-flex", alignItems: "center", gap: 6,
  }),

  cmd: {
    flex: 1, maxWidth: 540, height: 28,
    border: "1px solid var(--d-line-2)", borderRadius: 6,
    background: "rgba(255,255,255,.03)",
    display: "flex", alignItems: "center", gap: 8, padding: "0 10px",
    color: "var(--d-muted)", fontFamily: "var(--f-mono)", fontSize: 12,
  },

  // body grid
  body: {
    flex: 1, minHeight: 0, display: "grid",
    gridTemplateColumns: "1fr 240px",
  },

  panel: { padding: "18px 22px", overflow: "auto", minHeight: 0 },

  rail: {
    borderLeft: "1px solid var(--d-line)",
    padding: "18px 14px", display: "flex", flexDirection: "column", gap: 12,
    overflow: "auto", minHeight: 0,
  },

  pill: (variant = "default") => {
    const v = {
      default: { bg: "rgba(255,255,255,.04)", fg: "var(--d-ink-2)", bd: "var(--d-line)" },
      hot:     { bg: "color-mix(in oklab, var(--acc) 18%, transparent)", fg: "var(--acc)", bd: "color-mix(in oklab, var(--acc) 40%, transparent)" },
      warn:    { bg: "color-mix(in oklab, var(--warn) 18%, transparent)", fg: "var(--warn)", bd: "color-mix(in oklab, var(--warn) 40%, transparent)" },
      ok:      { bg: "color-mix(in oklab, var(--ok) 16%, transparent)", fg: "color-mix(in oklab, var(--ok) 80%, white 20%)", bd: "color-mix(in oklab, var(--ok) 40%, transparent)" },
    }[variant];
    return {
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "1px 7px", borderRadius: 4,
      background: v.bg, color: v.fg, border: `1px solid ${v.bd}`,
      fontSize: 10.5, fontFamily: "var(--f-mono)",
      letterSpacing: ".02em",
    };
  },

  sect: {
    fontFamily: "var(--f-mono)", fontSize: 10.5,
    color: "var(--d-muted)", letterSpacing: ".08em",
    textTransform: "uppercase", marginBottom: 8,
    display: "flex", alignItems: "center", gap: 8,
  },
};

function OpTopbar({ view, onView }) {
  return (
    <div style={opStyles.topbar}>
      <div style={opStyles.brand}>
        <div style={opStyles.brandMark}>A</div>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--d-ink)", letterSpacing: ".04em" }}>agora</span>
        <span style={opStyles.pathSeg}>/</span>
        <span style={opStyles.pathCur}>{view === "home" ? "inicio" : "laia.maria"}</span>
      </div>

      <span style={{ width: 1, height: 18, background: "var(--d-line)", margin: "0 4px" }}/>

      <button style={opStyles.navBtn(view === "home")} onClick={() => onView("home")}>
        <I.home size={13}/>inicio
      </button>
      <button style={opStyles.navBtn(view === "chat")} onClick={() => onView("chat")}>
        <I.bot size={13}/>laia
      </button>
      <button style={opStyles.navBtn(false)}><I.list size={13}/>backlog</button>
      <button style={opStyles.navBtn(false)}><I.grid size={13}/>skills</button>
      <button style={opStyles.navBtn(false)}><I.pulse size={13}/>coordinador</button>

      <div style={{ flex: 1 }}/>

      <div style={opStyles.cmd}>
        <I.cmd size={12}/>
        <span style={{ flex: 1 }}>pregunta a laia · ejecuta skill · <span style={{ color: "var(--d-ink-2)" }}>‘revisar propuesta motor sur’</span></span>
        <span className="mono" style={{ background: "var(--d-line)", color: "var(--d-ink-2)", padding: "0 5px", borderRadius: 3, fontSize: 10.5 }}>⌘K</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--d-muted)", fontFamily: "var(--f-mono)", fontSize: 11 }}>
        <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--ok)", animation: "pulse-dot 2s ease-in-out infinite" }}/>
        coord activo
      </div>

      <div style={{ width: 26, height: 26, borderRadius: 999,
                     background: "linear-gradient(135deg,var(--acc),#8a3a26)", color: "white",
                     display: "grid", placeItems: "center", fontSize: 10.5, fontWeight: 700 }}>
        {AGORA_USER.initials}
      </div>
    </div>
  );
}

/* ---------- HOME (operador) ---------- */
function OpHome({ onView }) {
  return (
    <div style={opStyles.body}>
      <div style={opStyles.panel}>
        {/* greeting + brief */}
        <div style={{ marginBottom: 26 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 6 }}>
            <span className="mono" style={{ color: "var(--d-muted)", fontSize: 11.5 }}>$ laia.brief --user maria --date 08-may</span>
            <span style={opStyles.pill("ok")}>OK · 7s</span>
          </div>
          <h1 style={{ margin: "4px 0 4px", fontFamily: "var(--f-display)", fontStyle: "italic",
                        fontSize: 36, letterSpacing: "-.005em", color: "var(--d-ink)", lineHeight: 1.05 }}>
            {AGORA_BRIEF.greeting}
          </h1>
          <p style={{ margin: 0, fontSize: 13.5, color: "var(--d-ink-2)", maxWidth: 720 }}>
            {AGORA_BRIEF.summary}
          </p>
        </div>

        {/* priorities — terminal-style list */}
        <div style={{ marginBottom: 28 }}>
          <div style={opStyles.sect}>
            <span>priorities</span>
            <span style={{ flex: 1, height: 1, background: "var(--d-line)" }}/>
            <span>{AGORA_BRIEF.priorities.length}</span>
          </div>
          {AGORA_BRIEF.priorities.map((p, i) => (
            <div key={p.id} style={{
              display: "grid", gridTemplateColumns: "auto 110px 1fr auto",
              gap: 14, alignItems: "center",
              padding: "10px 4px", borderBottom: "1px solid var(--d-line)",
            }}>
              <span className="mono" style={{ color: "var(--d-muted)", fontSize: 12 }}>0{i+1}</span>
              <span style={opStyles.pill(p.tag === "Riesgo" ? "warn" : p.tag === "Cierre" ? "ok" : "hot")}>
                {p.tag.toLowerCase()}
              </span>
              <div>
                <div style={{ fontSize: 14, color: "var(--d-ink)", fontWeight: 500 }}>{p.title}</div>
                <div style={{ fontSize: 11.5, color: "var(--d-muted)", fontFamily: "var(--f-mono)" }}>{p.meta}</div>
              </div>
              <button style={{ height: 28, padding: "0 12px", borderRadius: 6,
                                background: "transparent", border: "1px solid var(--d-line-2)",
                                color: "var(--d-ink)", fontSize: 12, cursor: "pointer",
                                display: "inline-flex", alignItems: "center", gap: 6 }}>
                {p.action}<I.arrowR size={12}/>
              </button>
            </div>
          ))}
        </div>

        {/* three-column dense grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr 1.1fr", gap: 18 }}>
          {/* TODAY */}
          <div>
            <div style={opStyles.sect}><span>today</span><span style={{ flex: 1, height: 1, background: "var(--d-line)" }}/><span>{AGORA_TASKS.length}</span></div>
            <div className="mono" style={{ fontSize: 12.5, lineHeight: 1.85 }}>
              {AGORA_TASKS.map((t) => (
                <div key={t.id} style={{ display: "grid", gridTemplateColumns: "44px 12px 1fr", gap: 6, padding: "2px 0" }}>
                  <span style={{ color: "var(--d-muted)" }}>{t.when}</span>
                  <span style={{ color: t.status === "scheduled" ? "var(--acc)" : "var(--d-muted-2)" }}>{t.status === "scheduled" ? "●" : "○"}</span>
                  <span style={{ color: "var(--d-ink-2)" }}>{t.title} <span style={{ color: "var(--d-muted)" }}>· {t.via}</span></span>
                </div>
              ))}
            </div>
          </div>

          {/* BACKLOG */}
          <div>
            <div style={opStyles.sect}><span>backlog</span><span style={{ flex: 1, height: 1, background: "var(--d-line)" }}/><span>3</span></div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {AGORA_BACKLOG.map((b) => (
                <div key={b.id}>
                  <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5 }}>
                    <span style={{ color: "var(--d-ink-2)" }}>{b.proj}</span>
                    <span className="tab-num" style={{ color: "var(--acc)" }}>{Math.round(b.progress*100)}%</span>
                  </div>
                  <div style={{ height: 4, background: "var(--d-line)", borderRadius: 2, marginTop: 4, overflow: "hidden" }}>
                    <div style={{ width: `${b.progress*100}%`, height: "100%", background: "var(--acc)" }}/>
                  </div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)", marginTop: 3 }}>
                    {b.owner} · {b.items} ítems · due {b.due}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* COORDINATOR */}
          <div>
            <div style={opStyles.sect}><span>coordinator · 24h</span><span style={{ flex: 1, height: 1, background: "var(--d-line)" }}/><span>{AGORA_COORDINATOR.toArch.actions24h}</span></div>
            <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.7 }}>
              {AGORA_COORDINATOR.events.map((e) => (
                <div key={e.id} style={{ display: "grid", gridTemplateColumns: "46px 1fr auto", gap: 8, padding: "3px 0", borderBottom: "1px dashed var(--d-line)" }}>
                  <span style={{ color: "var(--d-muted)" }}>{e.at}</span>
                  <span style={{ color: "var(--d-ink-2)" }}>{e.text}</span>
                  <span style={opStyles.pill(e.badge === "ARCH" ? "hot" : "default")}>{e.badge}</span>
                </div>
              ))}
            </div>
            <div className="mono" style={{ marginTop: 10, fontSize: 11, color: "var(--d-muted)" }}>
              <span style={{ color: "var(--d-ink-2)" }}>$</span> arch.report --next {AGORA_COORDINATOR.toArch.next.replace(/\s/g, "_")}
              <span className="cursor-blink"/>
            </div>
          </div>
        </div>

        {/* skills strip */}
        <div style={{ marginTop: 28 }}>
          <div style={opStyles.sect}><span>skill marketplace</span><span style={{ flex: 1, height: 1, background: "var(--d-line)" }}/><span>24 · 6 fijadas</span></div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 10 }}>
            {AGORA_SKILLS.map((s) => (
              <div key={s.id} style={{ border: "1px solid var(--d-line)", borderRadius: 8,
                                        padding: 12, background: "rgba(255,255,255,.02)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <span className="serif" style={{ color: "var(--acc)", fontSize: 18 }}>{s.glyph}</span>
                  <span className="mono tab-num" style={{ fontSize: 10.5, color: "var(--d-muted)" }}>{s.uses}</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--d-ink)", fontWeight: 500 }}>{s.name}</div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)", marginTop: 3 }}>by {s.by}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT RAIL — team + system */}
      <div style={opStyles.rail}>
        <div>
          <div style={opStyles.sect}><span>team · ahora</span></div>
          {AGORA_TEAM.map((p) => (
            <div key={p.name} style={{ display: "grid", gridTemplateColumns: "8px 1fr auto", gap: 8,
                                        padding: "7px 0", borderBottom: "1px dashed var(--d-line)" }}>
              <span style={{ width: 6, height: 6, borderRadius: 999, background: p.dot, marginTop: 6 }}/>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: "var(--d-ink)" }}>{p.name}</div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)",
                                                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {p.status}
                </div>
              </div>
              <span style={opStyles.pill()}>{p.with}</span>
            </div>
          ))}
        </div>

        <div>
          <div style={opStyles.sect}><span>tu memoria</span></div>
          <div className="mono" style={{ fontSize: 11, lineHeight: 1.7, color: "var(--d-ink-2)" }}>
            <div><span style={{ color: "var(--d-muted)" }}>hechos.</span> 142</div>
            <div><span style={{ color: "var(--d-muted)" }}>cuentas.</span> 9</div>
            <div><span style={{ color: "var(--d-muted)" }}>preferencias.</span> 12</div>
            <div><span style={{ color: "var(--d-muted)" }}>sync.</span> hace 2 min</div>
          </div>
        </div>

        <div>
          <div style={opStyles.sect}><span>laia → arch</span></div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)", lineHeight: 1.7 }}>
            <div>último: <span style={{ color: "var(--d-ink-2)" }}>{AGORA_COORDINATOR.toArch.last}</span></div>
            <div>próximo: <span style={{ color: "var(--d-ink-2)" }}>{AGORA_COORDINATOR.toArch.next}</span></div>
            <div>vpn: <span style={{ color: "var(--ok)" }}>activa</span></div>
          </div>
          <button style={{ marginTop: 8, width: "100%", padding: "6px 10px",
                            border: "1px dashed var(--d-line-2)", borderRadius: 6,
                            background: "transparent", color: "var(--d-ink-2)",
                            fontFamily: "var(--f-mono)", fontSize: 11, cursor: "pointer" }}>
            ver informe nocturno →
          </button>
        </div>

        <div style={{ marginTop: "auto", fontFamily: "var(--f-mono)", fontSize: 10,
                       color: "var(--d-muted-2)", textAlign: "center", paddingTop: 12,
                       borderTop: "1px solid var(--d-line)" }}>
          AGORA · build 0.4 · ARCH-link encrypted
        </div>
      </div>
    </div>
  );
}

window.OperatorShell = function OperatorShell({ view, onView }) {
  return (
    <div style={opStyles.root}>
      <OpTopbar view={view} onView={onView}/>
      {view === "home" ? <OpHome onView={onView}/> : <OperatorChat onView={onView}/>}
    </div>
  );
};
window.opStyles = opStyles;
window.OpTopbar = OpTopbar;
