#!/usr/bin/env python3
"""
Seed script for the 'demo-completo' workspace.
Creates nodes of every type to exercise the full semantic zone layout.

Run:  python3 seed_demo.py
"""
import sys
import requests

BASE = "http://localhost:8077/api/workspaces/demo-completo"

def node(title: str, kind: str, parent_ref: str | None = None) -> dict:
    r = requests.post(f"{BASE}/nodes", json={
        "title": title,
        "kind": kind,
        "parent_ref": parent_ref,
        "content": f"Nodo de ejemplo: {title}",
    }, timeout=10)
    if not r.ok:
        print(f"  ERROR {r.status_code} al crear '{title}': {r.text[:200]}")
        sys.exit(1)
    data = r.json()
    slug = data.get("slug") or data.get("id")
    print(f"  ✓ [{kind:12s}] {title!r}  → {slug}")
    return data

def link(from_ref: str, to_ref: str, rel: str = "contains") -> None:
    r = requests.post(f"{BASE}/nodes/{from_ref}/links", json={
        "target_ref": to_ref,
        "rel": rel,
    }, timeout=10)
    if not r.ok:
        print(f"  WARN link {from_ref}→{to_ref}: {r.status_code}")

# ── ensure workspace directory exists ────────────────────────────────────────
import os, pathlib
ws_path = pathlib.Path.home() / ".hermes" / "workspaces" / "demo-completo"
ws_path.mkdir(parents=True, exist_ok=True)
print(f"Directorio: {ws_path}")

# ── warm up (creates workspace + index node) ──────────────────────────────────
print("Inicializando workspace 'demo-completo'...")
r = requests.get(f"{BASE}/nodes", timeout=10)
if not r.ok:
    print(f"ERROR al acceder al workspace: {r.status_code} {r.text[:200]}")
    sys.exit(1)
existing = {n["title"] for n in r.json()}
if len(existing) > 1:
    print(f"El workspace ya tiene {len(existing)} nodos. Abortando para no duplicar.")
    print("Si quieres regenerarlo, borra ~/.hermes/workspaces/demo-completo primero.")
    sys.exit(0)
print(f"OK — workspace listo.\n")

# ── projects ──────────────────────────────────────────────────────────────────
print("Creando projects...")
alpha   = node("Proyecto Alpha",   "project")   # left side
beta    = node("Proyecto Beta",    "project")   # left side
gamma   = node("Proyecto Gamma",   "project")   # right side
delta   = node("Proyecto Delta",   "project")   # right side
epsilon = node("Proyecto Epsilon", "project")   # extra (right)

# ── global topics (not under any project) ─────────────────────────────────────
print("\nCreando topics globales...")
t_tech = node("Tecnología",    "topic")
t_seg  = node("Seguridad",     "topic")
t_arch = node("Arquitectura",  "topic")

# ── global topic children ────────────────────────────────────────────────────
print("\nCreando hijos de topics globales...")
node("Stack Técnico",           "doc",       parent_ref=t_tech["slug"])
node("Comparativa Frameworks",  "doc",       parent_ref=t_tech["slug"])
node("Roadmap Técnico",         "reference", parent_ref=t_tech["slug"])
node("Políticas de Seguridad",  "doc",       parent_ref=t_seg["slug"])
node("OWASP Top 10",            "reference", parent_ref=t_seg["slug"])
node("Diagrama de Sistema",     "doc",       parent_ref=t_arch["slug"])

# ── global important ──────────────────────────────────────────────────────────
print("\nCreando important globales...")
node("Objetivo Q2 2025",        "important")
node("Decisión Crítica #1",     "important")

# ── global orphan docs / references ──────────────────────────────────────────
print("\nCreando docs y references huérfanos...")
node("Guía de Onboarding",      "doc")
node("Acuerdos de Equipo",      "doc")
node("FAQ General",             "doc")
node("Documentación Externa",   "reference")
node("Licencias OSS",           "reference")

# ── global scripts ────────────────────────────────────────────────────────────
print("\nCreando scripts globales...")
node("Setup Inicial",           "script")
node("Backup Automático",       "script")

