// AGORA · Cockpit · Chat
// Right-rail (LAIA identity, dark) + center thread (light) + inspector (light).

function CockpitChat({ onView }) {
  const [draft, setDraft] = React.useState("");
  return (
    <div style={{ display: "grid",
                  gridTemplateColumns: "260px minmax(0,1fr) 280px",
                  height: "100%", minHeight: 0 }}>

      {/* LAIA identity rail — DARK */}
      <aside style={{ background: "var(--d-bg)", color: "var(--d-ink)",
                      borderRight: "1px solid var(--d-line)",
                      padding: "var(--pad-2) var(--pad)",
                      display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ position: "relative", width: 40, height: 40, borderRadius: 12,
                          background: "linear-gradient(135deg, #2A2D38 0%, #14161D 100%)",
                          border: "1px solid var(--d-line-2)",
                          display: "grid", placeItems: "center" }}>
              <span className="serif" style={{ color: "var(--acc)", fontSize: 22 }}>L</span>
              <span style={{ position: "absolute", right: -2, bottom: -2, width: 12, height: 12,
                              borderRadius: 999, background: "var(--ok)", border: "2px solid var(--d-bg)" }}/>
            </div>
            <div>
              <div style={{ fontSize: 14.5, fontWeight: 600, letterSpacing: ".005em" }}>LAIA</div>
              <div style={{ fontSize: 11.5, color: "var(--d-muted)" }}>· María · activa</div>
            </div>
          </div>
          <p style={{ margin: "12px 0 0", fontSize: 12, color: "var(--d-ink-2)", lineHeight: 1.55 }}>
            Tu medio personal con la inteligencia LAIA. Recuerda tu contexto, tus cuentas y tu estilo.
          </p>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em",
                         textTransform: "uppercase", color: "var(--d-muted)", marginBottom: 8 }}>Memoria activa</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {AGORA_MEMORY.map((m) => (
              <div key={m.k} style={{ fontSize: 11.5, lineHeight: 1.4 }}>
                <span style={{ color: "var(--d-muted)" }}>{m.k}</span><br/>
                <span style={{ color: "var(--d-ink)" }}>{m.v}</span>
              </div>
            ))}
          </div>
          <button style={{ marginTop: 10, background: "transparent", border: "1px dashed var(--d-line-2)",
                            color: "var(--d-ink-2)", borderRadius: 8, padding: "6px 8px",
                            fontSize: 11.5, width: "100%", cursor: "pointer", display: "flex",
                            alignItems: "center", justifyContent: "center", gap: 6 }}>
            <I.book size={12}/> ver memoria completa
          </button>
        </div>

        <div style={{ marginTop: "auto", borderTop: "1px solid var(--d-line)", paddingTop: 14, minHeight: 0, overflow: "auto" }} className="thin-scroll">
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em",
                         textTransform: "uppercase", color: "var(--d-muted)", marginBottom: 8 }}>Hilos recientes</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {AGORA_RECENT_THREADS.map((th) => (
              <div key={th.id} style={{
                padding: "8px 10px", borderRadius: 8, cursor: "pointer",
                background: th.active ? "rgba(255,255,255,.04)" : "transparent",
                border: th.active ? "1px solid var(--d-line-2)" : "1px solid transparent",
                display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8,
              }}>
                <span style={{ fontSize: 12, color: th.active ? "var(--d-ink)" : "var(--d-ink-2)",
                                fontWeight: th.active ? 600 : 400, overflow: "hidden",
                                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{th.title}</span>
                <span style={{ fontSize: 10.5, color: "var(--d-muted)" }}>{th.when}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* CENTER — conversation */}
      <section style={{ display: "flex", flexDirection: "column", minHeight: 0,
                         background: "var(--l-bg)" }}>
        <div className="thin-scroll" style={{ flex: 1, overflow: "auto", padding: "28px 36px 20px" }}>
          <div style={{ maxWidth: 720, margin: "0 auto", display: "flex", flexDirection: "column", gap: 18 }}>
            <ThreadHeader/>
            {AGORA_THREAD.map((m) => <Msg key={m.id} m={m}/>)}
          </div>
        </div>
        <Composer draft={draft} setDraft={setDraft}/>
      </section>

      {/* INSPECTOR — right */}
      <aside style={{ background: "var(--l-card)", borderLeft: "1px solid var(--l-line)",
                       padding: "var(--pad-2) var(--pad)", display: "flex", flexDirection: "column",
                       gap: 14, minHeight: 0, overflow: "auto" }} className="thin-scroll">
        <div>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em",
                         textTransform: "uppercase", color: "var(--l-muted)", marginBottom: 8 }}>Contexto del hilo</div>
          <div style={{ ...cpStyles.pill("hot"), marginBottom: 10 }}>📌 Auto Vidal · 10:30</div>
          <div style={{ fontSize: 12.5, color: "var(--l-ink-2)", lineHeight: 1.55 }}>
            LAIA está trabajando en la demo del módulo de campañas para Auto Vidal.
            Decisor: <b style={{ color: "var(--l-ink)" }}>Marta R.</b> · CMO.
          </div>
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em",
                         textTransform: "uppercase", color: "var(--l-muted)", marginBottom: 8 }}>Skills en uso</div>
          {[
            { n: "Guion de demo",        m: "ejecutado · 12s" },
            { n: "Generador de email",   m: "en curso…" },
            { n: "Consulta CRM",         m: "ejecutado · 0.4s" },
          ].map((s) => (
            <div key={s.n} style={{ display: "flex", justifyContent: "space-between",
                                     padding: "7px 0", borderBottom: "1px solid var(--l-line)",
                                     fontSize: 12.5 }}>
              <span>{s.n}</span><span style={{ color: "var(--l-muted)" }}>{s.m}</span>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: ".1em",
                         textTransform: "uppercase", color: "var(--l-muted)", marginBottom: 8 }}>Tareas vinculadas</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {AGORA_TASKS.slice(0,3).map((t) => (
              <div key={t.id} style={{ display: "flex", gap: 8, fontSize: 12.5,
                                        padding: "6px 8px", borderRadius: 6,
                                        border: "1px solid var(--l-line)", background: "var(--l-bg)" }}>
                <span className="mono" style={{ color: "var(--l-muted)" }}>{t.when}</span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.title}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: "auto", padding: 12, borderRadius: 10,
                       background: "var(--acc-soft)", border: "1px solid var(--acc-line)",
                       fontSize: 12, color: "var(--l-ink-2)", lineHeight: 1.55 }}>
          <div style={{ fontWeight: 600, color: "var(--l-ink)", marginBottom: 4 }}>Mismo hilo, ayer</div>
          Repasaste con LAIA la propuesta de Auto Vidal. Hoy retomáis con el guion de demo.
        </div>
      </aside>
    </div>
  );
}

