// AGORA · Variación 1 "Cockpit"
// Light DoYouWin chrome + dark AI/data panels.
// Exports: <CockpitShell view onView/> rendering Home / Chat.

const cpStyles = {
  root: {
    display: "grid",
    gridTemplateColumns: "232px 1fr",
    height: "100%",
    background: "transparent",
    color: "var(--l-ink)",
  },

  // sidebar
  side: {
    background: "var(--l-card)",
    borderRight: "1px solid var(--l-line)",
    display: "flex",
    flexDirection: "column",
    padding: "18px 14px 14px",
    gap: 18,
    minHeight: 0,
  },
  brand: { display: "flex", alignItems: "center", gap: 10, padding: "0 4px 4px", borderBottom: "1px solid var(--l-line)", paddingBottom: 14 },
  brandMark: {
    width: 28, height: 28, borderRadius: 8,
    background: "var(--acc)", color: "var(--acc-ink)",
    display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13,
    letterSpacing: ".02em",
    boxShadow: "0 1px 0 rgba(255,255,255,.6) inset, 0 1px 2px rgba(0,0,0,.12)",
  },
  brandWord: { fontFamily: "var(--f-display)", fontStyle: "italic", fontSize: 20, letterSpacing: ".005em" },
  brandSub: { fontSize: 10.5, color: "var(--l-muted)", letterSpacing: ".06em", textTransform: "uppercase" },

  navItem: (active) => ({
    display: "flex", alignItems: "center", gap: 10,
    height: "var(--row-h)", padding: "0 10px",
    borderRadius: 8, cursor: "pointer",
    color: active ? "var(--l-ink)" : "var(--l-ink-2)",
    background: active ? "var(--acc-soft)" : "transparent",
    fontWeight: active ? 600 : 500,
    fontSize: 13.5,
    border: active ? "1px solid var(--acc-line)" : "1px solid transparent",
  }),
  navTag: { marginLeft: "auto", fontSize: 10.5, color: "var(--l-muted)" },
  sectLabel: { fontSize: 10, fontWeight: 600, letterSpacing: ".1em", color: "var(--l-muted)", textTransform: "uppercase", padding: "6px 10px 0" },

  // appbar
  appbar: {
    height: 54, display: "flex", alignItems: "center",
    padding: "0 22px", gap: 14,
    borderBottom: "1px solid var(--l-line)", background: "var(--l-card)",
  },
  crumb: { display: "flex", alignItems: "center", gap: 8, color: "var(--l-muted)", fontSize: 13 },
  crumbCurrent: { color: "var(--l-ink)", fontWeight: 600 },
  search: {
    flex: 1, maxWidth: 480,
    display: "flex", alignItems: "center", gap: 8,
    height: 34, padding: "0 12px",
    background: "var(--l-subtle)", border: "1px solid var(--l-line)",
    borderRadius: 999, color: "var(--l-muted)",
  },
  kbd: {
    fontFamily: "var(--f-mono)", fontSize: 10.5, padding: "2px 5px",
    border: "1px solid var(--l-line-2)", borderRadius: 4,
    background: "var(--l-card)", color: "var(--l-muted)",
  },
  iconBtn: {
    width: 34, height: 34, borderRadius: 999,
    border: "1px solid var(--l-line)", background: "var(--l-card)",
    color: "var(--l-ink-2)", display: "grid", placeItems: "center",
    cursor: "pointer", position: "relative",
  },
  avatar: {
    width: 34, height: 34, borderRadius: 999,
    background: "linear-gradient(135deg, var(--acc) 0%, #8a3a26 100%)",
    color: "white", fontWeight: 600, display: "grid", placeItems: "center",
    fontSize: 12, letterSpacing: ".02em",
  },

  // content area
  main: { display: "flex", flexDirection: "column", height: "100%", minHeight: 0 },
  scroll: { flex: 1, overflow: "auto", padding: "var(--pad-2)" },

  // generic card
  card: {
    background: "var(--l-card)", border: "1px solid var(--l-line)",
    borderRadius: 14, padding: "var(--pad-2)",
  },
  cardDark: {
    background: "var(--d-bg)", color: "var(--d-ink)",
    border: "1px solid var(--d-line)", borderRadius: 14,
    padding: "var(--pad-2)",
  },

  pill: (variant = "default") => {
    const v = {
      default: { bg: "var(--l-subtle)", fg: "var(--l-ink-2)", bd: "var(--l-line)" },
      hot:     { bg: "color-mix(in oklab, var(--acc) 12%, transparent)", fg: "var(--acc)", bd: "var(--acc-line)" },
      warn:    { bg: "color-mix(in oklab, var(--warn) 14%, transparent)", fg: "var(--warn)", bd: "color-mix(in oklab, var(--warn) 30%, transparent)" },
      ok:      { bg: "color-mix(in oklab, var(--ok) 12%, transparent)", fg: "var(--ok)", bd: "color-mix(in oklab, var(--ok) 30%, transparent)" },
      auto:    { bg: "rgba(255,255,255,.06)", fg: "var(--d-ink-2)", bd: "var(--d-line-2)" },
    }[variant];
    return {
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 8px", borderRadius: 999,
      background: v.bg, color: v.fg, border: `1px solid ${v.bd}`,
      fontSize: 11, fontWeight: 600, letterSpacing: ".01em",
    };
  },

  btn: (variant = "default") => {
    const v = {
      default: { bg: "var(--l-card)", fg: "var(--l-ink)", bd: "var(--l-line-2)" },
      primary: { bg: "var(--acc)", fg: "var(--acc-ink)", bd: "var(--acc)" },
      ghost:   { bg: "transparent", fg: "var(--l-ink-2)", bd: "transparent" },
      darkPrimary: { bg: "var(--acc)", fg: "var(--acc-ink)", bd: "var(--acc)" },
    }[variant];
    return {
      height: 34, padding: "0 14px",
      borderRadius: 999, border: `1px solid ${v.bd}`,
      background: v.bg, color: v.fg,
      fontWeight: 600, fontSize: 13,
      display: "inline-flex", alignItems: "center", gap: 6,
      cursor: "pointer",
    };
  },
};

