import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Save, Trash2, Eye, Code2, Plus, X, Link2, CheckCircle2, Hash, Tag, CornerDownRight } from 'lucide-react'
import { api } from '../lib/api'
import type { Node, NodePayload } from '../lib/api'
import { kindClass, ALL_KINDS } from '../lib/kind'
import { relativeTime } from '../lib/time'
import { useChatContext } from '../App'

const EDGE_TYPES = ['contains', 'references', 'depends_on', 'related_to']

function escape(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderInline(s: string) {
  return escape(s)
    .replace(/`([^`]+?)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, (_full, label, href) => {
      const isAnchor = href.startsWith('#')
      return `<a href="${href}"${isAnchor ? '' : ' target="_blank" rel="noreferrer"'} class="md-link">${label}</a>`
    })
}

function renderMarkdown(src: string): string {
  if (!src.trim()) return ''

  // 1. Remove horizontal rules (--- on its own line)
  let text = src.replace(/^---+$/gm, '')

  // 2. Handle fenced code blocks first (must preserve newlines inside)
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    return `<pre class="md-pre"><code class="inline-code">${escape(code.trimEnd())}</code></pre>`
  })

  // 3. Handle inline code (backticks) before other processing
  // (already done in renderInline, but we need to protect already-processed pre blocks)
  // Split into lines, process each, reassemble
  const lines = text.split('\n')
  const processed: string[] = []
  let inPreBlock = false

  for (const line of lines) {
    if (line.trim().startsWith('<pre')) inPreBlock = true
    if (inPreBlock) {
      processed.push(line)
      if (line.trim().endsWith('</pre>')) inPreBlock = false
      continue
    }

    // Block-level elements: headings, list items, blockquotes, tables, hr, paragraphs
    const stripped = line.trimEnd()

    // Headings
    const hMatch = stripped.match(/^(#{1,4})\s+(.*)$/)
    if (hMatch) {
      processed.push(`<h${hMatch[1].length} class="md-h${hMatch[1].length}">${renderInline(hMatch[2])}</h${hMatch[1].length}>`)
      continue
    }

    // Blockquote
    if (stripped.startsWith('> ')) {
      processed.push(`<blockquote class="md-blockquote">${renderInline(stripped.replace(/^>\s?/, ''))}</blockquote>`)
      continue
    }

    // Unordered list item
    if (/^-\s/.test(stripped) || /^\*\s/.test(stripped)) {
      processed.push(`<li class="md-li">${renderInline(stripped.replace(/^[*-]\s+/, ''))}</li>`)
      continue
    }

    // Ordered list item
    if (/^\d+\.\s/.test(stripped)) {
      processed.push(`<li class="md-li md-li-ol">${renderInline(stripped.replace(/^\d+\.\s+/, ''))}</li>`)
      continue
    }

    // Table row — detect by having | and likely containing | at least twice
    if (stripped.startsWith('|') && stripped.endsWith('|') && (stripped.match(/\|/g) || []).length >= 3) {
      const cells = stripped.split('|').slice(1, -1).map(c => c.trim())
      // Separator row (contains ---, :, etc.)
      if (cells.every(c => /^[-:]+$/.test(c) || /^:[-:]+$/.test(c) || /^[-:]+:$/.test(c))) {
        continue // skip separator
      }
      processed.push(`<tr class="md-tr">${cells.map(c => `<td class="md-td">${renderInline(c)}</td>`).join('')}</tr>`)
      continue
    }

    // Empty line → paragraph break
    if (!stripped) {
      processed.push('')
      continue
    }

    // Default: paragraph
    processed.push(`<p class="md-p">${renderInline(stripped)}</p>`)
  }

  // 4. Group consecutive list items into <ul>/<ol>
  const grouped: string[] = []
  let i = 0
  while (i < processed.length) {
    const line = processed[i]
    if (line.startsWith('<li class="md-li')) {
      const isOl = line.includes('md-li-ol')
      const tag = isOl ? 'ol' : 'ul'
      const items: string[] = []
      while (i < processed.length && processed[i].startsWith('<li class="md-li')) {
        items.push(processed[i].replace(' class="md-li"', '').replace(' class="md-li md-li-ol"', ''))
        i++
      }
      // Skip leading empty lines between items
      grouped.push(`<${tag} class="md-ul">${items.join('')}</${tag}>`)
      continue
    }
    // Wrap consecutive table rows in <table>
    if (line.startsWith('<tr')) {
      const rows: string[] = []
      while (i < processed.length && processed[i].startsWith('<tr')) {
        rows.push(processed[i])
        i++
      }
      if (rows.length > 0) {
        grouped.push(`<table class="md-table"><tbody>${rows.join('')}</tbody></table>`)
        continue
      }
    }
    grouped.push(line)
    i++
  }

  // 5. Join, remove trailing empty lines from paragraphs
  return grouped
    .join('\n')
    .replace(/<p class="md-p"><\/p>/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function MarkdownPreview({ content }: { content: string }) {
  const html = useMemo(() => renderMarkdown(content), [content])
  if (!content.trim()) {
    return <p className="text-slate-500 italic text-sm">Sin contenido todavía…</p>
  }
  return <div className="md-prose" dangerouslySetInnerHTML={{ __html: html }} />
}

export default function NodeEditor() {
  const { ws, slug } = useParams<{ ws: string; slug: string }>()
  const navigate = useNavigate()
  const isNew = slug === undefined
  const [node, setNode] = useState<Node | null>(null)
  const [form, setForm] = useState<NodePayload>({
    title: '', kind: 'doc', content: '', summary: '', tags: [], parent_ref: null,
  })
  const [original, setOriginal] = useState<string>('')
  const [preview, setPreview] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [justSaved, setJustSaved] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [linkRef, setLinkRef] = useState('')
  const [linkRel, setLinkRel] = useState('related_to')
  const [addingLink, setAddingLink] = useState(false)

  const { setNodeContext } = useChatContext()

  useEffect(() => {
    if (!ws || isNew) {
      setNodeContext(null)
      return
    }
    api.getNode(ws, slug!).then(n => {
      setNode(n)
      setNodeContext({ title: n.title, slug: n.slug, kind: n.kind })
      const loaded: NodePayload = {
        title: n.title,
        kind: n.kind,
        content: n.content,
        summary: n.summary,
        tags: n.tags.filter(t => t !== n.slug),
        parent_ref: null,
        status: n.status,
      }
      setForm(loaded)
      setOriginal(JSON.stringify(loaded))
    }).catch(e => setError(e.message))
  }, [ws, slug, isNew])

  const dirty = isNew ? !!(form.title || form.content || form.summary) : JSON.stringify(form) !== original

  const save = async () => {
    if (!ws || !form.title.trim()) return
    setSaving(true)
    setError('')
    try {
      if (isNew) {
        const created = await api.createNode(ws, form)
        navigate(`/ws/${ws}/nodes/${created.slug}`, { replace: true })
      } else {
        const updated = await api.updateNode(ws, slug!, form)
        setNode(updated)
        setOriginal(JSON.stringify(form))
        setJustSaved(true)
        setTimeout(() => setJustSaved(false), 1800)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  // Cmd/Ctrl+S
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (!saving && form.title.trim()) save()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const deleteNode = async () => {
    if (!ws || !slug) return
    if (!confirm(`¿Eliminar el nodo "${form.title}"? Esta acción no se puede deshacer.`)) return
    try {
      await api.deleteNode(ws, slug)
      navigate(`/ws/${ws}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const addTag = () => {
    const t = tagInput.trim().toLowerCase().replace(/\s+/g, '-')
    if (!t || form.tags?.includes(t)) return
    setForm(f => ({ ...f, tags: [...(f.tags ?? []), t] }))
    setTagInput('')
  }

  const removeTag = (tag: string) => {
    setForm(f => ({ ...f, tags: (f.tags ?? []).filter(t => t !== tag) }))
  }

  const handleTagKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() }
  }

  const submitLink = async () => {
    if (!ws || !slug || !linkRef.trim()) return
    try {
      await api.addLink(ws, slug, { target_ref: linkRef.trim(), rel: linkRel })
      const updated = await api.getNode(ws, slug)
      setNode(updated)
      setLinkRef(''); setAddingLink(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  if (!isNew && !node && !error) {
    return <div className="app-bg flex items-center justify-center h-screen"><div className="text-slate-400">Cargando nodo…</div></div>
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3 sticky top-0 z-20 backdrop-blur-xl" style={{ borderBottom: '1px solid var(--border)', background: 'rgba(5,5,5,0.8)' }}>
        <button onClick={() => navigate(`/ws/${ws}`)} className="btn-ghost flex items-center justify-center h-9 w-9 rounded-lg text-slate-300">
          <ChevronLeft size={18} />
        </button>
        <div className="flex items-center gap-2 text-sm min-w-0">
          <button onClick={() => navigate('/')} className="text-slate-500 hover:text-slate-300 transition-colors">LAIA</button>
          <span className="text-slate-700">/</span>
          <button onClick={() => navigate(`/ws/${ws}`)} className="text-slate-400 hover:text-slate-200 transition-colors">{ws}</button>
          <span className="text-slate-700">/</span>
          <span className="text-white font-medium truncate">
            {isNew ? 'Nuevo nodo' : form.title || 'Sin título'}
          </span>
        </div>

        {/* Status indicator */}
        <div className="ml-3 flex items-center gap-2 text-xs">
          {error ? (
            <span className="text-red-400 flex items-center gap-1"><X size={12} />{error}</span>
          ) : justSaved ? (
            <span className="text-emerald-400 flex items-center gap-1 fade-up"><CheckCircle2 size={12} /> Guardado</span>
          ) : dirty ? (
            <span className="text-amber-300/90 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400"></span> Cambios sin guardar
            </span>
          ) : !isNew && node ? (
            <span className="text-slate-500">Actualizado {relativeTime(node.updated_at)}</span>
          ) : null}
        </div>

        <div className="ml-auto flex items-center gap-2">
          {!isNew && (
            <button onClick={deleteNode} className="btn-danger-ghost flex items-center gap-1.5 px-3 h-9 rounded-lg text-sm">
              <Trash2 size={14} /> <span className="hidden sm:inline">Eliminar</span>
            </button>
          )}
          <button
            onClick={save}
            disabled={saving || !form.title.trim()}
            className="btn-primary flex items-center gap-2 px-4 h-9 rounded-lg text-sm text-white font-medium"
          >
            <Save size={14} /> {saving ? 'Guardando…' : 'Guardar'}
            <kbd className="hidden md:inline ml-1 px-1 py-0.5 text-[0.6rem] bg-white/20 rounded font-mono">⌘S</kbd>
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: metadata */}
        <aside className="w-80 shrink-0 overflow-y-auto" style={{ borderRight: '1px solid var(--border)', background: 'rgba(255,255,255,0.015)' }}>
          <div className="p-5 flex flex-col gap-6">
            <Section label="Título">
              <input
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="field w-full px-3 py-2 rounded-lg text-sm font-medium"
                placeholder="Título del nodo"
                autoFocus={isNew}
              />
            </Section>

            <Section label="Tipo">
              <div className="relative">
                <select
                  value={form.kind}
                  onChange={e => setForm(f => ({ ...f, kind: e.target.value }))}
                  className="field w-full px-3 py-2 rounded-lg text-sm appearance-none pr-8"
                >
                  {ALL_KINDS.map(k => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
                  <span className={`chip ${kindClass(form.kind)}`}>{form.kind}</span>
                </div>
              </div>
            </Section>

            <Section label="Resumen">
              <textarea
                value={form.summary}
                onChange={e => setForm(f => ({ ...f, summary: e.target.value }))}
                rows={3}
                className="field w-full px-3 py-2 rounded-lg text-sm resize-none leading-relaxed"
                placeholder="Descripción breve…"
              />
            </Section>

            <Section label="Nodo padre" icon={<CornerDownRight size={11} />}>
              <input
                value={form.parent_ref ?? ''}
                onChange={e => setForm(f => ({ ...f, parent_ref: e.target.value || null }))}
                className="field w-full px-3 py-2 rounded-lg text-sm mono"
                placeholder="slug del padre…"
              />
            </Section>

            <Section label="Tags / aliases" icon={<Tag size={11} />}>
              {(form.tags ?? []).length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {(form.tags ?? []).map(tag => (
                    <span key={tag} className="chip bg-slate-700/50 text-slate-200 ring-slate-600/50 ring-1 ring-inset group">
                      <Hash size={9} className="opacity-50" />
                      {tag}
                      <button onClick={() => removeTag(tag)} className="text-slate-400 hover:text-red-300 ml-0.5">
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex gap-1.5">
                <input
                  value={tagInput}
                  onChange={e => setTagInput(e.target.value)}
                  onKeyDown={handleTagKey}
                  className="field flex-1 px-2.5 py-1.5 rounded-lg text-xs"
                  placeholder="nuevo-tag"
                />
                <button onClick={addTag} className="btn-ghost px-2.5 py-1.5 rounded-lg text-slate-300">
                  <Plus size={13} />
                </button>
              </div>
            </Section>

            {/* Links */}
            {!isNew && node && (
              <Section
                label="Enlaces"
                icon={<Link2 size={11} />}
                action={
                  <button onClick={() => setAddingLink(v => !v)} className="text-slate-500 hover:text-amber-300 transition-colors">
                    {addingLink ? <X size={13} /> : <Plus size={13} />}
                  </button>
                }
              >
                {addingLink && (
                  <div className="flex flex-col gap-2 mb-3 p-3 rounded-lg fade-up" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)' }}>
                    <input
                      value={linkRef}
                      onChange={e => setLinkRef(e.target.value)}
                      className="field px-2.5 py-1.5 rounded text-xs mono"
                      placeholder="slug destino"
                    />
                    <select
                      value={linkRel}
                      onChange={e => setLinkRel(e.target.value)}
                      className="field px-2.5 py-1.5 rounded text-xs"
                    >
                      {EDGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <button onClick={submitLink} className="btn-primary px-3 py-1.5 rounded text-white text-xs font-medium">
                      Añadir enlace
                    </button>
                  </div>
                )}
                {node.links.length === 0 ? (
                  <p className="text-slate-500 text-xs italic">Sin enlaces</p>
                ) : (
                  <div className="space-y-1">
                    {node.links.map(link => (
                      <button
                        key={link.slug + link.rel}
                        onClick={() => navigate(`/ws/${ws}/nodes/${link.slug}`)}
                        className="w-full flex items-center gap-2 text-left px-2 py-1.5 rounded-md group transition-colors"
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,196,90,0.06)')}
                        onMouseLeave={e => (e.currentTarget.style.background = '')}
                      >
                        <span className="text-[0.6rem] uppercase tracking-wider font-medium w-16 shrink-0" style={{ color: 'var(--text-muted)' }}>{link.rel}</span>
                        <span className={`chip ${kindClass(link.kind || 'doc')} py-0 text-[0.6rem]`}>{link.kind || 'doc'}</span>
                        <span className="text-xs truncate transition-colors group-hover:text-amber-200" style={{ color: '#c0c0c0' }}>
                          {link.title || link.slug}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </Section>
            )}

            {!isNew && node && (
              <div className="pt-2 text-[0.68rem] text-slate-600 leading-relaxed mono">
                <div>id: {node.id}</div>
                <div>slug: {node.slug}</div>
              </div>
            )}
          </div>
        </aside>

        {/* Right: content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-2.5" style={{ borderBottom: '1px solid var(--border)', background: 'rgba(5,5,5,0.4)' }}>
            <span className="text-xs flex-1" style={{ color: 'var(--text-muted)' }}>Contenido · Markdown</span>
            <div className="flex items-center gap-0.5 p-0.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)' }}>
              <button
                onClick={() => setPreview(false)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-all ${!preview ? 'text-white shadow' : 'hover:text-white'}`}
                style={!preview ? { background: 'rgba(255,196,90,0.15)', color: 'var(--brand)' } : { color: 'var(--text-muted)' }}
              >
                <Code2 size={12} /> Editar
              </button>
              <button
                onClick={() => setPreview(true)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-all ${preview ? 'text-white shadow' : 'hover:text-white'}`}
                style={preview ? { background: 'rgba(255,196,90,0.15)', color: 'var(--brand)' } : { color: 'var(--text-muted)' }}
              >
                <Eye size={12} /> Preview
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-4xl mx-auto px-8 py-6">
              {preview ? (
                <MarkdownPreview content={form.content ?? ''} />
              ) : (
                <textarea
                  value={form.content ?? ''}
                  onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                  className="w-full min-h-[calc(100vh-200px)] bg-transparent text-slate-200 mono text-[13.5px] leading-relaxed resize-none focus:outline-none"
                  placeholder="# Título del nodo&#10;&#10;Contenido en Markdown…"
                  spellCheck={false}
                />
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

function Section({
  label, icon, children, action,
}: {
  label: string
  icon?: React.ReactNode
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-[0.65rem] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          {icon && <span className="text-slate-600">{icon}</span>}
          {label}
        </label>
        {action}
      </div>
      {children}
    </div>
  )
}