function ThreadHeader() {
  return (
    <div style={{ paddingBottom: 14, borderBottom: "1px solid var(--l-line)",
                   display: "flex", alignItems: "center", gap: 10 }}>
      <span className="serif" style={{ fontSize: 22, lineHeight: 1, color: "var(--acc)" }}>L</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 15, fontWeight: 600 }}>LAIA · María</div>
        <div style={{ fontSize: 12, color: "var(--l-muted)" }}>
          memoria personal · 142 hechos · sincronizada hace 2 min
        </div>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <button style={cpStyles.btn("default")}><I.pin size={13}/>fijar</button>
        <button style={cpStyles.btn("default")}><I.loop size={13}/>nuevo hilo</button>
      </div>
    </div>
  );
}

/* ----- messages ----- */
function Msg({ m }) {
  if (m.from === "user") return <UserMsg m={m}/>;
  if (m.kind === "tool") return <ToolMsg m={m}/>;
  if (m.kind === "artifact") return <ArtifactMsg m={m}/>;
  if (m.kind === "thinking") return <ThinkingMsg/>;
  return <LaiaMsg m={m}/>;
}

function UserMsg({ m }) {
  return (
    <div style={{ alignSelf: "flex-end", maxWidth: "78%", animation: "fadein .3s ease both" }}>
      <div style={{ background: "var(--l-ink)", color: "var(--l-card)",
                    padding: "10px 14px", borderRadius: "16px 16px 4px 16px",
                    fontSize: 14, lineHeight: 1.5 }}>
        {m.text}
      </div>
      <div style={{ fontSize: 11, color: "var(--l-muted)", marginTop: 4, textAlign: "right" }}>María · ahora</div>
    </div>
  );
}

function LaiaMsg({ m }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start", animation: "fadein .3s ease both" }}>
      <span className="serif" style={{ fontSize: 20, lineHeight: 1, color: "var(--acc)", paddingTop: 2 }}>L</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, lineHeight: 1.62, color: "var(--l-ink)" }}>{m.text}</div>
      </div>
    </div>
  );
}

