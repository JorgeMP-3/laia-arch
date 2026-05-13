// Mock data for AGORA prototype.
// All in Spanish, contextualized to DoYouWin / MyHelpCar (automoción).

const AGORA_USER = {
  name: "María Lasaga",
  short: "María",
  role: "Account Manager · Concesionarios",
  initials: "ML",
  team: "DoYouWin · Madrid",
};

const AGORA_BRIEF = {
  greeting: "Buenos días, María.",
  date: "Jueves · 8 de mayo",
  // LAIA's morning brief — what she prioritized for María overnight
  summary: "He revisado tu agenda, los leads activos y tres conversaciones del CRM. Tres cosas que merecen tu atención hoy:",
  priorities: [
    {
      id: "p1",
      tag: "Lead caliente",
      title: "Auto Vidal pidió segunda demo del módulo de campañas.",
      meta: "WhatsApp · 07:42",
      action: "Preparar demo",
    },
    {
      id: "p2",
      tag: "Riesgo",
      title: "Concesiones Norte lleva 11 días sin abrir el dashboard.",
      meta: "SOFIA flagueó churn",
      action: "Llamar a Andrés",
    },
    {
      id: "p3",
      tag: "Cierre",
      title: "Propuesta de Motor Sur lista para revisar.",
      meta: "Borrador v3 · 2 cambios sugeridos",
      action: "Revisar borrador",
    },
  ],
};

const AGORA_TASKS = [
  { id: "t1", title: "Demo módulo campañas — Auto Vidal",         when: "10:30",  via: "Calendly",   skill: "Reuniones",     status: "scheduled" },
  { id: "t2", title: "Llamar a Andrés (Concesiones Norte)",       when: "12:00",  via: "SOFIA",      skill: "Retención",     status: "todo" },
  { id: "t3", title: "Revisar propuesta Motor Sur — v3",          when: "14:00",  via: "Backlog",    skill: "Propuestas",    status: "todo" },
  { id: "t4", title: "Cerrar onboarding — Talleres Pérez",        when: "16:00",  via: "CRM",        skill: "Onboarding",    status: "todo" },
  { id: "t5", title: "Sync semanal con Jorge",                    when: "17:30",  via: "Meet",       skill: "—",             status: "scheduled" },
];

const AGORA_SKILLS = [
  { id: "s1", name: "Generador de propuestas",      glyph: "✶", uses: 142, by: "Equipo Comercial" },
  { id: "s2", name: "Resumen de llamada (SOFIA)",    glyph: "◐", uses: 318, by: "DoYouWin core" },
  { id: "s3", name: "Análisis de churn",             glyph: "△", uses:  47, by: "Data" },
  { id: "s4", name: "Email de seguimiento",          glyph: "✎", uses: 211, by: "María L." },
  { id: "s5", name: "Comparador de ofertas",         glyph: "◇", uses:  62, by: "Equipo Comercial" },
  { id: "s6", name: "Brief de concesionario",        glyph: "▢", uses:  28, by: "Marketing" },
];

const AGORA_COORDINATOR = {
  // autonomous actions in the last 24h, latest first
  events: [
    { id: "c1", at: "06:02", kind: "report",  text: "Informe diario enviado a ARCH.",                                  badge: "ARCH" },
    { id: "c2", at: "04:18", kind: "skill",   text: "Skill ‘Resumen de llamada’ procesó 14 grabaciones de SOFIA.",     badge: "auto" },
    { id: "c3", at: "23:47", kind: "alert",   text: "Detectado riesgo de churn en Concesiones Norte — añadido a hoy.", badge: "auto" },
    { id: "c4", at: "22:10", kind: "backlog", text: "Movió 3 tareas de ‘próximas’ a ‘hoy’ según prioridad de Jorge.",  badge: "auto" },
    { id: "c5", at: "20:34", kind: "skill",   text: "Generó borrador v3 de propuesta Motor Sur.",                      badge: "auto" },
  ],
  toArch: { last: "06:02", next: "mañana 06:00", actions24h: 17 },
};

const AGORA_BACKLOG = [
  { id: "b1", proj: "Lanzamiento campaña Q2",   owner: "María",       progress: 0.62, items: 14, due: "23 may" },
  { id: "b2", proj: "Onboarding Talleres Pérez", owner: "Equipo SAT",  progress: 0.30, items:  9, due: "30 may" },
  { id: "b3", proj: "Pilot SOFIA · postventa",   owner: "Andrés",      progress: 0.85, items: 22, due: "15 may" },
];

