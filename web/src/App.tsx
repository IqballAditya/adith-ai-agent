import React, { useState, useEffect, useCallback } from 'react'
import {
  MessageSquare,
  FolderTree,
  Code2,
  Terminal as TerminalIcon,
  Settings,
  Play,
  Rocket,
  ChevronDown,
} from 'lucide-react'
import { FileTree } from './components/FileTree'
import { CodeEditor, getLanguageFromPath } from './components/CodeEditor'
import { ChatPanel } from './components/ChatPanel'
import { TerminalView } from './components/TerminalView'
import { EditorTab, ChatMessage } from './types'

export const App: React.FC = () => {
  // Navigation sidebar toggles
  const [showFileTree, setShowFileTree] = useState<boolean>(true)
  const [showChatPanel, setShowChatPanel] = useState<boolean>(true)
  const [showTerminal, setShowTerminal] = useState<boolean>(true)

  // Editor tabs state
  const [tabs, setTabs] = useState<EditorTab[]>([])
  const [activePath, setActivePath] = useState<string | undefined>(undefined)

  // Chat messages
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('Google Gemini Flash')
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState<boolean>(false)

  // Gateway health state
  const [gatewayStatus, setGatewayStatus] = useState<'online' | 'offline' | 'checking'>('checking')

  const models = [
    'Google Gemini Flash',
    'Claude 3.5 Sonnet + R1',
    'DeepSeek R1',
    'GPT-4o',
    'Claude 3.5 Haiku',
  ]

  // Check backend health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch('/health')
        if (res.ok) {
          setGatewayStatus('online')
        } else {
          setGatewayStatus('offline')
        }
      } catch {
        setGatewayStatus('offline')
      }
    }
    checkHealth()
    const timer = setInterval(checkHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  // Open a file from file tree
  const handleSelectFile = useCallback(async (path: string) => {
    // If already open, just activate tab
    const existing = tabs.find((t) => t.path === path)
    if (existing) {
      setActivePath(path)
      return
    }

    try {
      const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`)
      if (!res.ok) {
        throw new Error(`Failed to read file ${path}`)
      }
      const content = await res.text()
      const fileName = path.split('/').pop() || path

      const newTab: EditorTab = {
        path,
        name: fileName,
        content,
        language: getLanguageFromPath(path),
        isDirty: false,
      }

      setTabs((prev) => [...prev, newTab])
      setActivePath(path)
    } catch (err: any) {
      console.error('Error opening file:', err)
    }
  }, [tabs])

  const handleCloseTab = useCallback((path: string) => {
    setTabs((prev) => {
      const next = prev.filter((t) => t.path !== path)
      if (activePath === path) {
        const closedIndex = prev.findIndex((t) => t.path === path)
        const nextActive = next[closedIndex] || next[closedIndex - 1] || next[0]
        setActivePath(nextActive ? nextActive.path : undefined)
      }
      return next
    })
  }, [activePath])

  const handleChangeContent = useCallback((path: string, newContent: string) => {
    setTabs((prev) =>
      prev.map((t) =>
        t.path === path ? { ...t, content: newContent, isDirty: true } : t
      )
    )
  }, [])

  // Accept diff from ChatPanel
  const handleAcceptDiff = useCallback(
    async (path: string, modified: string, original?: string): Promise<boolean> => {
      try {
        // Find current original content if open
        const existingTab = tabs.find((t) => t.path === path)
        const originalContent = (original !== undefined && original !== "") ? original : (existingTab ? existingTab.content : "");

        const res = await fetch('/api/diff/accept', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path,
            original: originalContent,
            modified,
          }),
        })

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          alert(`Failed to apply diff: ${errData.error || res.statusText}`)
          return false
        }

        // Immediately update editor buffer if open
        setTabs((prev) => {
          const exists = prev.some((t) => t.path === path)
          if (exists) {
            return prev.map((t) =>
              t.path === path
                ? { ...t, content: modified, isDirty: false }
                : t
            )
          } else {
            // If file was not open, open it
            const fileName = path.split('/').pop() || path
            return [
              ...prev,
              {
                path,
                name: fileName,
                content: modified,
                language: getLanguageFromPath(path),
                isDirty: false,
              },
            ]
          }
        })

        setActivePath(path)
        return true
      } catch (err: any) {
        alert(`Error applying diff: ${err.message}`)
        return false
      }
    },
    [tabs]
  )

  // Save active file content back to disk via Gateway
  const handleSaveFile = useCallback(
    async (path: string) => {
      const tab = tabs.find((t) => t.path === path)
      if (!tab) return

      try {
        let original = ''
        try {
          const checkRes = await fetch(`/api/file?path=${encodeURIComponent(path)}`)
          if (checkRes.ok) {
            original = await checkRes.text()
          }
        } catch {
          // If file does not exist on disk, original remains empty
        }

        const res = await fetch('/api/diff/accept', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            path,
            original,
            modified: tab.content,
          }),
        })

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          console.error(`Save failed: ${errData.error || res.statusText}`)
          return
        }

        // Clear dirty state on success
        setTabs((prev) =>
          prev.map((t) => (t.path === path ? { ...t, isDirty: false } : t))
        )
      } catch (err: any) {
        console.error('Error saving file:', err)
      }
    },
    [tabs]
  )

  // Keyboard shortcut Ctrl+Enter to trigger agent or open chat
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        setShowChatPanel(true)
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [])

  return (
    <div className="h-screen w-screen flex flex-col bg-studio-bg text-slate-200 overflow-hidden font-sans select-none">
      {/* Top Global Header */}
      <header className="h-12 border-b border-studio-border bg-studio-card flex items-center justify-between px-4 z-20 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-400 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20 text-xs">
              ⚡
            </div>
            <span className="font-bold tracking-tight text-white text-sm">
              ADITH <span className="text-indigo-400 font-semibold">AI STUDIO</span>
            </span>
            <span className="text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.5 rounded font-mono">
              v1.0.0
            </span>
          </div>

          <div className="h-4 w-px bg-studio-border mx-1" />

          <div className="flex items-center gap-2 text-xs text-slate-400 bg-studio-surface px-2.5 py-1 rounded border border-studio-border hover:border-slate-600 cursor-pointer transition">
            <Code2 className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-slate-200 font-medium">adith-ai-studio</span>
            <span className="text-slate-500 text-[11px] font-mono">/ git:main</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Gateway Status Badge */}
          <div className="flex items-center gap-1.5 bg-studio-surface border border-studio-border text-xs px-2 py-1 rounded-md text-slate-400">
            <span
              className={`w-2 h-2 rounded-full ${
                gatewayStatus === 'online'
                  ? 'bg-emerald-400'
                  : gatewayStatus === 'checking'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-rose-500'
              }`}
            />
            <span className="text-[11px]">
              {gatewayStatus === 'online' ? 'Gateway :8090' : 'Offline'}
            </span>
          </div>

          {/* Model Picker */}
          <div className="relative">
            <button
              onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
              className="flex items-center gap-1.5 bg-studio-surface border border-studio-border hover:border-slate-600 text-xs px-2.5 py-1 rounded-md text-slate-300 transition"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-slate-400">Model:</span>
              <span className="font-semibold text-white">{selectedModel}</span>
              <ChevronDown className="w-3 h-3 text-slate-400 ml-1" />
            </button>

            {isModelDropdownOpen && (
              <div className="absolute right-0 mt-1 w-52 bg-studio-card border border-studio-border rounded-lg shadow-xl z-30 py-1 text-xs">
                {models.map((m) => (
                  <button
                    key={m}
                    onClick={() => {
                      setSelectedModel(m)
                      setIsModelDropdownOpen(false)
                    }}
                    className={`w-full text-left px-3 py-1.5 flex items-center justify-between hover:bg-studio-surface transition ${
                      selectedModel === m ? 'text-indigo-400 font-semibold' : 'text-slate-300'
                    }`}
                  >
                    <span>{m}</span>
                    {selectedModel === m && (
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Run / Agent Trigger */}
          <button
            onClick={() => setShowChatPanel(true)}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium px-3 py-1.5 rounded-md flex items-center gap-1.5 shadow-md shadow-indigo-600/25 transition cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Run Agent (Ctrl+Enter)</span>
          </button>

          <button className="bg-studio-surface hover:bg-studio-active text-slate-300 text-xs px-2.5 py-1.5 rounded-md border border-studio-border transition flex items-center gap-1">
            <Rocket className="w-3 h-3 text-emerald-400" />
            <span>Deploy</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Icon Strip */}
        <aside className="w-12 bg-studio-card border-r border-studio-border flex flex-col items-center py-3 gap-3 text-slate-400 flex-shrink-0 z-10">
          <button
            onClick={() => setShowChatPanel(!showChatPanel)}
            title="Toggle AI Copilot"
            className={`w-8 h-8 rounded-lg flex items-center justify-center transition ${
              showChatPanel
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'hover:bg-studio-surface hover:text-slate-200'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
          </button>

          <button
            onClick={() => setShowFileTree(!showFileTree)}
            title="Toggle File Explorer"
            className={`w-8 h-8 rounded-lg flex items-center justify-center transition ${
              showFileTree
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'hover:bg-studio-surface hover:text-slate-200'
            }`}
          >
            <FolderTree className="w-4 h-4" />
          </button>

          <button
            onClick={() => setShowTerminal(!showTerminal)}
            title="Toggle Terminal"
            className={`w-8 h-8 rounded-lg flex items-center justify-center transition ${
              showTerminal
                ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                : 'hover:bg-studio-surface hover:text-slate-200'
            }`}
          >
            <TerminalIcon className="w-4 h-4" />
          </button>

          <div className="mt-auto">
            <button
              title="Settings"
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-studio-surface hover:text-slate-200 transition"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </aside>

        {/* File Explorer Sidebar */}
        {showFileTree && (
          <div className="w-60 flex-shrink-0">
            <FileTree
              activePath={activePath}
              onSelectFile={handleSelectFile}
            />
          </div>
        )}

        {/* AI Agent Chat Panel */}
        {showChatPanel && (
          <ChatPanel
            messages={messages}
            setMessages={setMessages}
            onAcceptDiff={handleAcceptDiff}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
            activeFilePath={activePath}
          />
        )}

        {/* Right Side: Code Editor + Terminal */}
        <main className="flex-1 flex flex-col bg-studio-bg overflow-hidden min-w-0">
          <CodeEditor
            tabs={tabs}
            activePath={activePath}
            onSelectTab={setActivePath}
            onCloseTab={handleCloseTab}
            onChangeContent={handleChangeContent}
            onSave={handleSaveFile}
          />

          {showTerminal && (
            <TerminalView onClose={() => setShowTerminal(false)} />
          )}
        </main>
      </div>
    </div>
  )
}

export default App
