"use client"

import { OpenFile } from "@/types"
import { useState, useRef, useCallback, useEffect } from "react"
import { saveFileContent } from "@/lib/api"
import dynamic from "next/dynamic"
import type { OnMount } from "@monaco-editor/react"

// Load Monaco only on the client — it's heavy and uses browser APIs
const Editor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex-1 flex items-center justify-center bg-[#1e1e2e]">
      <span className="text-[#6c6c8a] text-xs animate-pulse">Loading editor...</span>
    </div>
  ),
})

const LANG_MAP: Record<string, string> = {
  ts: "typescript",  tsx: "typescript", js: "javascript",   jsx: "javascript",
  py: "python",      rs: "rust",        go: "go",           java: "java",
  c:  "c",           cpp: "cpp",        cs: "csharp",       rb: "ruby",
  php: "php",        swift: "swift",    kt: "kotlin",       scala: "scala",
  md: "markdown",    json: "json",      yaml: "yaml",       yml: "yaml",
  toml: "toml",      html: "html",      css: "css",         scss: "scss",
  sql: "sql",        sh: "shell",       bash: "shell",      xml: "xml",
  ini: "ini",        env: "ini",        lock: "plaintext",  txt: "plaintext",
}

function detectLang(filename: string): string {
  const base = filename.toLowerCase()
  if (base === "dockerfile") return "dockerfile"
  if (base === "makefile") return "makefile"
  if (base === ".env" || base === ".env.example") return "ini"
  const ext = filename.split(".").pop()?.toLowerCase() || ""
  return LANG_MAP[ext] || "plaintext"
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

interface Props {
  file: OpenFile | null
  workspace?: string
}

export default function CodeEditor({ file, workspace }: Props) {
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [lineCount, setLineCount] = useState(0)
  const editorValueRef = useRef<string>("")

  useEffect(() => {
    if (file) {
      editorValueRef.current = file.content
      setLineCount(file.content.split("\n").length)
    }
  }, [file])

  const handleSave = useCallback(async () => {
    if (!file || !workspace) return
    setSaveStatus("saving")
    const r = await saveFileContent(file.path, editorValueRef.current, workspace)
    setSaveStatus(r.ok ? "saved" : "error")
    setTimeout(() => setSaveStatus("idle"), 2000)
  }, [file, workspace])

  const handleMount: OnMount = useCallback((editor, monaco) => {
    // Ctrl+S / Cmd+S → save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      editorValueRef.current = editor.getValue()
      handleSave()
    })

    // Keep ref updated on every change
    editor.onDidChangeModelContent(() => {
      editorValueRef.current = editor.getValue()
      setLineCount(editor.getModel()?.getLineCount() ?? 0)
    })
  }, [handleSave])

  if (!file) {
    return (
      <div className="flex-1 flex items-center justify-center h-full bg-[#1e1e2e] rounded-[inherit]">
        <div className="text-center space-y-3 animate-fade-in">
          <div className="w-14 h-14 rounded-2xl bg-[#2a2a3e] flex items-center justify-center mx-auto text-2xl">
            💻
          </div>
          <p className="text-[#6c6c8a] text-sm">Select a file to view</p>
          <p className="text-[#4a4a6a] text-xs">or ask the AI to create one</p>
        </div>
      </div>
    )
  }

  const lang = detectLang(file.name)
  const bytes = new TextEncoder().encode(editorValueRef.current || file.content).length

  return (
    <div className="flex flex-col h-full overflow-hidden rounded-[inherit]">
      {/* Tab bar — dark to match Monaco */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-[#181825] border-b border-[#2a2a40]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#f38ba8] opacity-80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#fab387] opacity-80" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#a6e3a1] opacity-80" />
          </div>
          <div className="h-4 w-px bg-[#2a2a40]" />
          <span className="text-[#cdd6f4] text-xs font-mono font-medium">{file.name}</span>
          <span className="text-[10px] text-[#6c7086] uppercase tracking-wider">{lang}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[#585b70]">{lineCount} lines · {formatBytes(bytes)}</span>
          {saveStatus === "saving" && (
            <span className="text-[10px] text-[#fab387] animate-pulse">Saving…</span>
          )}
          {saveStatus === "saved" && (
            <span className="text-[10px] text-[#a6e3a1]">✓ Saved</span>
          )}
          {saveStatus === "error" && (
            <span className="text-[10px] text-[#f38ba8]">Save failed</span>
          )}
          <button
            onClick={handleSave}
            disabled={saveStatus === "saving" || !workspace}
            className="px-3 py-1 rounded-lg text-[10px] font-medium bg-[#2a2a40] text-[#cdd6f4] hover:bg-[#313244] hover:text-white transition-all duration-150 disabled:opacity-40"
          >
            Save
          </button>
        </div>
      </div>

      {/* Monaco */}
      <div className="flex-1 overflow-hidden">
        <Editor
          height="100%"
          language={lang}
          defaultValue={file.content}
          key={file.path}
          theme="vs-dark"
          onMount={handleMount}
          options={{
            fontSize: 13,
            lineHeight: 22,
            fontFamily: "'JetBrains Mono', 'Cascadia Code', 'Fira Code', Menlo, monospace",
            fontLigatures: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            insertSpaces: true,
            renderLineHighlight: "line",
            cursorBlinking: "smooth",
            cursorSmoothCaretAnimation: "on",
            smoothScrolling: true,
            padding: { top: 16, bottom: 32 },
            renderWhitespace: "selection",
            bracketPairColorization: { enabled: true },
            guides: { indentation: true, bracketPairs: true },
            scrollbar: { verticalScrollbarSize: 5, horizontalScrollbarSize: 5 },
            overviewRulerBorder: false,
            hideCursorInOverviewRuler: true,
            lineNumbers: "on",
            glyphMargin: false,
            folding: true,
            suggest: { showWords: false },
          }}
        />
      </div>
    </div>
  )
}
