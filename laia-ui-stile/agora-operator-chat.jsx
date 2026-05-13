// AGORA · Operator · Chat
// Full dark, typography-driven, no bubbles. Mono for tool-use.

function OperatorChat({ onView }) {
  const [draft, setDraft] = React.useState("");
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 240px",
                  height: "100%", minHeight: 0 }}>
      {/* MAIN */}
      <section style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--d-line)",
                       display: "flex", alignItems: "center", gap: 12 }}>
          <span className="serif" style={{ fontSize: 22, color: "var(--acc)", lineHeight: 1 }}>L</span>
          <div>
            <div style={{ fontSize: 14, color: "var(--d-ink)", fontWeight: 600 }}>laia.maria</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--d-muted)" }}>
              memoria: 142 hechos · sync 2m · skills: 24 disponibles
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button style={opStyles.navBtn(false)}><I.pin size={12}/>fijar</button>
            <button style={opStyles.navBtn(false)}><I.loop size={12}/>nuevo hilo</button>
            <button style={opStyles.navBtn(false)}><I.more size={12}/></button>
          </div>
        </div>

        <div className="thin-scroll" style={{ flex: 1, overflow: "auto", padding: "20px 28px 8px" }}>
          <div style={{ maxWidth: 760, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14 }}>
            {AGORA_THREAD.map((m) => <OpMsg key={m.id} m={m}/>)}
          </div>
        </div>

        {/* composer */}
        <div style={{ borderTop: "1px solid var(--d-line)", padding: "12px 28px 18px",
                       background: "linear-gradient(to top, rgba(255,255,255,.02), transparent)" }}>
          <div style={{ maxWidth: 760, margin: "0 auto" }}>
            <div className="mono" style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
              {["resumir hilo","crear tarea","borrador email","comparar ayer","ejecutar skill"].map(c => (
                <button key={c} style={opStyles.navBtn(false)}>{c}</button>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10,
                           border: "1px solid var(--d-line-2)", borderRadius: 8,
                           padding: "10px 12px", background: "rgba(255,255,255,.02)" }}>
              <span className="mono" style={{ color: "var(--acc)", fontSize: 13, paddingTop: 2 }}>›</span>
              <textarea
                value={draft} onChange={(e) => setDraft(e.target.value)}
                placeholder="pregunta a laia · ejecuta skill · adjunta cuenta…"
                rows={1}
                style={{ flex: 1, border: "none", outline: "none", resize: "none",
                         background: "transparent", fontSize: 14, lineHeight: 1.55,
                         color: "var(--d-ink)", padding: "2px 0",
                         fontFamily: "var(--f-mono)" }}/>
              <span className="mono" style={{ fontSize: 11, color: "var(--d-muted)" }}>{draft.length}/2000</span>
              <button style={{ height: 28, padding: "0 12px", borderRadius: 6,
                                background: "var(--acc)", color: "var(--acc-ink)",
                                border: "none", fontSize: 12, fontWeight: 600,
                                fontFamily: "var(--f-mono)", cursor: "pointer",
                                display: "inline-flex", alignItems: "center", gap: 5 }}>
                ↩ enviar
              </button>
            </div>
            <div className="mono" style={{ display: "flex", justifyContent: "space-between", marginTop: 6,
                           fontSize: 10.5, color: "var(--d-muted)" }}>
              <span>laia · datos confinados a doyouwin · arch.audit on</span>
              <span>haiku-4-5 · turno 4 · 06:42 utc</span>
            </div>
          </div>
        </div>
      </section>

      {/* RAIL */}
      <aside style={opStyles.rail}>
        <div>
          <div style={opStyles.sect}><span>memoria activa</span></div>
          {AGORA_MEMORY.map((m) => (
            <div key={m.k} style={{ paddingBottom: 7, marginBottom: 7,
                                     borderBottom: "1px dashed var(--d-line)" }}>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)" }}>{m.k.toLowerCase()}</div>
              <div style={{ fontSize: 12, color: "var(--d-ink-2)", lineHeight: 1.4 }}>{m.v}</div>
            </div>
          ))}
        </div>

        <div>
          <div style={opStyles.sect}><span>hilos</span></div>
          {AGORA_RECENT_THREADS.map((th) => (
            <div key={th.id} style={{
              padding: "6px 8px", borderRadius: 6, marginBottom: 2,
              background: th.active ? "rgba(255,255,255,.04)" : "transparent",
              border: th.active ? "1px solid var(--d-line-2)" : "1px solid transparent",
              display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8,
              cursor: "pointer",
            }}>
              <span style={{ fontSize: 11.5, color: th.active ? "var(--d-ink)" : "var(--d-ink-2)",
                              fontWeight: th.active ? 600 : 400, overflow: "hidden",
                              textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{th.title}</span>
              <span className="mono" style={{ fontSize: 10, color: "var(--d-muted)" }}>{th.when}</span>
            </div>
          ))}
        </div>

        <div style={{ marginTop: "auto", padding: 10, border: "1px dashed var(--d-line-2)",
                       borderRadius: 6 }}>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)", marginBottom: 4 }}>contexto · hilo</div>
          <div style={{ fontSize: 12, color: "var(--d-ink)" }}>Auto Vidal · demo 10:30</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)", marginTop: 4 }}>
            decisor: <span style={{ color: "var(--d-ink-2)" }}>marta.r@autovidal</span>
          </div>
        </div>
      </aside>
    </div>
  );
}