/* ----------------------- Sidebar ----------------------- */
function CpSidebar({ view, onView }) {
  const items = [
    { id: "home",  label: "Inicio",       icon: I.home,  active: view === "home" },
    { id: "chat",  label: "LAIA",         icon: I.bot,   active: view === "chat", tag: <span style={{ ...cpStyles.pill("hot"), padding: "1px 6px", fontSize: 9.5 }}>en línea</span> },
    { id: "back",  label: "Backlog",      icon: I.list },
    { id: "skill", label: "Skills",       icon: I.grid, tag: <span style={cpStyles.navTag}>·24</span> },
    { id: "coor",  label: "Coordinador",  icon: I.pulse },
    { id: "team",  label: "Equipo",       icon: I.team },
  ];
  return (
    <aside style={cpStyles.side}>
      <div style={cpStyles.brand}>
        <div style={cpStyles.brandMark}>A</div>
        <div>
          <div style={cpStyles.brandWord}>AGORA</div>
          <div style={cpStyles.brandSub}>by LAIA · DoYouWin</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {items.map((it) => (
          <div key={it.id}
               onClick={() => (it.id === "home" || it.id === "chat") && onView(it.id)}
               style={cpStyles.navItem(it.active)}>
            <it.icon size={16} />
            <span>{it.label}</span>
            {it.tag}
          </div>
        ))}
      </div>

      <div style={{ marginTop: "auto" }}>
        <div style={cpStyles.sectLabel}>Coordinador 24/7</div>
        <div style={{ padding: "6px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 12.5, color: "var(--l-ink-2)" }}>
            <span className="tab-num" style={{ fontWeight: 700, color: "var(--l-ink)" }}>17</span> acciones autónomas
            <span style={{ color: "var(--l-muted)" }}> · 24h</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--l-muted)" }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--ok)", animation: "pulse-dot 2.4s ease-in-out infinite" }}/>
            informe a ARCH · mañana 06:00
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ----------------------- Appbar ----------------------- */
function CpAppbar({ view, onView }) {
  const titles = { home: "Inicio", chat: "LAIA · María" };
  return (
    <header style={cpStyles.appbar}>
      <div style={cpStyles.crumb}>
        <span>AGORA</span>
        <I.chev size={12} />
        <span style={cpStyles.crumbCurrent}>{titles[view]}</span>
      </div>

      <div style={cpStyles.search}>
        <I.search size={14} />
        <span style={{ flex: 1, fontSize: 13 }}>Pregunta a LAIA o busca en backlog, skills, equipo…</span>
        <span style={cpStyles.kbd}>⌘K</span>
      </div>

      <button style={cpStyles.iconBtn} title="Notificaciones">
        <I.bell size={15}/>
        <span style={{ position: "absolute", top: 7, right: 8, width: 7, height: 7, borderRadius: 999, background: "var(--acc)", border: "1.5px solid var(--l-card)" }}/>
      </button>
      <button style={cpStyles.iconBtn} title="ARCH (sólo Jorge)" disabled>
        <I.arch size={15}/>
      </button>
      <div style={cpStyles.avatar}>{AGORA_USER.initials}</div>
    </header>
  );
}

/* ----------------------- HOME ----------------------- */
function CpHome({ onView }) {
  return (
    <div style={{ ...cpStyles.scroll, display: "grid",
                  gridTemplateColumns: "minmax(0,1.55fr) minmax(0,1fr)",
                  gap: "var(--pad-2)", alignContent: "start" }}>

      {/* hero brief — DARK panel (the AI surface) */}
      <section style={{ gridColumn: "1 / -1" }}>
        <CpHero onView={onView}/>
      </section>

      {/* today's tasks */}
      <section style={cpStyles.card}>
        <CardHead title="Hoy" meta={`${AGORA_TASKS.length} tareas · ${AGORA_BRIEF.date.toLowerCase()}`}
                  action={<button style={cpStyles.btn("ghost")}><I.plus size={14}/>nueva</button>} />
        <div style={{ display: "flex", flexDirection: "column", marginTop: 6 }}>
          {AGORA_TASKS.map((t, i) => <TaskRow key={t.id} t={t} last={i === AGORA_TASKS.length - 1}/>)}
        </div>
      </section>

      {/* coordinator pulse */}
      <section style={cpStyles.card}>
        <CardHead title="Coordinador 24/7"
                  meta={`${AGORA_COORDINATOR.toArch.actions24h} acciones · próximo informe a ARCH ${AGORA_COORDINATOR.toArch.next}`} />
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          {AGORA_COORDINATOR.events.map((e) => <CoordRow key={e.id} e={e}/>)}
        </div>
        <div style={{ borderTop: "1px solid var(--l-line)", marginTop: 12, paddingTop: 12,
                      display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12.5 }}>
          <span style={{ color: "var(--l-muted)" }}>El coordinador opera mientras duermes.</span>
          <button style={cpStyles.btn("default")}>Ver informe completo<I.arrowR size={14}/></button>
        </div>
      </section>

      {/* skills marketplace */}
      <section style={{ ...cpStyles.card, gridColumn: "1 / -1" }}>
        <CardHead title="Skill Marketplace"
                  meta="24 skills disponibles · 6 fijadas para ti"
                  action={<button style={cpStyles.btn("ghost")}>ver todas<I.arrowR size={14}/></button>}/>
        <div style={{ marginTop: 12, display: "grid",
                      gridTemplateColumns: "repeat(auto-fill,minmax(190px,1fr))", gap: 12 }}>
          {AGORA_SKILLS.map((s) => <SkillCard key={s.id} s={s}/>)}
        </div>
      </section>

      {/* backlog highlights */}
      <section style={cpStyles.card}>
        <CardHead title="Backlog compartido" meta="3 proyectos activos"
                  action={<button style={cpStyles.btn("ghost")}>abrir<I.arrowR size={14}/></button>}/>
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 12 }}>
          {AGORA_BACKLOG.map((b) => <BacklogRow key={b.id} b={b}/>)}
        </div>
      </section>

      {/* team */}
      <section style={cpStyles.card}>
        <CardHead title="Equipo" meta="4 personas · ahora"/>
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 10 }}>
          {AGORA_TEAM.map((p) => <TeamRow key={p.name} p={p}/>)}
        </div>
      </section>
    </div>
  );
}

