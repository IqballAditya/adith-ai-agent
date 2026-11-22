import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send,
  Sparkles,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  Check,
  X,
  Loader2,
  FileCode,
  Zap,
} from 'lucide-react'
import { ChatMessage, DiffSuggestion } from '../types'
import { generateLocalAIResponse } from '../aiEngine'

interface ChatPanelProps {
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
  onAcceptDiff: (path: string, modified: string, original?: string) => Promise<boolean>
  selectedModel: string
  onSelectModel: (model: string) => void
  activeFilePath?: string
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  setMessages,
  onAcceptDiff,
  selectedModel,
  onSelectModel,
  activeFilePath,
}) => {
  const [inputPrompt, setInputPrompt] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState<boolean>(false)
  const [acceptingPath, setAcceptingPath] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const toggleReasoning = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? { ...msg, isReasoningOpen: !msg.isReasoningOpen }
          : msg
      )
    )
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const prompt = inputPrompt.trim()
    if (!prompt || isStreaming) return

    const userMessageId = `user-${Date.now()}`
    const assistantMessageId = `asst-${Date.now()}`

    const userMsg: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    }

    const asstMsg: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      reasoning: '',
      isReasoningOpen: true,
      isReasoningStreaming: true,
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMsg, asstMsg])
    setInputPrompt('')
    setIsStreaming(true)

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          workspace_id: 'default',
          prompt: prompt,
          model: selectedModel,
        }),
        signal: abortController.signal,
      })

      if (!response.ok) {
        const result = generateLocalAIResponse(prompt, selectedModel)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  reasoning: result.reasoning,
                  isReasoningStreaming: true,
                }
              : msg
          )
        )

        // Stream tokens smoothly into the UI
        const words = result.content.split(' ')
        let currentText = ''
        for (let i = 0; i < words.length; i++) {
          await new Promise((r) => setTimeout(r, 20))
          currentText += (i === 0 ? '' : ' ') + words[i]
          const isDone = i === words.length - 1
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: currentText,
                    isReasoningStreaming: false,
                    diff: isDone && result.diff ? { ...result.diff, status: 'pending' } : msg.diff,
                  }
                : msg
            )
          )
        }
        return
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data:')) continue

          const jsonStr = trimmed.slice(5).trim()
          try {
            const eventData = JSON.parse(jsonStr)
            const evtType = eventData.type

            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== assistantMessageId) return msg

                if (evtType === 'reasoning') {
                  const newReasoning = (msg.reasoning || '') + (eventData.content || '')
                  return {
                    ...msg,
                    reasoning: newReasoning,
                    isReasoningStreaming: true,
                  }
                } else if (evtType === 'message') {
                  const newContent = (msg.content || '') + (eventData.content || '')
                  return {
                    ...msg,
                    content: newContent,
                    isReasoningStreaming: false,
                  }
                } else if (evtType === 'diff') {
                  const diffData = eventData.data
                  return {
                    ...msg,
                    diff: {
                      path: diffData.path,
                      original: diffData.original,
                      modified: diffData.modified,
                      unified_diff: diffData.unified_diff,
                      status: 'pending',
                    },
                    isReasoningStreaming: false,
                  }
                } else if (evtType === 'done') {
                  return {
                    ...msg,
                    isReasoningStreaming: false,
                  }
                }
                return msg
              })
            )
          } catch {
            // Ignore malformed JSON event
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        const result = generateLocalAIResponse(prompt, selectedModel)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  reasoning: result.reasoning,
                  content: result.content,
                  diff: result.diff ? { ...result.diff, status: 'pending' } : undefined,
                  isReasoningStreaming: false,
                }
              : msg
          )
        )
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isReasoningStreaming: false }
            : msg
        )
      )
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleAcceptDiff = useCallback(
    async (messageId: string, diff: DiffSuggestion) => {
      setAcceptingPath(diff.path)
      try {
        const ok = await onAcceptDiff(diff.path, diff.modified, diff.original)
        if (ok) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === messageId && msg.diff
                ? { ...msg, diff: { ...msg.diff, status: 'applied' } }
                : msg
            )
          )
        }
      } finally {
        setAcceptingPath(null)
      }
    },
    [onAcceptDiff, setMessages]
  )

  // Quick acceptance via Tab key when not typing in an input or textarea
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        const activeEl = document.activeElement as HTMLElement | null
        const isEditing =
          activeEl &&
          (activeEl.tagName === 'INPUT' ||
            activeEl.tagName === 'TEXTAREA' ||
            activeEl.isContentEditable)

        if (!isEditing) {
          const pendingMsg = [...messages]
            .reverse()
            .find((m) => m.diff && m.diff.status === 'pending')

          if (pendingMsg && pendingMsg.diff) {
            e.preventDefault()
            handleAcceptDiff(pendingMsg.id, pendingMsg.diff)
          }
        }
      }
    }

    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [messages, handleAcceptDiff])

  const handleRejectDiff = (messageId: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId && msg.diff
          ? { ...msg, diff: { ...msg.diff, status: 'rejected' } }
          : msg
      )
    )
  }

  const handleClearChat = () => {
    if (isStreaming && abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setMessages([])
    setIsStreaming(false)
  }

  const renderDiffSnippet = (messageId: string, diff: DiffSuggestion) => {
    const rawLines = diff.unified_diff ? diff.unified_diff.split('\n') : []
    let addedCount = 0
    let removedCount = 0

    rawLines.forEach((line) => {
      if (line.startsWith('+') && !line.startsWith('+++')) addedCount++
      if (line.startsWith('-') && !line.startsWith('---')) removedCount++
    })

    const displayLines = rawLines.slice(0, 20)

    return (
      <div className="bg-studio-bg border border-studio-border rounded-lg overflow-hidden font-mono text-[11px] my-2 shadow-lg">
        {/* Diff Card Header */}
        <div className="bg-studio-card px-2.5 py-1.5 border-b border-studio-border flex items-center justify-between text-slate-400 text-[10px]">
          <div className="flex items-center gap-1.5">
            <FileCode className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-semibold text-slate-200">{diff.path}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-semibold">+{addedCount}</span>
            <span className="text-rose-400 font-semibold">-{removedCount}</span>
            {diff.status === 'applied' && (
              <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.2 rounded text-[10px] font-sans">
                Applied
              </span>
            )}
            {diff.status === 'rejected' && (
              <span className="bg-rose-500/20 text-rose-300 border border-rose-500/30 px-1.5 py-0.2 rounded text-[10px] font-sans">
                Rejected
              </span>
            )}
          </div>
        </div>

        {/* Diff Lines Body */}
        <div className="p-2 space-y-0.5 overflow-x-auto max-h-48">
          {displayLines.map((line, idx) => {
            if (line.startsWith('+') && !line.startsWith('+++')) {
              return (
                <div
                  key={idx}
                  className="text-emerald-400 bg-emerald-500/10 px-1 rounded whitespace-pre"
                >
                  {line}
                </div>
              )
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              return (
                <div
                  key={idx}
                  className="text-rose-400 bg-rose-500/10 px-1 rounded whitespace-pre"
                >
                  {line}
                </div>
              )
            } else if (line.startsWith('@@')) {
              return (
                <div
                  key={idx}
                  className="text-indigo-400/80 bg-indigo-950/30 px-1 rounded text-[10px] whitespace-pre"
                >
                  {line}
                </div>
              )
            }
            return (
              <div key={idx} className="text-slate-400 px-1 whitespace-pre">
                {line}
              </div>
            )
          })}
          {rawLines.length > 20 && (
            <div className="text-slate-500 text-[10px] italic px-1 pt-1">
              ... +{rawLines.length - 20} more lines
            </div>
          )}
        </div>

        {/* Diff Action Footer */}
        {diff.status === 'pending' ? (
          <div className="bg-studio-card p-2 border-t border-studio-border flex items-center gap-2">
            <button
              onClick={() => handleAcceptDiff(messageId, diff)}
              disabled={acceptingPath === diff.path}
              className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-sans font-medium py-1 px-3 rounded text-xs flex items-center justify-center gap-1.5 transition"
            >
              {acceptingPath === diff.path ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Applying Changes...
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  Accept Changes (Tab)
                </>
              )}
            </button>
            <button
              onClick={() => handleRejectDiff(messageId)}
              className="px-2.5 py-1 bg-studio-surface hover:bg-studio-active text-slate-400 hover:text-white rounded text-xs font-sans transition flex items-center gap-1"
            >
              <X className="w-3 h-3" />
              Reject
            </button>
          </div>
        ) : diff.status === 'applied' ? (
          <div className="bg-emerald-950/20 border-t border-emerald-500/20 p-2 text-emerald-400 text-xs flex items-center justify-center gap-1.5 font-sans">
            <Check className="w-3.5 h-3.5 text-emerald-400" />
            Changes successfully applied to workspace
          </div>
        ) : (
          <div className="bg-rose-950/20 border-t border-rose-500/20 p-2 text-rose-400 text-xs flex items-center justify-center gap-1.5 font-sans">
            <X className="w-3.5 h-3.5 text-rose-400" />
            Changes discarded
          </div>
        )}
      </div>
    )
  }

  return (
    <section className="w-96 bg-studio-card border-r border-studio-border flex flex-col flex-shrink-0 select-none h-full">
      {/* Agent Header */}
      <div className="h-10 border-b border-studio-border px-3 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              isStreaming ? 'bg-indigo-400 animate-ping' : 'bg-emerald-400'
            }`}
          />
          <span className="font-semibold text-slate-200">ADITH AI Copilot</span>
          <span className="text-[10px] text-slate-500 font-mono">Agentic Mode</span>
        </div>
        <div className="flex items-center gap-1 text-slate-400">
          <button
            onClick={handleClearChat}
            title="Reset conversation"
            className="hover:text-white p-1 rounded hover:bg-studio-surface transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 p-3 overflow-y-auto space-y-4 text-xs">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-4 space-y-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="font-semibold text-slate-300 text-xs">
                Ask ADITH AI Copilot
              </p>
              <p className="text-[11px] text-slate-500 mt-1 max-w-[240px]">
                Ask to refactor code, explain architecture, or generate AST-validated diff patches.
              </p>
            </div>
            <div className="space-y-1.5 w-full pt-2">
              <button
                onClick={() =>
                  setInputPrompt(
                    activeFilePath
                      ? `Refactor ${activeFilePath} to improve performance and error handling`
                      : 'Refactor endpoint /api/v1/checkout to add idempotency guard'
                  )
                }
                className="w-full text-left bg-studio-surface hover:bg-studio-active border border-studio-border p-2 rounded text-[11px] text-slate-300 transition"
              >
                ⚡ {activeFilePath ? `Refactor ${activeFilePath}` : 'Refactor checkout endpoint'}
              </button>
              <button
                onClick={() =>
                  setInputPrompt('Explain architecture and data flow in this workspace')
                }
                className="w-full text-left bg-studio-surface hover:bg-studio-active border border-studio-border p-2 rounded text-[11px] text-slate-300 transition"
              >
                🔍 Explain codebase structure
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            if (msg.role === 'user') {
              return (
                <div key={msg.id} className="flex items-start gap-2.5">
                  <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center font-bold text-white text-[10px] flex-shrink-0">
                    IA
                  </div>
                  <div className="bg-studio-surface border border-studio-border p-2.5 rounded-lg text-slate-200 max-w-[85%] leading-relaxed select-text">
                    {msg.content}
                  </div>
                </div>
              )
            }

            return (
              <div key={msg.id} className="flex items-start gap-2.5">
                <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center text-white text-[10px] flex-shrink-0 font-bold">
                  AI
                </div>
                <div className="space-y-2 flex-1 overflow-hidden select-text">
                  {/* Reasoning Trace */}
                  {msg.reasoning && (
                    <div className="border border-indigo-500/20 bg-indigo-950/20 rounded-lg p-2.5 text-[11px] space-y-1.5">
                      <div
                        onClick={() => toggleReasoning(msg.id)}
                        className="flex items-center justify-between text-indigo-400 font-medium cursor-pointer select-none"
                      >
                        <span className="flex items-center gap-1.5">
                          {msg.isReasoningStreaming ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                          ) : (
                            <Zap className="w-3.5 h-3.5 text-indigo-400" />
                          )}
                          <span>Reasoning Process</span>
                        </span>
                        <div className="flex items-center gap-1 text-slate-500 text-[10px]">
                          {msg.isReasoningOpen ? (
                            <ChevronDown className="w-3 h-3" />
                          ) : (
                            <ChevronRight className="w-3 h-3" />
                          )}
                        </div>
                      </div>

                      {msg.isReasoningOpen && (
                        <p className="text-slate-400 leading-relaxed font-mono text-[10px] whitespace-pre-wrap border-t border-indigo-500/10 pt-1.5">
                          {msg.reasoning}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Message Body */}
                  {msg.content && (
                    <div className="bg-studio-surface border border-studio-border p-3 rounded-lg text-slate-300 leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </div>
                  )}

                  {/* Diff Suggestion Card */}
                  {msg.diff && renderDiffSnippet(msg.id, msg.diff)}
                </div>
              </div>
            )
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Area */}
      <div className="p-3 border-t border-studio-border bg-studio-card">
        <form onSubmit={handleSubmit} className="relative">
          <div className="bg-studio-surface border border-studio-border rounded-lg p-2 focus-within:border-indigo-500 transition">
            <textarea
              ref={textareaRef}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask or instruct ADITH AI... (Enter to send, Shift+Enter for newline)"
              rows={2}
              className="w-full bg-transparent text-xs text-white placeholder-slate-500 outline-none resize-none font-sans"
            />
            <div className="flex items-center justify-between pt-1 border-t border-studio-border/50 text-[11px] text-slate-400 select-none">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setInputPrompt((p) => p + ' @Files ')}
                  className="hover:text-indigo-400 cursor-pointer text-[10px]"
                >
                  @Files
                </button>
                <button
                  type="button"
                  onClick={() => setInputPrompt((p) => p + ' #Docs ')}
                  className="hover:text-indigo-400 cursor-pointer text-[10px]"
                >
                  #Docs
                </button>
                <button
                  type="button"
                  onClick={() => setInputPrompt((p) => p + ' /MCP ')}
                  className="hover:text-indigo-400 cursor-pointer text-[10px]"
                >
                  /MCP
                </button>
              </div>

              <div className="flex items-center gap-2">
                {isStreaming ? (
                  <button
                    type="button"
                    onClick={() => abortControllerRef.current?.abort()}
                    className="bg-rose-600 hover:bg-rose-500 text-white px-2 py-0.5 rounded text-[10px] flex items-center gap-1 transition"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!inputPrompt.trim()}
                    className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white w-6 h-6 rounded flex items-center justify-center transition"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </form>
      </div>
    </section>
  )
}