# ── global agent notes ────────────────────────────────────────────────────────
print("\nCreando nodos agenticos globales...")
team = node("agents/team.md — demo", "agent-note")
log = node("agents/log.md — demo", "agent-log")
plan = node("Plan Demo", "agent-plan", parent_ref=team["slug"])
node("Log Plan Demo", "agent-log", parent_ref=plan["slug"])

# ── Proyecto Alpha ─────────────────────────────────────────────────────────────
print("\nCreando contenido de Proyecto Alpha...")
ta1 = node("Diseño UI",             "topic",     parent_ref=alpha["slug"])
ta2 = node("Backend Alpha",         "topic",     parent_ref=alpha["slug"])
# topic children
node("Guía de Estilos",             "doc",       parent_ref=ta1["slug"])
node("Componentes UI",              "doc",       parent_ref=ta1["slug"])
node("Mockups v2",                  "doc",       parent_ref=ta1["slug"])
node("Design System Ref",           "reference", parent_ref=ta1["slug"])
node("API Docs Alpha",              "doc",       parent_ref=ta2["slug"])
node("DB Schema v3",                "doc",       parent_ref=ta2["slug"])
# orphan docs under alpha (no topic)
node("Roadmap Alpha 2025",          "doc",       parent_ref=alpha["slug"])
node("Presupuesto Alpha",           "doc",       parent_ref=alpha["slug"])
# scripts
node("Deploy Alpha",                "script",    parent_ref=alpha["slug"])
node("Test Suite Alpha",            "script",    parent_ref=alpha["slug"])
# agent
node("Comportamiento Alpha",        "agent-note",parent_ref=alpha["slug"])
# important
node("Urgente: Fix Auth Bug",       "important", parent_ref=alpha["slug"])

# ── Proyecto Beta ──────────────────────────────────────────────────────────────
print("\nCreando contenido de Proyecto Beta...")
tb1 = node("Research Beta",         "topic",     parent_ref=beta["slug"])
tb2 = node("Producto Beta",         "topic",     parent_ref=beta["slug"])
node("Investigación Inicial",       "doc",       parent_ref=tb1["slug"])
node("Análisis Competencia",        "doc",       parent_ref=tb1["slug"])
node("Papers de Referencia",        "reference", parent_ref=tb1["slug"])
node("Feature Spec v1",             "doc",       parent_ref=tb2["slug"])
node("User Stories",                "doc",       parent_ref=tb2["slug"])
node("Analizador Beta",             "script",    parent_ref=beta["slug"])
node("Decisiones Beta",             "agent-note",parent_ref=beta["slug"])

# ── Proyecto Gamma ─────────────────────────────────────────────────────────────
print("\nCreando contenido de Proyecto Gamma...")
tg1 = node("Marketing Gamma",       "topic",     parent_ref=gamma["slug"])
node("Estrategia Go-to-Market",     "doc",       parent_ref=tg1["slug"])
node("Métricas KPI",                "doc",       parent_ref=tg1["slug"])
node("Brief Gamma",                 "doc",       parent_ref=gamma["slug"])
node("Contrato Cliente",            "reference", parent_ref=gamma["slug"])
node("Urgente Gamma",               "important", parent_ref=gamma["slug"])
node("Build Gamma",                 "script",    parent_ref=gamma["slug"])

# ── Proyecto Delta ─────────────────────────────────────────────────────────────
print("\nCreando contenido de Proyecto Delta...")
node("Procesador Delta",            "script",    parent_ref=delta["slug"])
node("Config Delta",                "doc",       parent_ref=delta["slug"])
node("Agente Delta",                "agent-note",parent_ref=delta["slug"])

# ── Proyecto Epsilon (minimal, sólo el nodo) ──────────────────────────────────
print("\nCreando contenido de Proyecto Epsilon...")
node("Notas Epsilon",               "doc",       parent_ref=epsilon["slug"])

print("\n✅ Workspace 'demo-completo' creado con éxito.")
print(f"   Ábrelo en: http://localhost:8077  → workspace 'demo-completo' → Grafo")