function CpHero({ onView }) {
  return (
    <div style={{ ...cpStyles.cardDark, position: "relative", overflow: "hidden",
                   padding: "calc(var(--pad-2) + 4px)" }}>
      {/* bg flourish */}
      <div className="dotgrid" style={{ position: "absolute", inset: 0, opacity: .35, color: "white", pointerEvents: "none" }}/>
      <div style={{ position: "absolute", right: -90, top: -90, width: 320, height: 320, borderRadius: "50%",
                    background: "radial-gradient(circle, color-mix(in oklab, var(--acc) 28%, transparent), transparent 60%)",
                    filter: "blur(14px)", pointerEvents: "none" }}/>

      <div style={{ position: "relative", display: "grid", gridTemplateColumns: "minmax(0,1fr) 280px", gap: 28 }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8,
                         color: "var(--d-muted)", fontSize: 11.5, letterSpacing: ".08em",
                         textTransform: "uppercase", marginBottom: 10 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--acc)",
                            animation: "pulse-dot 2s ease-in-out infinite" }}/>
            LAIA · brief de la mañana · {AGORA_BRIEF.date}
          </div>
          <h1 style={{ fontFamily: "var(--f-display)", fontStyle: "italic",
                        fontSize: 38, lineHeight: 1.05, margin: "0 0 6px",
                        color: "var(--d-ink)", letterSpacing: "-.01em" }}>
            {AGORA_BRIEF.greeting}
          </h1>
          <p style={{ color: "var(--d-ink-2)", fontSize: 14.5, maxWidth: 580, margin: "0 0 18px" }}>
            {AGORA_BRIEF.summary}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {AGORA_BRIEF.priorities.map((p, i) => <PriorityRow key={p.id} p={p} i={i+1}/>)}
          </div>

          <div style={{ marginTop: 18, display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => onView("chat")} style={cpStyles.btn("darkPrimary")}>
              Empezar con LAIA<I.arrowR size={14}/>
            </button>
            <button style={{ ...cpStyles.btn("ghost"), color: "var(--d-ink-2)" }}>
              Reorganizar mi día
            </button>
            <span style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--d-muted)" }}>
              memoria sincronizada · hace 2 min
            </span>
          </div>
        </div>

        {/* mini status panel */}
        <div style={{ borderLeft: "1px solid var(--d-line)", paddingLeft: 22,
                       display: "flex", flexDirection: "column", gap: 14 }}>
          <Stat k="Reuniones hoy" v="2" sub="10:30 · 17:30"/>
          <Stat k="Llamadas SOFIA" v="14" sub="resumen listo"/>
          <Stat k="Leads activos" v="9" sub="1 caliente · 1 en riesgo"/>
          <Stat k="Tu memoria" v="142 hechos" sub={<span style={{ color: "var(--acc)" }}>+5 hoy</span>}/>
        </div>
      </div>
    </div>
  );
}

