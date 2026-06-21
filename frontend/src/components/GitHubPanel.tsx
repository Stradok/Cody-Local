"use client"

import { useState, useEffect } from "react"
import { GitHubRepo, GitHubIssue, GitHubPR } from "@/types"
import {
  githubSetToken,
  githubGetUser,
  githubListRepos,
  githubListIssues,
  githubListPulls,
  githubCloneRepo,
} from "@/lib/api"

interface Props {
  workspace: string
  onFileSelect: (path: string, name: string) => void
}

export default function GitHubPanel({ workspace, onFileSelect }: Props) {
  const [token, setToken] = useState("")
  const [tokenSet, setTokenSet] = useState(false)
  const [user, setUser] = useState("")
  const [repos, setRepos] = useState<GitHubRepo[]>([])
  const [selected, setSelected] = useState("")
  const [issues, setIssues] = useState<GitHubIssue[]>([])
  const [pulls, setPulls] = useState<GitHubPR[]>([])
  const [tab, setTab] = useState<"repos" | "issues" | "pulls">("repos")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!tokenSet) return
    githubGetUser().then((d) => { if (d.user) setUser(d.user) })
    loadRepos()
  }, [tokenSet])

  async function handleSetToken() {
    if (!token.trim()) return
    const res = await githubSetToken(token.trim())
    if (res.error) { setError(res.error); return }
    setTokenSet(true); setError(null)
  }

  async function loadRepos() {
    setLoading(true)
    const data = await githubListRepos()
    if (data.error) setError(data.error)
    else if (data.repos) setRepos(data.repos)
    setLoading(false)
  }

  async function selectRepo(fullName: string) {
    setSelected(fullName); setTab("issues"); setLoading(true)
    const [i, p] = await Promise.all([githubListIssues(fullName, "open"), githubListPulls(fullName, "open")])
    if (i.issues) setIssues(i.issues)
    if (p.pulls) setPulls(p.pulls)
    setLoading(false)
  }

  async function handleClone(repo: GitHubRepo) {
    const data = await githubCloneRepo(repo.clone_url, repo.name, workspace)
    if (data.error) setError(data.error)
    else setError(null)
  }

  if (!tokenSet) {
    return (
      <div className="flex flex-col h-full">
        <div className="space-y-3 p-1">
          <p className="text-xs text-muted">Enter a GitHub personal access token:</p>
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSetToken()}
            placeholder="ghp_..."
            className="w-full bg-[#E0E5EC] text-fg text-[11px] px-3 py-2.5 rounded-[16px] neu-inset-sm placeholder:text-[#A0AEC0] transition-all duration-300 focus:neu-inset-deep"
          />
          <button onClick={handleSetToken}
            className="w-full neu-extruded-sm bg-[#E0E5EC] text-accent hover:text-fg py-2.5 rounded-[16px] text-xs font-medium transition-all duration-300 hover:-translate-y-[1px] hover:neu-extruded-hover active:translate-y-[0.5px] active:neu-inset-sm"
          >Connect</button>
          {error && <p className="text-red-400 text-[11px]">{error}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between mb-2 px-1">
        <span className="text-[11px] text-muted truncate font-medium">{user || "GitHub"}</span>
        <button onClick={() => { setTokenSet(false); setToken(""); setRepos([]); setSelected("") }}
          className="neu-extruded-sm text-muted hover:text-red-400 px-3 py-1 rounded-[12px] text-[10px] transition-all"
        >Disconnect</button>
      </div>

      <div className="flex gap-1 mb-2">
        {(["repos", "issues", "pulls"] as const).map((t) => (
          <button key={t} onClick={() => { if (t === "repos") { setSelected(""); loadRepos() }; setTab(t) }}
            disabled={t !== "repos" && !selected}
            className={`flex-1 py-1.5 rounded-[12px] text-[10px] font-medium transition-all duration-300 disabled:opacity-40 ${
              tab === t ? "neu-inset-sm text-accent" : "neu-extruded-sm text-muted hover:text-fg"
            }`}
          >{t === "repos" ? "Repos" : t === "issues" ? `Issues (${issues.length})` : `PRs (${pulls.length})`}</button>
        ))}
      </div>

      <div className="flex-1 overflow-auto space-y-[2px] pr-1">
        {loading && <p className="text-muted text-[11px] p-2 animate-pulse">Loading...</p>}
        {error && <p className="text-red-400 text-[11px] p-2">{error}</p>}

        {tab === "repos" && repos.map((r) => (
          <button key={r.full_name} onClick={() => selectRepo(r.full_name)}
            className="w-full text-left px-3 py-2 rounded-[12px] hover:neu-inset-sm transition-all duration-200"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-fg truncate">{r.name}</span>
              <div className="flex items-center gap-2 text-[10px] text-muted shrink-0 ml-2">
                <span>⭐{r.stars}</span>
                <span>🍴{r.forks}</span>
              </div>
            </div>
            <div className="flex items-center justify-between mt-0.5">
              <span className="text-[10px] text-muted">{r.language || ""}</span>
              <button onClick={(e) => { e.stopPropagation(); handleClone(r) }}
                className="text-[10px] text-accent hover:text-accent-light"
              >Clone</button>
            </div>
          </button>
        ))}

        {tab === "issues" && issues.length === 0 && !loading && (
          <p className="text-muted text-[11px] p-3">No open issues</p>
        )}
        {tab === "issues" && issues.map((i) => (
          <a key={i.number} href={i.url} target="_blank" rel="noreferrer"
            className="block px-3 py-2 rounded-[12px] hover:neu-inset-sm transition-all duration-200"
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-accent-secondary font-medium">#{i.number}</span>
              <span className="text-xs text-fg truncate">{i.title}</span>
            </div>
            <span className="text-[10px] text-muted">{i.user} · {i.comments} comments</span>
          </a>
        ))}

        {tab === "pulls" && pulls.length === 0 && !loading && (
          <p className="text-muted text-[11px] p-3">No open PRs</p>
        )}
        {tab === "pulls" && pulls.map((p) => (
          <a key={p.number} href={p.url} target="_blank" rel="noreferrer"
            className="block px-3 py-2 rounded-[12px] hover:neu-inset-sm transition-all duration-200"
          >
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-yellow-600 font-medium">#{p.number}</span>
              <span className="text-xs text-fg truncate">{p.title}</span>
            </div>
            <span className="text-[10px] text-muted">{p.user} · {p.head} → {p.base}</span>
          </a>
        ))}
      </div>
    </div>
  )
}
