/* ────────────────────────────────────────────────────────────────────────────
   WORKSPACE
   ----------------------------------------------------------------------------
   Full agent control center. Mounted below the LAIA hero — the user scrolls
   into it. Everything inside this tree consumes <AgentProvider> via
   `useAgent()`. Layout and palette are driven by <SettingsDrawer>.

   Hierarchy:
     Workspace
     ├─ TopBar               (model · modes · context meter)
     ├─ Grid (CSS columns)
     │  ├─ SessionsRail      (left)
     │  ├─ ChatStream        (center)
     │  └─ SidePanels        (right; tabs: trace · edits · agents · approvals)
     ├─ ApprovalDialog       (overlay when approval.request fires)
     ├─ CommandPalette       (⌘K overlay)
     ├─ DiffModal            (overlay when an edit chip is clicked)
     └─ SettingsDrawer       (right drawer)
──────────────────────────────────────────────────────────────────────────── */
import { useEffect, useRef, useState } from 'react'
import { useAgent } from '../../lib/agentRuntime'
import type { ToolCall } from '../../lib/agentRuntime'
import type { FileEdit } from '../../lib/api'
import { TopBar } from './TopBar'
import { SessionsRail } from './SessionsRail'
import { ChatStream } from './ChatStream'
import { SidePanels } from './SidePanels'
import { CommandPalette } from './CommandPalette'
import { DiffModal } from './DiffModal'
import { ApprovalDialog } from './ApprovalDialog'
import { PromptDialog } from './PromptDialog'
import { ToolDetailModal } from './ToolDetailModal'
import {
  applySettings,
  DEFAULT_SETTINGS,
  getLayoutCols,
  loadSettings,
  saveSettings,
  SettingsDrawer,
} from './SettingsDrawer'
import type { WorkspaceSettings } from './SettingsDrawer'

export function Workspace() {
  const { pendingPrompt } = useAgent()
  const rootRef = useRef<HTMLDivElement>(null)
  const [settings, setSettings] = useState<WorkspaceSettings>(loadSettings)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [diffEdit, setDiffEdit] = useState<FileEdit | null>(null)
  const [toolDetail, setToolDetail] = useState<ToolCall | null>(null)

  // Apply CSS vars whenever settings change
  useEffect(() => {
    saveSettings(settings)
    if (rootRef.current) applySettings(settings, rootRef.current)
  }, [settings])

  // ⌘K opens command palette globally inside the workspace
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(o => !o)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const cols = getLayoutCols(settings.layout, settings.showSessions, settings.showSidePanels)

  return (
    <div
      ref={rootRef}
      className="workspace-theme relative w-full"
      style={{ minHeight: '100vh' }}
    >
      <div className="ws-backdrop" />

      <div className="relative z-10 flex flex-col" style={{ height: '100vh' }}>
        <TopBar onOpenSettings={() => setSettingsOpen(true)} />

        <div
          style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: cols,
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {settings.showSessions && settings.layout !== 'centered' && settings.layout !== 'two-col-right' && (
            <SessionsRail />
          )}

          <ChatStream
            onOpenDiff={setDiffEdit}
            onOpenCommands={() => setPaletteOpen(true)}
            onOpenTool={setToolDetail}
          />

          {settings.showSidePanels && settings.layout !== 'centered' && settings.layout !== 'two-col-left' && (
            <SidePanels
              onOpenDiff={setDiffEdit}
              onOpenApproval={() => { /* approval is auto-shown via pendingPrompt */ }}
            />
          )}
        </div>
      </div>

      {pendingPrompt?.kind === 'approval' && <ApprovalDialog />}
      {pendingPrompt && pendingPrompt.kind !== 'approval' && <PromptDialog />}
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <DiffModal edit={diffEdit} onClose={() => setDiffEdit(null)} />
      <ToolDetailModal tc={toolDetail} onClose={() => setToolDetail(null)} />
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onChange={setSettings}
      />
    </div>
  )
}

export { DEFAULT_SETTINGS }