function PriorityRow({ p, i }) {
  const tagVariant = p.tag === "Riesgo" ? "warn" : p.tag === "Cierre" ? "ok" : "hot";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "22px 1fr auto", gap: 12,
                   alignItems: "center", padding: "10px 12px",
                   background: "rgba(255,255,255,.03)",
                   border: "1px solid var(--d-line)", borderRadius: 10 }}>
      <div className="mono" style={{ color: "var(--d-muted)", fontSize: 12 }}>0{i}</div>
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
          <span style={cpStyles.pill(tagVariant)}>{p.tag}</span>
          <span style={{ color: "var(--d-muted)", fontSize: 11.5 }}>{p.meta}</span>
        </div>
        <div style={{ color: "var(--d-ink)", fontSize: 14, fontWeight: 500 }}>{p.title}</div>
      </div>
      <button style={{ ...cpStyles.btn("ghost"), color: "var(--d-ink)",
                       border: "1px solid var(--d-line-2)" }}>
        {p.action}<I.arrowR size={13}/>
      </button>
    </div>
  );
}

function Stat({ k, v, sub }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--d-muted)", letterSpacing: ".06em", textTransform: "uppercase" }}>{k}</div>
      <div className="tab-num" style={{ fontFamily: "var(--f-display)", fontStyle: "italic", fontSize: 26, color: "var(--d-ink)", lineHeight: 1.1, marginTop: 2 }}>{v}</div>
      <div style={{ fontSize: 11.5, color: "var(--d-ink-2)" }}>{sub}</div>
    </div>
  );
}

function CardHead({ title, meta, action }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
      <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, letterSpacing: "-.005em" }}>{title}</h2>
      {meta && <span style={{ fontSize: 12, color: "var(--l-muted)" }}>{meta}</span>}
      <div style={{ marginLeft: "auto" }}>{action}</div>
    </div>
  );
}

