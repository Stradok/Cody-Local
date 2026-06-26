import { FileEntry, LibraryBook, LibrarySource } from "@/types"

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

export async function checkHealth(): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) })
    return { ok: res.ok }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { ok: false, error: msg }
  }
}

export async function fetchModels(): Promise<{ models: string[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/models`)
    if (!res.ok) {
      const text = await res.text()
      return { models: [], error: `Backend returned ${res.status}: ${text.slice(0, 200)}` }
    }
    const data = await res.json()
    return { models: data.models.map((m: { name: string }) => m.name) }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { models: [], error: `Cannot reach backend at ${API_BASE} — ${msg}` }
  }
}

export async function chat(
  model: string,
  messages: { role: string; content: string }[],
  workspace: string,
  onChunk: (chunk: string) => void,
  onToolCall: (name: string, args: string) => void,
  onToolResult: (name: string, result: string) => void,
  onDone: () => void,
  onError?: (message: string) => void,
  mode = "chat",
  onSources?: (sources: LibrarySource[]) => void,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, workspace, mode }),
    })
  } catch {
    onError?.(`Cannot reach backend at ${API_BASE}`)
    onDone()
    return
  }

  const reader = res.body?.getReader()
  if (!reader) { onDone(); return }

  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        let evt: Record<string, string>
        try { evt = JSON.parse(line.slice(6)) } catch { continue }

        switch (evt.type) {
          case "chunk":      onChunk(evt.content || ""); break
          case "tool_call":  onToolCall(evt.name, evt.arguments); break
          case "tool_result": onToolResult(evt.name, evt.result); break
          case "sources":    onSources?.(evt.results as unknown as LibrarySource[]); break
          case "error":      onError?.(evt.content || evt.message || "Unknown error"); break
          case "done":       onDone(); return
        }
      }
    }
  } finally {
    reader.cancel()
    onDone()
  }
}

export async function pullModel(
  model: string,
  onProgress: (status: string, percent?: number) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/api/models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    })
  } catch {
    onError("Cannot reach backend")
    return
  }

  const reader = res.body?.getReader()
  if (!reader) { onError("No response body"); return }
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n\n")
      buffer = lines.pop() || ""
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        let evt: Record<string, unknown>
        try { evt = JSON.parse(line.slice(6)) } catch { continue }
        if (evt.status === "error") { onError(String(evt.error || "Pull failed")); return }
        if (evt.done === true) { onDone(); return }
        const pct = evt.total && evt.completed
          ? Math.round((Number(evt.completed) / Number(evt.total)) * 100)
          : undefined
        onProgress(String(evt.status || ""), pct)
      }
    }
  } finally {
    reader.cancel()
  }
}

export async function setWorkspace(path: string): Promise<{ path: string; tree: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    if (!res.ok) {
      const text = await res.text()
      return { path, tree: "", error: text.slice(0, 300) }
    }
    return res.json()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { path, tree: "", error: `Cannot reach backend: ${msg}` }
  }
}

export async function exploreDirectory(path: string): Promise<{ path: string; entries: FileEntry[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/explore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    if (!res.ok) {
      const text = await res.text()
      return { path, entries: [], error: text.slice(0, 300) }
    }
    return res.json()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { path, entries: [], error: `Cannot reach backend: ${msg}` }
  }
}

export async function validateWorkspace(path: string): Promise<{ valid: boolean; path?: string; resolved?: string; warnings?: string[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    return res.json()
  } catch (e: unknown) {
    return { valid: false, error: String(e) }
  }
}

export async function browseRoots(): Promise<{ roots: { path: string; label: string; type: string }[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/browse-roots`)
    if (!res.ok) return { roots: [], error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) {
    return { roots: [], error: String(e) }
  }
}

export async function listRecentWorkspaces(): Promise<{ workspaces: { path: string; resolved: string; label: string; last_opened: string }[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/recent`)
    if (!res.ok) return { workspaces: [], error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) {
    return { workspaces: [], error: String(e) }
  }
}

export async function removeRecentWorkspace(path: string): Promise<{ error?: string }> {
  try {
    await fetch(`${API_BASE}/api/workspace/recent/remove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    return {}
  } catch (e: unknown) {
    return { error: String(e) }
  }
}

export async function searchFiles(workspace: string, query: string): Promise<{ results: { name: string; path: string; relative: string }[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace, query }),
    })
    if (!res.ok) {
      const text = await res.text()
      return { results: [], error: text.slice(0, 300) }
    }
    return res.json()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { results: [], error: `Cannot reach backend: ${msg}` }
  }
}

export async function githubSetToken(token: string): Promise<{ error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/token`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return {}
  } catch (e: unknown) { return { error: String(e) } }
}

export async function githubGetUser(): Promise<{ user?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/user`)
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) { return { error: String(e) } }
}

export async function githubListRepos(): Promise<{ repos?: import("@/types").GitHubRepo[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/repos`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ per_page: 30 }),
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) { return { error: String(e) } }
}

export async function githubListIssues(repo: string, state = "open"): Promise<{ issues?: import("@/types").GitHubIssue[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/issues`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo, state }),
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) { return { error: String(e) } }
}

export async function githubListPulls(repo: string, state = "open"): Promise<{ pulls?: import("@/types").GitHubPR[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/pulls`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo, state }),
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) { return { error: String(e) } }
}

export async function githubCloneRepo(url: string, targetDir: string, workspace: string): Promise<{ result?: string; path?: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/github/clone`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, target_dir: targetDir, workspace }),
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) { return { error: String(e) } }
}

