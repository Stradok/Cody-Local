"use client"

import { useState, useEffect } from "react"
import { Episode, SemanticMemory } from "@/types"
import {
  memoryListEpisodes,
  memoryDeleteEpisode,
  memoryListSemantic,
  memoryAddSemantic,
  memoryDeleteSemantic,
  memoryListSessionLogs,
} from "@/lib/api"

type Tab = "facts" | "episodes" | "logs"

export default function MemoryPanel() {
  const [tab, setTab] = useState<Tab>("facts")

  const [facts, setFacts]         = useState<SemanticMemory[]>([])
  const [episodes, setEpisodes]   = useState<Episode[]>([])
  const [logs, setLogs]           = useState<{ filename: string; path: string }[]>([])
  const [logsDir, setLogsDir]     = useState("")
  const [loading, setLoading]     = useState(false)

  const [newKey, setNewKey]     = useState("")
  const [newValue, setNewValue] = useState("")
  const [addError, setAddError] = useState("")
  const [showAdd, setShowAdd]   = useState(false)

  useEffect(() => { load() }, [tab])

  async function load() {
    setLoading(true)
    if (tab === "facts") {
      const d = await memoryListSemantic()
      if (!d.error) setFacts(d.facts)
    } else if (tab === "episodes") {
      const d = await memoryListEpisodes()
      if (!d.error) setEpisodes(d.episodes)
    } else {
      const d = await memoryListSessionLogs()
      if (!d.error) {
        setLogs(d.logs || [])
        setLogsDir(d.logs_dir || "")
      }
    }
    setLoading(false)
  }

  async function handleDeleteFact(id: number) {
    await memoryDeleteSemantic(id)
    setFacts((p) => p.filter((f) => f.id !== id))
  }

  async function handleDeleteEpisode(id: number) {
    await memoryDeleteEpisode(id)
    setEpisodes((p) => p.filter((e) => e.id !== id))
  }

  async function handleAddFact() {
    if (!newKey.trim() || !newValue.trim()) return
    setAddError("")
    const res = await memoryAddSemantic(newKey.trim(), newValue.trim())
    if (res.error) { setAddError(res.error); return }
    setNewKey(""); setNewValue(""); setShowAdd(false)
    load()
  }

  return (
    <div className="flex flex-col h-full min-h-0">

      {/* Sub-tabs */}
      <div className="shrink-0 flex gap-1 pb-2 mb-1 border-b border-muted/10">
        {(["facts", "episodes", "logs"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-1.5 rounded-[10px] text-[9px] font-medium uppercase tracking-wide transition-all ${
              tab === t ? "neu-inset-sm text-accent" : "text-muted hover:text-fg"
            }`}
          >
            {t === "facts" ? "Facts" : t === "episodes" ? "Episodes" : "Logs"}
          </button>
        ))}
      </div>

      {/* ── Facts tab ── */}
      {tab === "facts" && (
        <div className="flex flex-col h-full min-h-0">
          <div className="shrink-0 flex items-center justify-between px-1 mb-2">
            <span className="text-[9px] text-muted">{facts.length} stored facts</span>
            <button
              onClick={() => { setShowAdd(!showAdd); setAddError("") }}
              className={`text-[10px] px-2 py-1 rounded-[8px] transition-all ${
                showAdd ? "neu-inset-sm text-accent" : "neu-extruded-sm text-accent hover:text-fg"
              }`}
            >
              {showAdd ? "Cancel" : "+ Add"}
            </button>
          </div>

          {showAdd && (
            <div className="shrink-0 mb-2 p-2 rounded-[12px] neu-inset-sm space-y-1.5 animate-slide-down">
              <input
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="key (e.g. preferred_model)"
                className="w-full bg-transparent text-fg text-[10px] px-2.5 py-1.5 rounded-[8px] neu-inset-sm placeholder:text-muted/50 focus:outline-none"
              />
              <input
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddFact()}
                placeholder="value"
                className="w-full bg-transparent text-fg text-[10px] px-2.5 py-1.5 rounded-[8px] neu-inset-sm placeholder:text-muted/50 focus:outline-none"
              />
              {addError && <p className="text-red-400 text-[9px]">{addError}</p>}
              <button
                onClick={handleAddFact}
                disabled={!newKey.trim() || !newValue.trim()}
                className="w-full py-1.5 rounded-[8px] text-[10px] font-medium neu-extruded-sm text-accent hover:text-fg transition-all disabled:opacity-40"
              >
                Save Fact
              </button>
            </div>
          )}

          <div className="flex-1 overflow-auto space-y-0.5 min-h-0 pr-1">
            {loading && <p className="text-muted text-[10px] p-2 animate-pulse">Loading…</p>}
            {!loading && facts.length === 0 && (
              <div className="text-center py-6">
                <p className="text-muted text-[11px]">No facts yet.</p>
                <p className="text-muted/50 text-[10px] mt-1">Saved automatically after conversations.</p>
              </div>
            )}
            {facts.map((f) => (
              <div key={f.id} className="flex items-start gap-2 px-2 py-2 rounded-[10px] hover:neu-inset-sm transition-all group">
                <div className="flex-1 min-w-0">
                  <p className="text-[9px] font-mono text-accent truncate">{f.key}</p>
                  <p className="text-[10px] text-fg leading-snug">{f.value}</p>
                  <p className="text-[9px] text-muted/50">{f.updated_at.slice(0, 10)}</p>
                </div>
                <button
                  onClick={() => handleDeleteFact(f.id)}
                  className="opacity-0 group-hover:opacity-100 text-[11px] text-muted hover:text-red-400 transition-all shrink-0 px-1"
                >×</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Episodes tab ── */}
      {tab === "episodes" && (
        <div className="flex-1 overflow-auto space-y-1.5 min-h-0 pr-1">
          {loading && <p className="text-muted text-[10px] p-2 animate-pulse">Loading…</p>}
          {!loading && episodes.length === 0 && (
            <div className="text-center py-6">
              <p className="text-muted text-[11px]">No episodes yet.</p>
              <p className="text-muted/50 text-[10px] mt-1">Summaries are saved after each session.</p>
            </div>
          )}
          {episodes.map((ep) => (
            <div key={ep.id} className="group p-2.5 rounded-[12px] neu-inset-sm">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] text-muted">{ep.created_at.slice(0, 10)}</span>
                  {ep.workspace && (
                    <span className="text-[9px] text-accent/70 truncate max-w-[80px]">
                      {ep.workspace.split("/").pop()}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => handleDeleteEpisode(ep.id)}
                  className="opacity-0 group-hover:opacity-100 text-[10px] text-muted hover:text-red-400 transition-all"
                >×</button>
              </div>
              <p className="text-[10px] text-fg leading-relaxed">{ep.summary}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Logs tab ── */}
      {tab === "logs" && (
        <div className="flex flex-col h-full min-h-0">
          {logsDir && (
            <p className="shrink-0 text-[9px] text-muted/60 px-1 mb-2 font-mono truncate" title={logsDir}>
              {logsDir}
            </p>
          )}
          <div className="flex-1 overflow-auto space-y-0.5 min-h-0 pr-1">
            {loading && <p className="text-muted text-[10px] p-2 animate-pulse">Loading…</p>}
            {!loading && logs.length === 0 && (
              <div className="text-center py-6">
                <p className="text-muted text-[11px]">No session logs yet.</p>
                <p className="text-muted/50 text-[10px] mt-1">Saved automatically after sessions.</p>
              </div>
            )}
            {logs.map((log) => (
              <div key={log.filename} className="flex items-center gap-2 px-2 py-2 rounded-[10px] hover:neu-inset-sm transition-all">
                <span className="text-muted/50 text-[10px] shrink-0">📄</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-fg truncate font-mono">{log.filename}</p>
                  <p className="text-[9px] text-muted/50 truncate">{log.path}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