function TaskRow({ t, last }) {
  const ico = t.status === "scheduled" ? "•" : "○";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "auto 60px 1fr auto",
                   gap: 12, alignItems: "center", padding: "10px 2px",
                   borderBottom: last ? "none" : "1px solid var(--l-line)" }}>
      <span className="mono" style={{ color: t.status === "scheduled" ? "var(--acc)" : "var(--l-muted-2)", fontSize: 14, width: 14 }}>{ico}</span>
      <span className="mono tab-num" style={{ fontSize: 12.5, color: "var(--l-muted)" }}>{t.when}</span>
      <span style={{ fontSize: 13.5, fontWeight: 500 }}>{t.title}</span>
      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <span style={cpStyles.pill("default")}>{t.via}</span>
        {t.skill !== "—" && <span style={{ fontSize: 11.5, color: "var(--l-muted)" }}>· {t.skill}</span>}
      </div>
    </div>
  );
}

function CoordRow({ e }) {
  const dot = e.kind === "alert" ? "var(--warn)" : e.kind === "report" ? "#7A5AE0" : "var(--ok)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "44px 8px 1fr auto", gap: 8, alignItems: "start" }}>
      <span className="mono tab-num" style={{ fontSize: 11.5, color: "var(--l-muted)", paddingTop: 2 }}>{e.at}</span>
      <span style={{ width: 6, height: 6, borderRadius: 999, background: dot, marginTop: 6 }}/>
      <span style={{ fontSize: 13 }}>{e.text}</span>
      <span style={{ ...cpStyles.pill(e.badge === "ARCH" ? "hot" : "default"), fontSize: 10 }}>{e.badge}</span>
    </div>
  );
}

function SkillCard({ s }) {
  return (
    <div style={{ border: "1px solid var(--l-line)", borderRadius: 12, padding: 14,
                   background: "var(--l-card)", display: "flex", flexDirection: "column", gap: 10,
                   minHeight: 110, position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: "var(--l-subtle)",
                       display: "grid", placeItems: "center", fontFamily: "var(--f-display)", fontStyle: "italic",
                       fontSize: 18, color: "var(--acc)" }}>{s.glyph}</div>
        <span style={{ fontSize: 11, color: "var(--l-muted)" }} className="tab-num">{s.uses} usos</span>
      </div>
      <div>
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>{s.name}</div>
        <div style={{ fontSize: 11.5, color: "var(--l-muted)", marginTop: 2 }}>por {s.by}</div>
      </div>
      <div style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={cpStyles.pill("default")}>fijada</span>
        <I.arrowR size={14} style={{ color: "var(--l-muted)" }}/>
      </div>
    </div>
  );
}

function BacklogRow({ b }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 13.5, fontWeight: 500 }}>{b.proj}</span>
        <span style={{ fontSize: 11.5, color: "var(--l-muted)" }}>{b.owner} · {b.items} ítems · {b.due}</span>
      </div>
      <div style={{ height: 6, background: "var(--l-subtle)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${Math.round(b.progress * 100)}%`, height: "100%",
                       background: "var(--acc)", borderRadius: 999 }}/>
      </div>
    </div>
  );
}

function TeamRow({ p }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{ width: 30, height: 30, borderRadius: 999, background: "var(--l-subtle)",
                     display: "grid", placeItems: "center", fontSize: 11, fontWeight: 700,
                     color: "var(--l-ink-2)" }}>{p.initials}</div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
        <div style={{ fontSize: 11.5, color: "var(--l-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p.status}
        </div>
      </div>
      <span style={{ fontSize: 10.5, padding: "2px 7px", borderRadius: 999,
                      background: "var(--l-subtle)", color: "var(--l-ink-2)",
                      border: "1px solid var(--l-line)" }}>{p.with}</span>
      <span style={{ width: 8, height: 8, borderRadius: 999, background: p.dot }}/>
    </div>
  );
}

Object.assign(window, {
  CockpitShell: function CockpitShell({ view, onView }) {
    return (
      <div style={cpStyles.root}>
        <CpSidebar view={view} onView={onView}/>
        <div style={cpStyles.main}>
          <CpAppbar view={view} onView={onView}/>
          {view === "home" ? <CpHome onView={onView}/> : <CockpitChat onView={onView}/>}
        </div>
      </div>
    );
  },
  cpStyles, CardHead,
});
