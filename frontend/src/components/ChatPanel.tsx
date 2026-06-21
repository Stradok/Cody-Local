"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Message, ToolCall } from "@/types"
import { chat, runAgent, searchFiles, readFileContent, pullModel } from "@/lib/api"
import ToolCallCard from "./ToolCallCard"

interface Props {
  model: string
  workspace: string
  onFileWritten?: (path: string, workspace: string) => void
  onToast?: (message: string, type: "success" | "error" | "info" | "warning") => void
}

interface Mention {
  name: string
  path: string
  relative: string
}

type Mode = "plan" | "build"

const MODE_CONFIG = {
  plan: {
    label: "Plan",
    placeholder: "Describe what you want to build, ask architecture questions…",
    welcome: "Planning mode — I'll analyze requirements, ask questions, and produce implementation plans.",
    welcomeSub: "No code is written in this mode.",
  },
  build: {
    label: "Build",
    placeholder: "Describe what to build — I'll plan and execute it…",
    welcome: "Build mode — I'll plan and autonomously execute tasks.",
    welcomeSub: "Files are written to your workspace.",
  },
} as const

export default function ChatPanel({ model, workspace, onFileWritten, onToast }: Props) {
  const [mode, setMode] = useState<Mode>("plan")
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "How can I help you build today?" },
  ])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)

  // Agent/build state
  const [plan, setPlan] = useState<string[]>([])
  const [stepTypes, setStepTypes] = useState<string[]>([])
  const [currentStep, setCurrentStep] = useState(-1)
  const [agentStatus, setAgentStatus] = useState("")

  // Error / pull state
  const [modelError, setModelError] = useState<string | null>(null)
  const [pulling, setPulling] = useState(false)
  const [pullProgress, setPullProgress] = useState("")

  // @-mention state
  const [showMentions, setShowMentions] = useState(false)
  const [mentionQuery, setMentionQuery] = useState("")
  const [mentionIdx, setMentionIdx] = useState(0)
  const [suggestions, setSuggestions] = useState<Mention[]>([])
  const [mentionedFiles, setMentionedFiles] = useState<Map<string, string>>(new Map())

  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const sessionRef = useRef("")

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, plan])

  useEffect(() => {
    if (!streaming) { setPlan([]); setCurrentStep(-1); setAgentStatus("") }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const fetchSuggestions = useCallback(async (q: string) => {
    if (!workspace || !q) { setSuggestions([]); return }
    const data = await searchFiles(workspace, q)
    if (!data.error) setSuggestions(data.results.slice(0, 8))
  }, [workspace])

  function handleInput(value: string) {
    setInput(value)
    const at = value.lastIndexOf("@")
    if (at !== -1 && (at === 0 || value[at - 1] === " ")) {
      const q = value.slice(at + 1).split(" ")[0]
      if (q.length > 0) {
        setShowMentions(true)
        setMentionQuery(q)
        setMentionIdx(0)
        setTimeout(() => fetchSuggestions(q), 100)
        return
      }
    }
    setShowMentions(false)
  }

  function selectMention(s: Mention) {
    const at = input.lastIndexOf("@")
    const before = input.slice(0, at)
    const after = input.slice(at + mentionQuery.length + 1)
    setInput(before + `@${s.relative} ` + after)
    setMentionedFiles((p) => new Map(p).set(s.relative, s.path))
    setShowMentions(false)
    inputRef.current?.focus()
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (showMentions) {
      if (e.key === "ArrowDown")  { e.preventDefault(); setMentionIdx((i) => Math.min(i + 1, suggestions.length - 1)); return }
      if (e.key === "ArrowUp")    { e.preventDefault(); setMentionIdx((i) => Math.max(i - 1, 0)); return }
      if (e.key === "Enter" && suggestions[mentionIdx]) { e.preventDefault(); selectMention(suggestions[mentionIdx]); return }
      if (e.key === "Escape")     { setShowMentions(false); return }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  async function buildContent(raw: string): Promise<string> {
    let content = raw.trim()
    const ctx: string[] = []
    for (const [tag, filePath] of mentionedFiles) {
      const data = await readFileContent(filePath)
      if (!data.error) ctx.push(`File ${tag}:\n\`\`\`\n${data.content}\n\`\`\``)
    }
    if (ctx.length > 0) content = `I'm referencing these files:\n${ctx.join("\n\n")}\n\nMy request: ${content}`
    return content
  }

  async function handleSend() {
    if (!input.trim() || streaming) return
    setModelError(null)
    if (mode === "build") await handleBuildSend()
    else await handlePlanSend()
  }

  async function handlePlanSend() {
    const finalContent = await buildContent(input)
    const userMsg: Message = { role: "user", content: input.trim() }
    setMessages((p) => [...p, userMsg])
    setInput("")
    setMentionedFiles(new Map())
    setStreaming(true)

    const apiMessages = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }))
    apiMessages[apiMessages.length - 1].content = finalContent

    setMessages((p) => [...p, { role: "assistant", content: "" }])

    await chat(
      model, apiMessages, workspace,
      (chunk) => setMessages((p) => {
        const a = [...p]
        a[a.length - 1] = { ...a[a.length - 1], content: a[a.length - 1].content + chunk }
        return a
      }),
      () => {},  // no tool calls in plan mode
      () => {},
      () => setStreaming(false),
      (errMsg) => {
        setModelError(errMsg)
        setMessages((p) => p.slice(0, -1))
        setStreaming(false)
        onToast?.(`${errMsg.split("\n")[0]}`, "error")
      },
      "plan",
    )
  }

  async function handleBuildSend() {
    const finalContent = await buildContent(input)
    const userMsg: Message = { role: "user", content: input.trim() }
    setMessages((p) => [...p, userMsg])
    setInput("")
    setMentionedFiles(new Map())
    setStreaming(true)
    setPlan([])
    setStepTypes([])
    setCurrentStep(-1)
    setAgentStatus(`Starting with ${model}…`)
    sessionRef.current = `build-${Date.now()}`

    const apiMessages = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }))
    apiMessages[apiMessages.length - 1].content = finalContent

    setMessages((p) => [...p, { role: "assistant", content: "" }])

    await runAgent(model, apiMessages, workspace, sessionRef.current, {
      onStatus:    (msg) => setAgentStatus(msg),
      onPlan:      (steps, types) => {
        setPlan(steps)
        setStepTypes(types || [])
        setCurrentStep(0)
        setAgentStatus("Executing plan…")
      },
      onStepStart: (step, desc, agent) => {
        setCurrentStep(step)
        const agentTag = agent ? `[${agent}] ` : ""
        setAgentStatus(`${agentTag}Step ${step + 1}: ${desc.slice(0, 50)}${desc.length > 50 ? "…" : ""}`)
      },
      onStepDone:  (step) => setCurrentStep(step + 1),
      onToolCall:  (name, args) => setMessages((p) => {
        const a = [...p]; const m = { ...a[a.length - 1] }
        m.toolCalls = [...(m.toolCalls || []), { name, arguments: args }]
        a[a.length - 1] = m; return a
      }),
      onToolResult: (name, result) => setMessages((p) => {
        const a = [...p]; const m = { ...a[a.length - 1] }
        const calls = [...(m.toolCalls || [])]
        const idx = calls.findIndex((tc: ToolCall) => tc.name === name && !tc.result)
        if (idx !== -1) calls[idx] = { ...calls[idx], result }
        m.toolCalls = calls; a[a.length - 1] = m; return a
      }),
      onFileWritten: (path, ws) => {
        onFileWritten?.(path, ws)
        onToast?.(`Created: ${path.split("/").pop() || path}`, "success")
      },
      onChunk: (chunk) => setMessages((p) => {
        const a = [...p]
        a[a.length - 1] = { ...a[a.length - 1], content: a[a.length - 1].content + chunk }
        return a
      }),
      onWarning: (msg) => { setAgentStatus(`⚠ ${msg.slice(0, 60)}`); onToast?.(msg.slice(0, 80), "warning") },
      onError: (msg) => {
        setModelError(msg)
        setMessages((p) => p.slice(0, -1))
        setStreaming(false)
        setAgentStatus("")
        onToast?.(`Agent error: ${msg.split("\n")[0]}`, "error")
      },
      onDone: () => { setStreaming(false); setAgentStatus("") },
    })
  }

  async function handlePullModel() {
    if (!model || pulling) return
    setPulling(true)
    setPullProgress("Starting download…")
    setModelError(null)

    await pullModel(
      model,
      (status, pct) => setPullProgress(pct != null ? `${status} — ${pct}%` : status),
      () => {
        setPulling(false)
        setPullProgress("")
        onToast?.(`Model "${model}" downloaded successfully`, "success")
        window.location.reload()
      },
      (err) => {
        setPulling(false)
        setPullProgress("")
        setModelError(`Pull failed: ${err}`)
      },
    )
  }

  const isModelNotFound = modelError
    ? (modelError.includes("not installed") || modelError.includes("ollama pull") || modelError.includes("404"))
    : false

  const showEmpty   = !workspace
  const showWelcome = workspace && messages.length === 1 && !streaming && !modelError
  const cfg = MODE_CONFIG[mode]

  // Agent type badge colors
  const agentColor: Record<string, string> = {
    coding:     "text-blue-400",
    filesystem: "text-yellow-400",
    terminal:   "text-green-400",
    validation: "text-purple-400",
  }

  return (
    <div className="flex flex-col h-full min-h-0 relative">

      {/* Mode tabs + model badge */}
      {workspace && (
        <div className="shrink-0 flex items-center justify-between pb-2 border-b border-muted/10 mb-2">
          <div className="flex items-center gap-1">
            {(["plan", "build"] as Mode[]).map((m) => (
              <button key={m} onClick={() => !streaming && setMode(m)} disabled={streaming}
                className={`px-3 py-1 rounded-[12px] text-[10px] font-medium transition-all duration-200 ${
                  mode === m ? "neu-inset-sm text-accent" : "text-muted hover:text-fg disabled:opacity-40"
                }`}
              >
                {MODE_CONFIG[m].label}
              </button>
            ))}
            {agentStatus && mode === "build" && (
              <span className="ml-2 text-[9px] text-muted truncate max-w-[140px] animate-pulse">{agentStatus}</span>
            )}
          </div>
          {model && (
            <span className="text-[9px] text-muted/60 font-mono truncate max-w-[100px]" title={model}>
              {model.split(":")[0]}
            </span>
          )}
        </div>
      )}

      {/* Model error / not-found banner */}
      {modelError && (
        <div className="shrink-0 animate-slide-up mb-2 p-3 rounded-[16px] neu-inset-sm border border-red-300/20">
          <div className="flex items-start gap-2">
            <span className="text-red-400 text-xs font-bold shrink-0 mt-px">✕</span>
            <p className="text-[10px] text-fg/80 leading-relaxed whitespace-pre-wrap flex-1 min-w-0">{modelError}</p>
            <button onClick={() => setModelError(null)} className="text-muted hover:text-fg text-[10px] shrink-0">✕</button>
          </div>
          {isModelNotFound && (
            <div className="flex items-center gap-2 mt-2 pl-4">
              <button onClick={handlePullModel} disabled={pulling}
                className="neu-extruded-sm px-3 py-1.5 rounded-[10px] text-[10px] font-medium text-accent hover:text-fg transition-all duration-200 disabled:opacity-50"
              >
                {pulling
                  ? <><span className="inline-block w-2.5 h-2.5 border-2 border-accent/30 border-t-accent rounded-full animate-spin mr-1.5" />Downloading…</>
                  : `Pull "${model}"`
                }
              </button>
              {pullProgress && <span className="text-[10px] text-muted animate-pulse">{pullProgress}</span>}
            </div>
          )}
        </div>
      )}

      {showEmpty ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-muted text-xs text-center">Open a project first</p>
        </div>
      ) : showWelcome ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-muted text-xs text-center leading-relaxed">
            {cfg.welcome}<br />
            <span className="opacity-50 text-[10px]">{cfg.welcomeSub}</span>
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-auto space-y-3 px-1 min-h-0">

          {/* Build plan tracker */}
          {mode === "build" && plan.length > 0 && (
            <div className="neu-inset-sm rounded-[16px] p-3 animate-slide-down">
              <p className="text-[9px] font-display font-bold text-muted uppercase tracking-widest mb-2">Execution Plan</p>
              <div className="space-y-1">
                {plan.map((step, i) => {
                  const stype = stepTypes[i] || "coding"
                  const typeColor = agentColor[stype] || "text-muted"
                  return (
                    <div key={i} className={`flex items-start gap-2 text-[10px] transition-all duration-300 ${
                      i < currentStep ? "text-muted" : i === currentStep ? "text-fg font-medium" : "text-fg/45"
                    }`}>
                      <span className="shrink-0 w-4 font-mono text-center leading-relaxed">
                        {i < currentStep ? "✓" : i === currentStep ? "▶" : `${i + 1}.`}
                      </span>
                      <span className={`shrink-0 text-[8px] font-mono uppercase ${typeColor} w-14`}>{stype}</span>
                      <span className={`leading-snug ${i < currentStep ? "line-through opacity-60" : ""}`}>
                        {step.replace(/^\d+\.\s*/, "")}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.slice(1).map((msg, i) => {
            const isLast = i === messages.length - 2
            const isStreamingThis = isLast && streaming && msg.role === "assistant"
            return (
              <div key={i} className="msg-enter">
                <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`rounded-[16px] px-3.5 py-2.5 text-xs leading-relaxed ${
                    msg.role === "user"
                      ? "bg-accent text-white max-w-[88%] shadow-sm"
                      : "text-fg w-full"
                  }`}>
                    {msg.role === "assistant" && msg.content === "" && isStreamingThis ? (
                      <span className="inline-block w-[2px] h-[14px] bg-accent/60 align-middle animate-blink rounded-sm" />
                    ) : (
                      <span className={`whitespace-pre-wrap break-words${isStreamingThis && msg.content ? " streaming-cursor" : ""}`}>
                        {msg.content}
                      </span>
                    )}
                  </div>
                </div>
                {msg.toolCalls?.map((tc, j) => <ToolCallCard key={j} toolCall={tc} />)}
              </div>
            )
          })}
          <div ref={endRef} />
        </div>
      )}

      {/* @-mention dropdown */}
      {showMentions && suggestions.length > 0 && (
        <div className="absolute bottom-[60px] left-1 right-1 neu-extruded-sm bg-[#E0E5EC] rounded-[16px] z-10 max-h-40 overflow-auto p-1 animate-slide-up">
          {suggestions.map((s, i) => (
            <button key={s.path} onClick={() => selectMention(s)} onMouseEnter={() => setMentionIdx(i)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-[12px] text-xs text-left transition-all ${
                i === mentionIdx ? "neu-inset-sm text-fg" : "text-muted hover:text-fg"
              }`}
            >
              <span className="text-muted/50">📄</span>
              <span className="truncate">{s.relative}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="shrink-0 pt-2">
        <div className="flex gap-1.5">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={cfg.placeholder}
            disabled={streaming || !workspace || pulling}
            className="flex-1 bg-[#E0E5EC] text-fg text-[11px] px-4 py-2.5 rounded-[16px] neu-inset-sm placeholder:text-[#A0AEC0] transition-all duration-300 focus:neu-inset-deep disabled:opacity-40"
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim() || !workspace || pulling}
            className="neu-extruded-sm bg-[#E0E5EC] text-accent hover:text-fg px-4 py-2.5 rounded-[16px] text-xs font-medium transition-all duration-300 hover:-translate-y-[1px] hover:neu-extruded-hover active:translate-y-[0.5px] active:neu-inset-sm disabled:opacity-40 min-w-[56px] flex items-center justify-center"
          >
            {streaming
              ? <span className="w-3 h-3 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              : "Send"
            }
          </button>
        </div>
      </div>
    </div>
  )
}
