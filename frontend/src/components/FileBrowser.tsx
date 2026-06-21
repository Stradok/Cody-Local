"use client"

import { useState, useEffect } from "react"
import { FileEntry } from "@/types"
import { exploreDirectory } from "@/lib/api"

interface Props {
  workspace: string
  onFileSelect: (path: string, name: string) => void
  onChangeWorkspace?: () => void
  refreshKey?: number
}

export default function FileBrowser({ workspace, onFileSelect, onChangeWorkspace, refreshKey }: Props) {
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    setLoading(true)
    setExpanded(new Set())
    exploreDirectory(workspace).then((data) => {
      if (data.error) setError(data.error)
      else setEntries(data.entries)
      setLoading(false)
    })
  }, [workspace, refreshKey])

  async function handleClick(entry: FileEntry) {
    if (entry.type === "directory") {
      if (expanded.has(entry.path)) {
        setExpanded((p) => { const n = new Set(p); n.delete(entry.path); return n })
      } else {
        setExpanded((p) => new Set(p).add(entry.path))
      }
    } else {
      onFileSelect(entry.path, entry.name)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Workspace header with change button */}
      <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-muted/10">
        <span className="text-[10px] text-muted truncate font-medium">
          {workspace.split("/").pop()}
        </span>
        {onChangeWorkspace && (
          <button onClick={onChangeWorkspace}
            className="text-[10px] text-accent hover:text-accent-light neu-extruded-sm px-2.5 py-1 rounded-[10px] transition-all"
          >Open Folder...</button>
        )}
      </div>

      {/* File tree */}
      <div className="flex-1 overflow-auto space-y-[1px] pr-1">
        {loading && <p className="text-muted text-[11px] p-2 animate-pulse">Loading...</p>}
        {error && <p className="text-red-400 text-[11px] p-2">{error}</p>}
        {!loading && !error && entries.length === 0 && (
          <p className="text-muted text-[11px] p-2">Empty directory</p>
        )}
        {!loading && entries.map((e) => (
          <Row key={e.path} entry={e} depth={0} expanded={expanded} onClick={handleClick} workspace={workspace} />
        ))}
      </div>
    </div>
  )
}

function Row({ entry, depth, expanded, onClick, workspace }: {
  entry: FileEntry; depth: number; expanded: Set<string>; onClick: (e: FileEntry) => void; workspace: string
}) {
  const [children, setChildren] = useState<FileEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const isExpanded = expanded.has(entry.path)

  async function handleClick() {
    if (entry.type === "directory" && isExpanded && children) {
      setChildren(null)
    }
    if (entry.type === "directory" && !isExpanded && !children) {
      setLoading(true)
      const data = await exploreDirectory(entry.path)
      if (!data.error) setChildren(data.entries)
      setLoading(false)
    }
    onClick(entry)
  }

  return (
    <div>
      <button onClick={handleClick}
        className="w-full flex items-center gap-2 px-3 py-1.5 rounded-[12px] text-[11px] text-left transition-all duration-200 hover:neu-inset-sm hover:bg-transparent focus-visible:neu-inset-sm"
        style={{ paddingLeft: `${12 + depth * 18}px` }}
      >
        <span className="text-xs shrink-0">
          {entry.type === "directory" ? (isExpanded ? "📂" : "📁") : "📄"}
        </span>
        <span className={`truncate ${entry.type === "directory" ? "font-medium text-fg" : "text-muted"}`}>
          {entry.name}
        </span>
        {loading && <span className="text-muted animate-pulse">...</span>}
      </button>
      {isExpanded && children?.map((c) => (
        <Row key={c.path} entry={c} depth={depth + 1} expanded={expanded} onClick={onClick} workspace={workspace} />
      ))}
    </div>
  )
}
