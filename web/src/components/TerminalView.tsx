import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { RotateCw, Trash2, X, Terminal as TerminalIcon } from 'lucide-react'

interface TerminalViewProps {
  onClose?: () => void
}

export const TerminalView: React.FC<TerminalViewProps> = ({ onClose }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')

  const connectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const term = termRef.current
    if (!term) return

    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.port === '5173' ? 'localhost:8090' : window.location.host
    const wsUrl = `${protocol}//${host}/api/terminal`

    try {
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
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
        setStatus('disconnected')
      }

      ws.onclose = () => {
        setStatus('disconnected')
        term.writeln('\r\n\x1b[31m[terminal]\x1b[0m Connection closed.')
      }
    } catch (err: any) {
      setStatus('disconnected')
      term.writeln(`\r\n\x1b[31m[terminal error]\x1b[0m ${err.message}`)
    }
  }, [])

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

    // Initial fit
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
      }
    })

    connectWebSocket()

    // Resize observer
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
  }, [connectWebSocket])

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
            Terminal (Firecracker MicroVM Sandbox)
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
              ? 'Connected :8090'
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
