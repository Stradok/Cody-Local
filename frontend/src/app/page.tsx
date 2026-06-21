"use client"

import { useState, useCallback, useEffect } from "react"
import { OpenFile } from "@/types"
import { readFileContent } from "@/lib/api"
import ModelSelector from "@/components/ModelSelector"
import WorkspacePicker from "@/components/WorkspacePicker"
import FileBrowser from "@/components/FileBrowser"
import CodeEditor from "@/components/CodeEditor"
import ChatPanel from "@/components/ChatPanel"
import GitHubPanel from "@/components/GitHubPanel"
import ToastStack, { ToastItem } from "@/components/Toast"

export default function Home() {
  const [model, setModel] = useState("")
  const [workspace, setWorkspace] = useState("")
  const [openFile, setOpenFile] = useState<OpenFile | null>(null)
  const [leftPanel, setLeftPanel] = useState<"files" | "github">("files")
  const [showLeft, setShowLeft] = useState(true)
  const [showChat, setShowChat] = useState(true)
  const [mobileView, setMobileView] = useState<"files" | "code" | "chat">("code")
  const [isMobile, setIsMobile] = useState(false)
  const [fileBrowserKey, setFileBrowserKey] = useState(0)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 900)
    check()
    window.addEventListener("resize", check)
    return () => window.removeEventListener("resize", check)
  }, [])

  const addToast = useCallback((message: string, type: ToastItem["type"] = "info") => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    setToasts((prev) => [...prev.slice(-4), { id, message, type }])
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const handleWorkspaceOpen = useCallback((path: string) => {
    setWorkspace(path)
    setShowLeft(true)
    setShowChat(true)
  }, [])

  const handleChangeWorkspace = useCallback(() => {
    setWorkspace("")
    setOpenFile(null)
  }, [])

  const handleFileSelect = useCallback(async (filePath: string, fileName: string) => {
    const data = await readFileContent(filePath)
    if (!data.error) {
      setOpenFile({ path: data.path, name: fileName, content: data.content })
      if (isMobile) setMobileView("code")
    }
  }, [isMobile])

  const onFileWritten = useCallback(async (path: string, _ws: string) => {
    // Refresh file browser
    setFileBrowserKey((k) => k + 1)
    // Reload the open file if it's the one that was written
    if (openFile) {
      const matches = openFile.path === path || openFile.path.endsWith(`/${path}`) || path.endsWith(openFile.name)
      if (matches) {
        const data = await readFileContent(openFile.path)
        if (!data.error) setOpenFile((f) => f ? { ...f, content: data.content } : f)
      }
    }
  }, [openFile])

  // ── No workspace: show picker ──────────────────────────────────────────────
  if (!workspace) {
    return (
      <div className="h-screen flex flex-col bg-[#E0E5EC] font-body">
        <header className="shrink-0 px-6 py-4">
          <div className="neu-extruded rounded-[32px] px-6 py-3 flex items-center justify-between max-w-2xl mx-auto">
            <h1 className="font-display font-extrabold text-base tracking-tight text-fg">
              CODY<span className="text-accent">LOCAL</span>
            </h1>
            <ModelSelector selected={model} onSelect={setModel} />
          </div>
        </header>
        <WorkspacePicker onWorkspaceOpen={handleWorkspaceOpen} />
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
      </div>
    )
  }

  // ── Mobile layout ──────────────────────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="h-screen flex flex-col bg-[#E0E5EC] font-body">
        <header className="shrink-0 px-4 py-3">
          <div className="neu-extruded rounded-[32px] px-5 py-3 flex items-center justify-between">
            <h1 className="font-display font-extrabold text-sm tracking-tight text-fg">
              CODY<span className="text-accent">LOCAL</span>
            </h1>
            <ModelSelector selected={model} onSelect={setModel} />
          </div>
        </header>
        <div className="flex-1 overflow-auto px-4 pb-4">
          {mobileView === "files" && (
            <div className="neu-inset-deep rounded-[32px] p-3 h-full overflow-auto">
              <div className="flex gap-2 mb-3">
                {(["files", "github"] as const).map((p) => (
                  <button key={p} onClick={() => setLeftPanel(p)}
                    className={`flex-1 py-2 rounded-[16px] text-xs font-medium transition-all duration-300 ${
                      leftPanel === p ? "neu-inset-sm text-accent" : "neu-extruded-sm text-muted hover:text-fg"
                    }`}
                  >{p === "files" ? "Files" : "GitHub"}</button>
                ))}
              </div>
              {leftPanel === "files"
                ? <FileBrowser onFileSelect={handleFileSelect} workspace={workspace} onChangeWorkspace={handleChangeWorkspace} refreshKey={fileBrowserKey} />
                : <GitHubPanel workspace={workspace} onFileSelect={handleFileSelect} />}
            </div>
          )}
          {mobileView === "code" && (
            <div className="neu-inset-deep rounded-[32px] overflow-hidden h-full">
              <CodeEditor file={openFile} workspace={workspace} />
            </div>
          )}
          {mobileView === "chat" && (
            <div className="neu-inset-deep rounded-[32px] p-3 h-full overflow-auto">
              <ChatPanel model={model} workspace={workspace} onFileWritten={onFileWritten} onToast={addToast} />
            </div>
          )}
        </div>
        <nav className="shrink-0 px-4 pb-4">
          <div className="neu-extruded rounded-[32px] px-6 py-3 flex justify-around">
            {(["files", "code", "chat"] as const).map((v) => (
              <button key={v} onClick={() => setMobileView(v)}
                className={`px-5 py-2 rounded-[16px] text-xs font-medium transition-all duration-300 ${
                  mobileView === v ? "neu-inset-sm text-accent" : "neu-extruded-sm text-muted hover:text-fg"
                }`}
              >
                {v === "files" ? "Files" : v === "code" ? "Code" : "Chat"}
              </button>
            ))}
          </div>
        </nav>
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
      </div>
    )
  }

  // ── Desktop layout ─────────────────────────────────────────────────────────
  return (
    <div className="h-screen flex flex-col bg-[#E0E5EC] font-body">
      {/* Top bar */}
      <header className="shrink-0 px-6 py-4">
        <div className="neu-extruded rounded-[32px] px-6 py-3 flex items-center justify-between max-w-[1600px] mx-auto">
          <div className="flex items-center gap-4">
            <h1 className="font-display font-extrabold text-base tracking-tight text-fg">
              CODY<span className="text-accent">LOCAL</span>
            </h1>
            <div className="h-5 w-px bg-muted/20" />
            <div className="flex items-center gap-1.5">
              <button onClick={() => setShowLeft(!showLeft)}
                className={`px-3 py-1.5 rounded-[14px] text-[11px] font-medium transition-all duration-200 ${
                  showLeft ? "neu-inset-sm text-accent" : "neu-extruded-sm text-muted hover:text-fg"
                }`}
              >
                {leftPanel === "files" ? "Files" : "GitHub"} {showLeft ? "▾" : "▸"}
              </button>
              {showLeft && (
                <button onClick={() => setLeftPanel(leftPanel === "files" ? "github" : "files")}
                  className="px-3 py-1.5 rounded-[14px] text-[11px] font-medium neu-extruded-sm text-muted hover:text-fg transition-all duration-200"
                >
                  {leftPanel === "files" ? "GitHub" : "Files"}
                </button>
              )}
              <button
                onClick={() => handleWorkspaceOpen(workspace)}
                className="px-3 py-1.5 rounded-[14px] text-[11px] font-medium neu-extruded-sm text-muted hover:text-fg transition-all"
                title="Change workspace"
              >
                Open…
              </button>
            </div>
            <div className="h-5 w-px bg-muted/20" />
            <span className="text-[11px] text-muted/70 font-medium truncate max-w-[200px]">
              {workspace.split("/").pop()}
            </span>
          </div>
          <ModelSelector selected={model} onSelect={setModel} />
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex gap-4 px-6 pb-4 min-h-0 max-w-[1600px] mx-auto w-full">

        {/* Left panel */}
        {showLeft && (
          <div className="neu-inset-deep rounded-[32px] p-3 w-60 shrink-0 overflow-hidden flex flex-col">
            <div className="px-2 pb-2 text-[9px] font-display font-bold text-muted/60 uppercase tracking-widest border-b border-muted/10 mb-2">
              {leftPanel === "files" ? "Explorer" : "GitHub"}
            </div>
            {leftPanel === "files"
              ? <FileBrowser onFileSelect={handleFileSelect} workspace={workspace} onChangeWorkspace={handleChangeWorkspace} refreshKey={fileBrowserKey} />
              : <GitHubPanel workspace={workspace} onFileSelect={handleFileSelect} />
            }
          </div>
        )}

        {/* Center: Editor */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="neu-inset-deep rounded-[32px] flex-1 overflow-hidden flex flex-col">
            <CodeEditor file={openFile} workspace={workspace} />
          </div>
        </div>

        {/* Right: Chat */}
        {showChat ? (
          <div className="neu-inset-deep rounded-[32px] p-3 w-[320px] shrink-0 flex flex-col">
            <div className="flex items-center justify-between px-1 pb-2 border-b border-muted/10 mb-2">
              <span className="text-[9px] font-display font-bold text-muted/60 uppercase tracking-widest">Assistant</span>
              <button onClick={() => setShowChat(false)}
                className="neu-extruded-sm w-6 h-6 rounded-full flex items-center justify-center text-[9px] text-muted hover:text-fg transition-all duration-200"
              >✕</button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ChatPanel model={model} workspace={workspace} onFileWritten={onFileWritten} onToast={addToast} />
            </div>
          </div>
        ) : (
          <button onClick={() => setShowChat(true)}
            className="self-end mb-6 neu-extruded-sm w-11 h-11 rounded-full flex items-center justify-center text-sm text-accent hover:neu-extruded-hover transition-all duration-200 hover:-translate-y-[1px]"
            title="Open Chat"
          >
            💬
          </button>
        )}
      </div>

      {/* Status bar */}
      <footer className="shrink-0 px-6 pb-4">
        <div className="neu-inset-sm rounded-[32px] px-5 py-2 flex items-center justify-between text-[10px] text-muted max-w-[1600px] mx-auto">
          <div className="flex items-center gap-3">
            <span className="font-medium text-fg/50">{workspace.split("/").pop()}</span>
            {openFile && (
              <>
                <span className="text-muted/30">/</span>
                <span className="text-accent font-mono font-medium">{openFile.name}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-muted/60">Ollama</span>
            <span className="font-medium text-fg/60">{model}</span>
          </div>
        </div>
      </footer>

      {/* Toast notifications */}
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
