export const KIND_CHIP: Record<string, string> = {
  index:        'bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-400/30',
  project:      'bg-orange-500/15 text-orange-300 ring-1 ring-inset ring-orange-400/30',
  topic:        'bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-400/30',
  important:    'bg-red-500/15 text-red-300 ring-1 ring-inset ring-red-400/30',
  doc:          'bg-zinc-600/25 text-zinc-200 ring-1 ring-inset ring-zinc-400/20',
  script:       'bg-yellow-500/15 text-yellow-300 ring-1 ring-inset ring-yellow-400/30',
  reference:    'bg-cyan-500/15 text-cyan-300 ring-1 ring-inset ring-cyan-400/30',
  'agent-note': 'bg-pink-500/15 text-pink-300 ring-1 ring-inset ring-pink-400/30',
  'agent-plan': 'bg-violet-500/15 text-violet-300 ring-1 ring-inset ring-violet-400/30',
  'agent-log':  'bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-400/30',
  'agent-node': 'bg-zinc-500/20 text-zinc-300 ring-1 ring-inset ring-zinc-400/25',
  detail:       'bg-zinc-500/20 text-zinc-300 ring-1 ring-inset ring-zinc-400/25',
}

export const KIND_NODE_COLOR: Record<string, string> = {
  index:        '#ffc45a',
  project:      '#f97316',
  topic:        '#10b981',
  important:    '#ef4444',
  doc:          '#52525b',
  script:       '#eab308',
  reference:    '#06b6d4',
  'agent-note': '#ec4899',
  'agent-plan': '#8b5cf6',
  'agent-log':  '#0ea5e9',
  'agent-node': '#71717a',
  detail:       '#71717a',
}

export const KIND_DOT: Record<string, string> = {
  index:        'bg-amber-400',
  project:      'bg-orange-400',
  topic:        'bg-emerald-400',
  important:    'bg-red-400',
  doc:          'bg-zinc-300',
  script:       'bg-yellow-400',
  reference:    'bg-cyan-400',
  'agent-note': 'bg-pink-400',
  'agent-plan': 'bg-violet-400',
  'agent-log':  'bg-sky-400',
  'agent-node': 'bg-zinc-400',
  detail:       'bg-zinc-400',
}

export function kindClass(kind: string): string {
  return KIND_CHIP[kind] ?? 'bg-zinc-500/15 text-zinc-300 ring-1 ring-inset ring-zinc-400/25'
}

export function kindDot(kind: string): string {
  return KIND_DOT[kind] ?? 'bg-zinc-400'
}

export function kindNodeColor(kind: string): string {
  return KIND_NODE_COLOR[kind] ?? '#52525b'
}

export const ALL_KINDS = ['index', 'project', 'topic', 'important', 'doc', 'script', 'reference', 'agent-note', 'agent-plan', 'agent-log']