/* messages */
function OpMsg({ m }) {
  if (m.from === "user") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 12, animation: "fadein .3s ease both" }}>
        <span className="mono" style={{ color: "var(--acc)", fontSize: 13, paddingTop: 1 }}>›</span>
        <div className="mono" style={{ color: "var(--d-ink)", fontSize: 13.5, lineHeight: 1.6 }}>{m.text}</div>
      </div>
    );
  }
  if (m.kind === "tool") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 12 }}>
        <span style={{ color: "var(--d-muted)", paddingTop: 2 }}><I.zap size={12}/></span>
        <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.55,
                                        color: "var(--d-ink-2)", border: "1px solid var(--d-line)",
                                        borderRadius: 6, padding: "6px 10px",
                                        background: "rgba(255,255,255,.02)" }}>
          <div>
            <span style={{ color: "var(--acc)" }}>{m.tool}</span>
            <span style={{ color: "var(--d-muted)" }}>(</span>
            {Object.entries(m.args).map(([k,v], i, a) => (
              <span key={k}>
                <span style={{ color: "var(--d-muted)" }}>{k}=</span>
                <span style={{ color: "var(--d-ink)" }}>"{v}"</span>
                {i < a.length-1 && <span style={{ color: "var(--d-muted)" }}>, </span>}
              </span>
            ))}
            <span style={{ color: "var(--d-muted)" }}>)</span>
          </div>
          <div style={{ paddingLeft: 14, position: "relative", color: "var(--d-ink-2)" }}>
            <span style={{ position: "absolute", left: 0, color: "var(--d-muted)" }}>→</span>{m.out}
          </div>
        </div>
      </div>
    );
  }
  if (m.kind === "artifact") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 12 }}>
        <span className="serif" style={{ color: "var(--acc)", fontSize: 18, paddingTop: 1 }}>L</span>
        <div style={{ border: "1px solid var(--d-line-2)", borderRadius: 8, overflow: "hidden",
                       background: "rgba(255,255,255,.02)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
                         borderBottom: "1px solid var(--d-line)" }}>
            <I.book size={13}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, color: "var(--d-ink)", fontWeight: 600 }}>{m.title}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--d-muted)" }}>{m.subtitle}</div>
            </div>
            <button style={opStyles.navBtn(false)}><I.copy size={11}/></button>
            <button style={{ ...opStyles.navBtn(false), background: "var(--acc)",
                              color: "var(--acc-ink)", borderColor: "var(--acc)" }}>abrir</button>
          </div>
          <div style={{ padding: "8px 12px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
            {m.sections.map((s, i) => (
              <div key={i} className="mono" style={{ display: "grid", gridTemplateColumns: "26px 1fr", gap: 8, fontSize: 11.5 }}>
                <span style={{ color: "var(--d-muted)" }}>0{i+1}</span>
                <div>
                  <div style={{ color: "var(--d-ink)" }}>{s.h}</div>
                  <div style={{ color: "var(--d-muted)", lineHeight: 1.5 }}>{s.p}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  if (m.kind === "thinking") {
    return (
      <div style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 12, alignItems: "center" }}>
        <span className="serif" style={{ color: "var(--acc)", fontSize: 18 }}>L</span>
        <div className="mono" style={{ fontSize: 12, color: "var(--d-muted)", display: "flex", gap: 8, alignItems: "center" }}>
          <span>redactando email…</span>
          {[0,1,2].map(i => (
            <span key={i} style={{ width: 4, height: 4, borderRadius: 999, background: "var(--acc)",
                                    animation: `pulse-dot 1.2s ease-in-out ${i*0.18}s infinite` }}/>
          ))}
          <span>· skill.email_seguimiento</span>
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "20px 1fr", gap: 12, animation: "fadein .3s ease both" }}>
      <span className="serif" style={{ color: "var(--acc)", fontSize: 18, paddingTop: 1 }}>L</span>
      <div style={{ fontSize: 14, lineHeight: 1.62, color: "var(--d-ink)" }}>{m.text}</div>
    </div>
  );
}

window.OperatorChat = OperatorChat;
