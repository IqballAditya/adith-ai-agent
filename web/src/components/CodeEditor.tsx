import React, { useRef } from 'react'
import Editor, { BeforeMount, OnMount } from '@monaco-editor/react'
import { X, FileCode, Zap } from 'lucide-react'
import { EditorTab } from '../types'

interface CodeEditorProps {
  tabs: EditorTab[]
  activePath?: string
  onSelectTab: (path: string) => void
  onCloseTab: (path: string) => void
  onChangeContent: (path: string, newContent: string) => void
  onSave?: (path: string) => void
}

export const getLanguageFromPath = (path: string): string => {
  const ext = path.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'go':
      return 'go'
    case 'py':
      return 'python'
    case 'ts':
      return 'typescript'
    case 'tsx':
      return 'typescript'
    case 'js':
    case 'jsx':
    case 'mjs':
      return 'javascript'
    case 'json':
      return 'json'
    case 'html':
      return 'html'
    case 'css':
      return 'css'
    case 'sql':
      return 'sql'
    case 'md':
      return 'markdown'
    case 'sh':
    case 'bash':
      return 'shell'
    default:
      return 'plaintext'
  }
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  tabs,
  activePath,
  onSelectTab,
  onCloseTab,
  onChangeContent,
  onSave,
}) => {
  const editorRef = useRef<any>(null)
  const activeTab = tabs.find((t) => t.path === activePath)

  const handleEditorWillMount: BeforeMount = (monaco) => {
    monaco.editor.defineTheme('studio-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '64748b', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'a78bfa', fontStyle: 'bold' },
        { token: 'string', foreground: '6ee7b7' },
        { token: 'number', foreground: 'fcd34d' },
        { token: 'type', foreground: '60a5fa' },
        { token: 'function', foreground: '38bdf8' },
        { token: 'variable', foreground: 'e2e8f0' },
      ],
      colors: {
        'editor.background': '#0A0C10',
        'editor.foreground': '#cbd5e1',
        'editorLineNumber.foreground': '#334155',
        'editorLineNumber.activeForeground': '#818cf8',
        'editor.lineHighlightBackground': '#181C2460',
        'editorCursor.foreground': '#6366f1',
        'editorWhitespace.foreground': '#1e293b',
        'editor.selectionBackground': '#2E3547',
        'editor.inactiveSelectionBackground': '#1e2538',
      },
    })
  }

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      if (activeTab && onSave) {
        onSave(activeTab.path)
      }
    })
  }

  return (
    <div className="flex-1 flex flex-col bg-studio-bg overflow-hidden">
      {/* Tabs Bar */}
      <div className="h-9 border-b border-studio-border bg-studio-card flex items-center px-2 gap-1 text-xs overflow-x-auto select-none">
        {tabs.length === 0 ? (
          <span className="text-[11px] text-slate-500 font-mono px-2">
            No files open
          </span>
        ) : (
          tabs.map((tab) => {
            const isActive = tab.path === activePath
            return (
              <div
                key={tab.path}
                onClick={() => onSelectTab(tab.path)}
                className={`group flex items-center gap-2 px-3 py-1.5 rounded-t cursor-pointer transition text-xs ${
                  isActive
                    ? 'bg-studio-bg text-indigo-400 border-t-2 border-indigo-500 border-x border-studio-border font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-studio-surface'
                }`}
              >
                <FileCode className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                <span className="font-mono text-[11px] truncate max-w-[150px]">
                  {tab.name}
                </span>
                {tab.isDirty && (
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onCloseTab(tab.path)
                  }}
                  className="opacity-40 group-hover:opacity-100 hover:text-white p-0.5 rounded transition"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* Editor Content Area */}
      <div className="flex-1 relative overflow-hidden">
        {activeTab ? (
          <Editor
            height="100%"
            path={activeTab.path}
            defaultLanguage={activeTab.language}
            language={activeTab.language}
            value={activeTab.content}
            theme="studio-dark"
            beforeMount={handleEditorWillMount}
            onMount={handleEditorDidMount}
            onChange={(val) => {
              onChangeContent(activeTab.path, val ?? '')
            }}
            options={{
              fontSize: 13,
              fontFamily: '"Fira Code", monospace',
              fontLigatures: true,
              lineNumbers: 'on',
              minimap: { enabled: true, maxColumn: 80 },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 2,
              wordWrap: 'on',
              smoothScrolling: true,
              renderLineHighlight: 'all',
              cursorBlinking: 'smooth',
            }}
          />
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 p-6 space-y-4">
            <div className="w-12 h-12 rounded-xl bg-studio-surface border border-studio-border flex items-center justify-center text-indigo-400">
              <Zap className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-sm font-semibold text-slate-300">
                ADITH AI STUDIO Editor
              </h3>
              <p className="text-xs text-slate-500 max-w-sm">
                Select a file from the explorer on the left or prompt ADITH AI Copilot to generate and modify code.
              </p>
            </div>
            <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500 bg-studio-surface border border-studio-border px-3 py-1.5 rounded">
              <span>Shortcuts:</span>
              <kbd className="bg-black/40 px-1.5 py-0.5 rounded text-indigo-300">Ctrl+S</kbd>
              <span>Save</span>
              <span className="text-slate-600">|</span>
              <kbd className="bg-black/40 px-1.5 py-0.5 rounded text-indigo-300">Ctrl+Enter</kbd>
              <span>Run Agent</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
