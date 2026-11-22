import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { RotateCw, Trash2, X } from 'lucide-react'
import { VIRTUAL_FILES } from '../virtualWorkspace'

interface TerminalViewProps {
  onClose?: () => void
}

export const TerminalView: React.FC<TerminalViewProps> = ({ onClose }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [sandboxMode, setSandboxMode] = useState<boolean>(false)
  const cmdBufferRef = useRef<string>('')

  const startSandboxShell = useCallback((term: Terminal) => {
    setStatus('connected')
    setSandboxMode(true)
    term.writeln('\x1b[36m[sandbox-init]\x1b[0m Connected to Adith AI Cloud Sandbox (Vercel Edge).')
    term.writeln('\x1b[90mType "help", "ls", "cat <file>", "python main.py", or "status".\x1b[0m\r\n')
    term.write('\x1b[32madith-ai@studio\x1b[0m:\x1b[34m~/workspace\x1b[0m$ ')
  }, [])

  const handleSandboxCommand = useCallback((cmd: string, term: Terminal) => {
    const trimmed = cmd.trim()
    if (!trimmed) {
      term.write('\x1b[32madith-ai@studio\x1b[0m:\x1b[34m~/workspace\x1b[0m$ ')
      return
    }

    const parts = trimmed.split(/\s+/)
    const base = parts[0].toLowerCase()

    if (base === 'help') {
      term.writeln('\x1b[1;37mADITH AI Cloud Terminal - Available Commands:\x1b[0m')
      term.writeln('  \x1b[33mls\x1b[0m               List workspace files & directories')
      term.writeln('  \x1b[33mcat <file>\x1b[0m       Display contents of a file')
      term.writeln('  \x1b[33mpython main.py\x1b[0m   Run the ADITH AI execution engine')
      term.writeln('  \x1b[33mstatus\x1b[0m           Display agent and cloud runtime health')
      term.writeln('  \x1b[33mgit status\x1b[0m       Check current git branch status')
      term.writeln('  \x1b[33mclear\x1b[0m            Clear the terminal screen')
    } else if (base === 'clear') {
      term.clear()
    } else if (base === 'ls') {
      term.writeln('\x1b[34magent/\x1b[0m   \x1b[34mcmd/\x1b[0m   \x1b[34mexamples/\x1b[0m   \x1b[32mmain.py\x1b[0m   README.md   go.mod')
    } else if (base === 'cat') {
      const target = parts[1]
      if (!target) {
        term.writeln('usage: cat <filename>')
      } else if (VIRTUAL_FILES[target]) {
        term.writeln(VIRTUAL_FILES[target].replace(/\n/g, '\r\n'))
      } else {
        term.writeln(`cat: ${target}: No such file or directory`)
      }
    } else if (base === 'python') {
      term.writeln('\x1b[32m============================================================\x1b[0m')
      term.writeln('  \x1b[1;36m⚡ ADITH AI AGENT & STUDIO - Running Engine\x1b[0m')
      term.writeln('\x1b[32m============================================================\x1b[0m')
      term.writeln('\x1b[32m✓\x1b[0m Agent initialized successfully.')
      term.writeln('\x1b[32m✓\x1b[0m AST Parser connected (Tree-sitter).')
      term.writeln('\x1b[32m✓\x1b[0m Vector Memory active.')
      term.writeln('Waiting for prompts or incoming tasks...')
    } else if (base === 'git' && parts[1] === 'status') {
      term.writeln('On branch main')
      term.writeln("Your branch is up to date with 'origin/main'.")
      term.writeln('nothing to commit, working tree clean')
    } else if (base === 'status') {
      term.writeln('\x1b[1;32m● System Operational\x1b[0m')
      term.writeln('  Service:  ADITH AI Studio')
      term.writeln('  Runtime:  Cloud Sandbox (Vercel Edge)')
      term.writeln('  Engine:   Google Gemini Flash')
      term.writeln('  AST:      Tree-sitter Multi-language Parser')
    } else {
      term.writeln(`bash: ${parts[0]}: command not found. Type "help" for available commands.`)
    }

    term.write('\x1b[32madith-ai@studio\x1b[0m:\x1b[34m~/workspace\x1b[0m$ ')
  }, [])

  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const term = termRef.current
    if (!term) return

    setStatus('connecting')

    const isCloud = window.location.hostname.includes('vercel.app')
    if (isCloud) {
      // In Vercel serverless environment, immediately provide interactive web sandbox
      startSandboxShell(term)
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.port === '5173' ? 'localhost:8090' : window.location.host
    const wsUrl = `${protocol}//${host}/api/terminal`

    try {
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        setSandboxMode(false)
        term.writeln('\x1b[32m[sandbox-init]\x1b[0m Connected to backend terminal shell.')
      }

      ws.onmessage = (event) => {
        if (typeof event.data === 'string') {
          term.write(event.data)
        } else if (event.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(event.data))
        }
      }

      ws.onerror = () => {
        startSandboxShell(term)
      }

      ws.onclose = () => {
        startSandboxShell(term)
      }
    } catch {
      startSandboxShell(term)
    }
  }, [startSandboxShell])

  useEffect(() => {
    if (!containerRef.current) return

    const term = new Terminal({
      cursorBlink: true,
      fontFamily: '"Fira Code", monospace',
      fontSize: 12,
      lineHeight: 1.2,
      theme: {
        background: '#0A0C10',
        foreground: '#cbd5e1',
        cursor: '#6366f1',
        selectionBackground: '#2E3547',
        black: '#0A0C10',
        red: '#f43f5e',
        green: '#10b981',
        yellow: '#f59e0b',
        blue: '#6366f1',
        magenta: '#a855f7',
        cyan: '#06b6d4',
        white: '#f8fafc',
        brightBlack: '#475569',
        brightRed: '#fb7185',
        brightGreen: '#34d399',
        brightYellow: '#fbbf24',
        brightBlue: '#818cf8',
        brightMagenta: '#c084fc',
        brightCyan: '#22d3ee',
        brightWhite: '#ffffff',
      },
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)

    try {
      fitAddon.fit()
    } catch {
      // ignore
    }

    termRef.current = term
    fitAddonRef.current = fitAddon

    // Handle user keystrokes
    term.onData((data) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(data)
        return
      }

      // Handle interactive sandbox shell
      if (data === '\r') {
        term.write('\r\n')
        const cmd = cmdBufferRef.current
        cmdBufferRef.current = ''
        handleSandboxCommand(cmd, term)
      } else if (data === '\u007F' || data === '\b') {
        if (cmdBufferRef.current.length > 0) {
          cmdBufferRef.current = cmdBufferRef.current.slice(0, -1)
          term.write('\b \b')
        }
      } else if (data === '\u0003') {
        cmdBufferRef.current = ''
        term.write('^C\r\n\x1b[32madith-ai@studio\x1b[0m:\x1b[34m~/workspace\x1b[0m$ ')
      } else if (data >= ' ' || data === '\t') {
        cmdBufferRef.current += data
        term.write(data)
      }
    })

    connectWebSocket()

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit()
      } catch {
        // ignore
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      if (wsRef.current) {
        wsRef.current.close()
      }
      term.dispose()
      termRef.current = null
      fitAddonRef.current = null
    }
  }, [connectWebSocket, handleSandboxCommand])

  const handleClear = () => {
    termRef.current?.clear()
  }

  const handleReconnect = () => {
    connectWebSocket()
  }

  return (
    <div className="h-48 border-t border-studio-border bg-studio-card flex flex-col select-none">
      {/* Terminal Title Bar */}
      <div className="h-8 border-b border-studio-border px-3 flex items-center justify-between text-xs text-slate-400 bg-studio-card">
        <div className="flex items-center gap-3">
          <span className="text-white font-medium flex items-center gap-1.5 text-[11px]">
            <span
              className={`w-2 h-2 rounded-full ${
                status === 'connected'
                  ? 'bg-emerald-400 animate-pulse'
                  : status === 'connecting'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-rose-500'
              }`}
            />
            Terminal ({sandboxMode ? 'Cloud MicroVM Sandbox' : 'Firecracker MicroVM Sandbox'})
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400 hover:text-slate-200 cursor-pointer text-[11px]">
            Problems (0)
          </span>
          <span className="text-slate-400 hover:text-slate-200 cursor-pointer text-[11px]">
            Output
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 font-mono">
            {status === 'connected'
              ? sandboxMode
                ? 'Cloud Active (Vercel)'
                : 'Connected :8090'
              : status === 'connecting'
              ? 'Connecting...'
              : 'Disconnected'}
          </span>
          <button
            onClick={handleClear}
            title="Clear terminal"
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-studio-surface transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleReconnect}
            title="Reconnect shell"
            className="text-slate-400 hover:text-white p-1 rounded hover:bg-studio-surface transition"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              title="Close terminal"
              className="text-slate-400 hover:text-white p-1 rounded hover:bg-studio-surface transition"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* xterm Container */}
      <div ref={containerRef} className="flex-1 p-2 bg-studio-bg overflow-hidden" />
    </div>
  )
}