const AGORA_TEAM = [
  { name: "Andrés P.", initials: "AP", status: "En llamada con Concesiones Norte", with: "SOFIA",  dot: "#1F8A5B" },
  { name: "Lucía R.",  initials: "LR", status: "Editando propuesta Motor Sur",      with: "LAIA",   dot: "#FF5A3C" },
  { name: "Jorge M.",  initials: "JM", status: "ARCH · revisión nocturna",          with: "ARCH",   dot: "#7A5AE0" },
  { name: "Pau S.",    initials: "PS", status: "Reunión externa",                   with: "—",      dot: "#9A9892" },
];

// chat thread — María & LAIA. Mix of prose, tool-use, and an artifact card.
const AGORA_THREAD = [
  { id: "m1", from: "laia", kind: "text",
    text: "Buenos días, María. Te he preparado el brief del día — empieza por Auto Vidal a las 10:30. ¿Repasamos juntas la demo o prefieres que prepare el guion?" },
  { id: "m2", from: "user", kind: "text",
    text: "Prepara el guion. Y mira si han abierto algo del dashboard esta semana." },
  { id: "m3", from: "laia", kind: "tool", tool: "consultar_crm",
    args: { cuenta: "Auto Vidal", rango: "7d" },
    out: "12 sesiones · 3 usuarios · módulo más visto: Campañas (47%)" },
  { id: "m4", from: "laia", kind: "tool", tool: "skill.guion_demo",
    args: { foco: "campañas", duracion: "20min" },
    out: "Guion v1 generado · 4 secciones · 3 preguntas de descubrimiento" },
  { id: "m5", from: "laia", kind: "artifact",
    title: "Guion · Demo Auto Vidal · 10:30",
    subtitle: "4 secciones · 20 min · foco campañas",
    sections: [
      { h: "Apertura · 2 min",       p: "Recap del piloto. Pregunta abierta sobre lo que más han usado." },
      { h: "Demo módulo campañas",   p: "Caso real: campaña SEAT últimos 7 días, métricas en directo." },
      { h: "Descubrimiento · 5 min", p: "Tres preguntas sobre objetivos Q3, presupuesto, decisor final." },
      { h: "Cierre · próximos pasos", p: "Propuesta para el viernes si encajan tiempos." },
    ] },
  { id: "m6", from: "laia", kind: "text",
    text: "He fijado el guion en este hilo y añadido la cuenta a tu memoria. Si quieres, también puedo redactar el email previo — ya tengo la firma habitual de Auto Vidal en el CRM." },
  { id: "m7", from: "user", kind: "text",
    text: "Sí, redacta el email. Tono cercano pero profesional, como con Lucía la semana pasada." },
  { id: "m8", from: "laia", kind: "thinking" },
];

const AGORA_MEMORY = [
  { k: "Cuentas activas",        v: "9 concesionarios · 3 grupos" },
  { k: "Estilo de email",        v: "cercano · 2-3 párrafos · sin jerga" },
  { k: "Reuniones favoritas",    v: "martes/jueves · mañana" },
  { k: "Productos clave",        v: "campañas, postventa SOFIA, dashboards" },
  { k: "Decisor en Auto Vidal",  v: "Marta R. (CMO) · email confirmado" },
];

const AGORA_RECENT_THREADS = [
  { id: "th1", title: "Demo Auto Vidal · 10:30",       when: "ahora",       active: true  },
  { id: "th2", title: "Propuesta Motor Sur",            when: "ayer",        active: false },
  { id: "th3", title: "Plan de retención · Norte",      when: "ayer",        active: false },
  { id: "th4", title: "Onboarding Talleres Pérez",     when: "lun.",        active: false },
  { id: "th5", title: "Brief Q2 con Jorge",             when: "1 may.",      active: false },
];

Object.assign(window, {
  AGORA_USER, AGORA_BRIEF, AGORA_TASKS, AGORA_SKILLS,
  AGORA_COORDINATOR, AGORA_BACKLOG, AGORA_TEAM,
  AGORA_THREAD, AGORA_MEMORY, AGORA_RECENT_THREADS,
});