export async function readFileContent(path: string): Promise<{ path: string; content: string; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/workspace/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    })
    if (!res.ok) {
      const text = await res.text()
      return { path, content: "", error: text.slice(0, 300) }
    }
    return res.json()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    return { path, content: "", error: `Cannot reach backend: ${msg}` }
  }
}

export async function saveFileContent(
  path: string,
  content: string,
  workspace: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/tool`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool: "write_file", args: { path, content }, workspace }),
    })
    if (!res.ok) {
      const text = await res.text()
      return { ok: false, error: text.slice(0, 300) }
    }
    return { ok: true }
  } catch (e: unknown) {
    return { ok: false, error: String(e) }
  }
}

export interface AgentHandlers {
  onPlan?: (steps: string[], stepTypes?: string[]) => void
  onStepStart?: (step: number, description: string, agent?: string) => void
  onStepDone?: (step: number, description: string) => void
  onToolCall?: (name: string, args: string) => void
  onToolResult?: (name: string, result: string) => void
  onChunk?: (content: string) => void
  onStatus?: (message: string) => void
  onWarning?: (message: string) => void
  onFileWritten?: (path: string, workspace: string) => void
  onError?: (message: string) => void
  onDone?: () => void
}

export async function runAgent(
  model: string,
  messages: { role: string; content: string }[],
  workspace: string,
  sessionId: string,
  handlers: AgentHandlers,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/agent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, messages, workspace, session_id: sessionId }),
  })

  if (!res.ok) {
    const text = await res.text()
    handlers.onError?.(`Agent request failed: ${res.status} — ${text.slice(0, 200)}`)
    return
  }

  const reader = res.body?.getReader()
  if (!reader) { handlers.onError?.("No response body"); return }

  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        let evt: Record<string, unknown>
        try {
          evt = JSON.parse(line.slice(6))
        } catch {
          continue
        }
        switch (evt.type) {
          case "plan":
            handlers.onPlan?.(evt.steps as string[], evt.step_types as string[] | undefined)
            break
          case "step_start":
            handlers.onStepStart?.(evt.step as number, evt.description as string, evt.agent as string | undefined)
            break
          case "step_done":
            handlers.onStepDone?.(evt.step as number, evt.description as string)
            break
          case "tool_call":
            handlers.onToolCall?.(evt.name as string, evt.arguments as string)
            break
          case "tool_result":
            handlers.onToolResult?.(evt.name as string, evt.result as string)
            break
          case "chunk":
            handlers.onChunk?.(evt.content as string)
            break
          case "status":
            handlers.onStatus?.(evt.message as string)
            break
          case "warning":
            handlers.onWarning?.(evt.message as string)
            break
          case "file_written":
            handlers.onFileWritten?.(evt.path as string, evt.workspace as string)
            break
          case "error":
            handlers.onError?.(evt.message as string)
            break
          case "done":
            handlers.onDone?.()
            return
        }
      }
    }
  } finally {
    reader.cancel()
  }
}

export async function listSessions(workspace = ""): Promise<{ sessions: Array<{ session_id: string; workspace: string; model: string; updated_at: string }>; error?: string }> {
  try {
    const url = workspace
      ? `${API_BASE}/api/sessions?workspace=${encodeURIComponent(workspace)}`
      : `${API_BASE}/api/sessions`
    const res = await fetch(url)
    if (!res.ok) return { sessions: [], error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) {
    return { sessions: [], error: String(e) }
  }
}

export async function getSessionMessages(sessionId: string): Promise<{ messages: Array<{ role: string; content: string }>; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(sessionId)}/messages`)
    if (!res.ok) return { messages: [], error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) {
    return { messages: [], error: String(e) }
  }
}

// ── Library ───────────────────────────────────────────────────────────────────

export async function libraryListBooks(): Promise<{ books: LibraryBook[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/library/books`)
    if (!res.ok) return { books: [], error: (await res.text()).slice(0, 200) }
    return res.json()
  } catch (e: unknown) {
    return { books: [], error: String(e) }
  }
}

export async function libraryIngestBook(
  path: string,
  title: string,
  category: string,
  embedModel = "nomic-embed-text",
): Promise<{ book_id?: string; title?: string; chunk_count?: number; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/library/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, title, category, embed_model: embedModel }),
    })
    if (!res.ok) {
      const text = await res.text()
      let detail = `Server error ${res.status}`
      try { detail = (JSON.parse(text) as { detail?: string }).detail || detail } catch { detail = text.slice(0, 200) || detail }
      return { error: detail }
    }
    return res.json()
  } catch (e: unknown) {
    return { error: String(e) }
  }
}

export async function libraryDeleteBook(bookId: string): Promise<{ error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/library/books/${encodeURIComponent(bookId)}`, {
      method: "DELETE",
    })
    if (!res.ok) return { error: (await res.text()).slice(0, 200) }
    return {}
  } catch (e: unknown) {
    return { error: String(e) }
  }
}

export async function librarySearch(
  query: string,
  nResults = 5,
  category = "",
): Promise<{ results: LibrarySource[]; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/library/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, n_results: nResults, category }),
    })
    if (!res.ok) {
      const text = await res.text()
      let detail = `Server error ${res.status}`
      try { detail = (JSON.parse(text) as { detail?: string }).detail || detail } catch { detail = text.slice(0, 200) || detail }
      return { results: [], error: detail }
    }
    return res.json()
  } catch (e: unknown) {
    return { results: [], error: String(e) }
  }
}