function ToolMsg({ m }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <span style={{ width: 20 }}/>
      <div style={{ flex: 1, border: "1px dashed var(--l-line-2)",
                    background: "var(--l-subtle)", borderRadius: 8,
                    padding: "8px 12px", fontFamily: "var(--f-mono)", fontSize: 12,
                    color: "var(--l-ink-2)" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
          <I.zap size={12} />
          <span style={{ color: "var(--acc)", fontWeight: 600 }}>{m.tool}</span>
          <span style={{ color: "var(--l-muted)" }}>
            ({Object.entries(m.args).map(([k,v]) => `${k}: "${v}"`).join(", ")})
          </span>
        </div>
        <div style={{ color: "var(--l-ink-2)", paddingLeft: 18, position: "relative" }}>
          <span style={{ position: "absolute", left: 0, color: "var(--l-muted)" }}>→</span>
          {m.out}
        </div>
      </div>
    </div>
  );
}

function ArtifactMsg({ m }) {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <span style={{ width: 20 }}/>
      <div style={{ flex: 1, border: "1px solid var(--l-line)",
                    background: "var(--l-card)", borderRadius: 12, overflow: "hidden",
                    boxShadow: "0 1px 0 rgba(0,0,0,.02), 0 6px 24px rgba(20,16,5,.06)" }}>
        <div style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 10,
                       borderBottom: "1px solid var(--l-line)" }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "var(--acc-soft)",
                         color: "var(--acc)", display: "grid", placeItems: "center" }}>
            <I.book size={14}/>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{m.title}</div>
            <div style={{ fontSize: 11.5, color: "var(--l-muted)" }}>{m.subtitle}</div>
          </div>
          <button style={cpStyles.btn("default")}><I.copy size={12}/></button>
          <button style={cpStyles.btn("primary")}>Abrir</button>
        </div>
        <div style={{ padding: "10px 16px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
          {m.sections.map((s, i) => (
            <div key={i} style={{ paddingLeft: 18, position: "relative" }}>
              <span className="mono" style={{ position: "absolute", left: 0, color: "var(--l-muted)", fontSize: 11, top: 2 }}>0{i+1}</span>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{s.h}</div>
              <div style={{ fontSize: 12.5, color: "var(--l-muted)", lineHeight: 1.5 }}>{s.p}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ThinkingMsg() {
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      <span className="serif" style={{ fontSize: 20, color: "var(--acc)" }}>L</span>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--l-muted)" }}>
        <span>redactando email</span>
        {[0,1,2].map(i => (
          <span key={i} style={{ width: 5, height: 5, borderRadius: 999, background: "var(--acc)",
                                  animation: `pulse-dot 1.2s ease-in-out ${i*0.18}s infinite` }}/>
        ))}
        <span style={{ marginLeft: 8 }}>· skill ‘Email de seguimiento’</span>
      </div>
    </div>
  );
}

function Composer({ draft, setDraft }) {
  return (
    <div style={{ borderTop: "1px solid var(--l-line)", background: "var(--l-card)",
                   padding: "12px 36px 18px" }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
          {["Resumir hilo","Crear tarea","Borrador de email","Comparar con ayer"].map(c => (
            <button key={c} style={{ ...cpStyles.btn("default"), height: 28, fontSize: 12 }}>{c}</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8,
                       border: "1px solid var(--l-line-2)", borderRadius: 14,
                       padding: "10px 12px", background: "var(--l-bg)" }}>
          <button style={{ ...cpStyles.btn("ghost"), padding: 6 }}><I.paperclip size={16}/></button>
          <textarea
            value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Escribe a LAIA… (⌘↩ para enviar)"
            rows={1}
            style={{ flex: 1, border: "none", outline: "none", resize: "none",
                     background: "transparent", fontSize: 14, lineHeight: 1.55,
                     color: "var(--l-ink)", padding: "4px 0" }}/>
          <span style={{ fontSize: 11, color: "var(--l-muted)", whiteSpace: "nowrap" }}>{draft.length}/2000</span>
          <button style={{ ...cpStyles.btn("primary"), padding: "0 12px" }}>
            <I.send size={14}/>enviar
          </button>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6,
                       fontSize: 11, color: "var(--l-muted)" }}>
          <span>LAIA usa tu memoria personal y skills compartidas. No comparte datos fuera de DoYouWin.</span>
          <span>haiku-4-5 · turno 4 de hoy</span>
        </div>
      </div>
    </div>
  );
}

window.CockpitChat = CockpitChat;
