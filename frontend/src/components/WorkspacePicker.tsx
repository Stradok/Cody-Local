"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { FileEntry } from "@/types"
import {
  setWorkspace,
  validateWorkspace,
  exploreDirectory,
  browseRoots,
  listRecentWorkspaces,
  removeRecentWorkspace,
} from "@/lib/api"

interface Props {
  onWorkspaceOpen: (path: string) => void
}

export default function WorkspacePicker({ onWorkspaceOpen }: Props) {
  const [path, setPath] = useState("")
  const [recent, setRecent] = useState<Array<{ path: string; resolved: string; label: string; last_opened: string }>>([])
  const [roots, setRoots] = useState<Array<{ path: string; label: string }>>([])
  const [browsing, setBrowsing] = useState(false)
  const [browseEntries, setBrowseEntries] = useState<FileEntry[]>([])
  const [browseHistory, setBrowseHistory] = useState<string[]>(["/"])
  const [errors, setErrors] = useState<string | null>(null)
  const [validating, setValidating] = useState(false)
  const [valid, setValid] = useState<boolean | null>(null)
  const [opening, setOpening] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const validateTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    browseRoots().then((r) => { if (!r.error) setRoots(r.roots.map((x) => ({ path: x.path, label: x.label }))) })
    listRecentWorkspaces().then((r) => { if (!r.error) setRecent(r.workspaces) })
  }, [])

  // Debounced live validation
  const doValidate = useCallback(async (p: string) => {
    if (!p.trim()) { setValid(null); setErrors(null); return }
    setValidating(true)
    const r = await validateWorkspace(p.trim())
    setValidating(false)
    if (r.valid) { setValid(true); setErrors(null) }
    else { setValid(false); setErrors(r.error || "Invalid path") }
  }, [])

  function handlePathChange(value: string) {
    setPath(value)
    setValid(null)
    setErrors(null)
    clearTimeout(validateTimer.current)
    if (value.trim().length > 2) {
      validateTimer.current = setTimeout(() => doValidate(value), 400)
    }
  }

  async function handleOpen(targetPath?: string) {
    const p = (targetPath || path).trim()
    if (!p) return
    setOpening(true)
    setErrors(null)
    const r = await setWorkspace(p)
    setOpening(false)
    if (r.error) {
      setErrors(r.error)
      return
    }
    // Refresh recent list
    listRecentWorkspaces().then((l) => { if (!l.error) setRecent(l.workspaces) })
    onWorkspaceOpen(r.path)
  }

  async function handleBrowseOpen(dir: string) {
    const data = await exploreDirectory(dir)
    if (data.error) { setErrors(data.error); return }
    setBrowseEntries(data.entries)
    setBrowseHistory((prev) => [...prev, dir])
  }

  function handleBrowseBack() {
    if (browseHistory.length <= 1) return
    const prev = browseHistory.slice(0, -1)
    setBrowseHistory(prev)
    if (prev.length > 0) {
      exploreDirectory(prev[prev.length - 1]).then((data) => {
        if (!data.error) setBrowseEntries(data.entries)
      })
    }
  }

  function handleBrowseSelect(dir: string) {
    setPath(dir)
    setBrowsing(false)
    doValidate(dir)
    inputRef.current?.focus()
  }

  async function handleRemoveRecent(rpath: string) {
    await removeRecentWorkspace(rpath)
    setRecent((prev) => prev.filter((r) => r.path !== rpath))
  }

  // Browse mode
  if (browsing) {
    const currentDir = browseHistory[browseHistory.length - 1]
    return (
      <div className="flex flex-col h-full min-h-0">
        <div className="flex items-center gap-2 mb-2">
          <button onClick={() => { if (browseHistory.length > 1) handleBrowseBack(); else setBrowsing(false) }}
            className="neu-extruded-sm px-3 py-1.5 rounded-[16px] text-[11px] font-medium text-muted hover:text-fg transition-all duration-300"
          >{browseHistory.length > 1 ? "← Back" : "✕ Close"}</button>
          <span className="text-xs text-fg font-medium truncate">{currentDir}</span>
        </div>
        <div className="flex-1 overflow-auto space-y-[1px] pr-1">
          {browseEntries.map((e) => (
            <button key={e.path} onClick={() => {
              if (e.type === "directory") handleBrowseOpen(e.path)
              else handleBrowseSelect(e.path)
            }}
              className="w-full flex items-center gap-2 px-3 py-1.5 rounded-[12px] text-[11px] text-left transition-all duration-200 hover:neu-inset-sm group"
            >
              <span className="text-xs shrink-0">{e.type === "directory" ? "📁" : "📄"}</span>
              <span className="truncate text-fg">{e.name}</span>
              {e.type === "directory" && (
                <button onClick={(ev) => { ev.stopPropagation(); handleBrowseSelect(e.path) }}
                  className="ml-auto text-[10px] text-accent opacity-0 group-hover:opacity-100 transition-opacity px-2 py-0.5 rounded-[8px] neu-extruded-sm"
                >Select</button>
              )}
            </button>
          ))}
        </div>
        <div className="shrink-0 mt-2">
          <button onClick={() => handleBrowseSelect(currentDir)}
            className="w-full neu-extruded-sm bg-[#E0E5EC] text-accent hover:text-fg py-2.5 rounded-[16px] text-xs font-medium transition-all duration-300 hover:-translate-y-[1px] active:translate-y-[0.5px] active:neu-inset-sm"
          >Open This Directory</button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-0 flex-1 px-4">
      <div className="w-full max-w-lg space-y-6">
        {/* Logo */}
        <div className="text-center space-y-2">
          <div className="neu-extruded-sm w-20 h-20 rounded-[32px] flex items-center justify-center mx-auto text-3xl animate-float">
            💻
          </div>
          <h1 className="font-display font-extrabold text-xl text-fg">
            CODY<span className="text-accent">LOCAL</span>
          </h1>
          <p className="text-muted text-xs font-body">Open a project to get started</p>
        </div>

        {/* Path input */}
        <div className="space-y-2">
          <div className="flex gap-1.5">
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                value={path}
                onChange={(e) => handlePathChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && valid) handleOpen() }}
                placeholder="~/projects/my-app"
                className="w-full bg-[#E0E5EC] text-fg text-sm px-4 py-3 rounded-[16px] neu-inset-sm placeholder:text-[#A0AEC0] transition-all duration-300 focus:neu-inset-deep pr-10"
                spellCheck={false}
              />
              {/* Validation indicator */}
              {path.trim().length > 2 && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2">
                  {validating ? (
                    <span className="text-muted text-sm animate-pulse">...</span>
                  ) : valid === true ? (
                    <span className="text-accent-secondary text-sm">✓</span>
                  ) : valid === false ? (
                    <span className="text-red-400 text-sm">✕</span>
                  ) : null}
                </span>
              )}
            </div>
            <button onClick={() => setBrowsing(true)}
              className="neu-extruded-sm bg-[#E0E5EC] text-muted hover:text-fg px-4 py-3 rounded-[16px] text-sm font-medium transition-all duration-300 hover:-translate-y-[1px] active:translate-y-[0.5px] active:neu-inset-sm"
            >Browse</button>
            <button onClick={() => handleOpen()} disabled={!valid || opening}
              className="neu-extruded-sm bg-[#E0E5EC] text-accent hover:text-fg px-5 py-3 rounded-[16px] text-sm font-medium transition-all duration-300 hover:-translate-y-[1px] active:translate-y-[0.5px] active:neu-inset-sm disabled:opacity-40"
            >{opening ? "Opening..." : "Open"}</button>
          </div>
          {errors && (
            <div className="neu-inset-sm rounded-[12px] px-3 py-2 text-[11px] text-red-400 break-words">
              {errors}
            </div>
          )}
        </div>

        {/* Quick access + Recent */}
        <div className="grid grid-cols-2 gap-4">
          {/* Quick Access */}
          <div>
            <h3 className="text-[10px] font-display font-bold text-muted uppercase tracking-widest mb-2 px-1">Quick Access</h3>
            <div className="space-y-[1px]">
              {roots.map((r) => (
                <button key={r.path} onClick={() => handleBrowseOpen(r.path)}
                  className="w-full text-left px-3 py-2 rounded-[12px] text-[11px] text-muted hover:text-fg hover:neu-inset-sm transition-all duration-200 flex items-center gap-2"
                >
                  <span>📁</span>
                  <span className="truncate font-medium">{r.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Recent Workspaces */}
          <div>
            <h3 className="text-[10px] font-display font-bold text-muted uppercase tracking-widest mb-2 px-1">Recent</h3>
            <div className="space-y-[1px]">
              {recent.length === 0 && (
                <p className="text-muted/50 text-[11px] px-3">No recent workspaces</p>
              )}
              {recent.map((r) => (
                <div key={r.path} className="group flex items-center rounded-[12px] hover:neu-inset-sm transition-all duration-200">
                  <button onClick={() => { setPath(r.path); doValidate(r.path) }}
                    className="flex-1 text-left px-3 py-2 text-[11px] min-w-0"
                  >
                    <span className="text-fg font-medium truncate block">{r.label}</span>
                    <span className="text-muted/50 truncate block">{r.resolved}</span>
                  </button>
                  <button onClick={() => handleRemoveRecent(r.path)}
                    className="shrink-0 px-2 py-2 text-[10px] text-muted/30 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                  >✕</button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
