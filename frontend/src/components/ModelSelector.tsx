"use client"

import { useEffect, useState } from "react"
import { fetchModels, checkHealth } from "@/lib/api"
import ModelPicker from "./ModelPicker"

const EMBEDDING_PREFIXES = [
  "nomic-embed-text",
  "mxbai-embed-large",
  "all-minilm",
  "snowflake-arctic-embed",
  "bge-m3",
  "bge-large",
  "bge-base",
  "text-embedding-ada",
]

interface Props {
  selected: string
  onSelect: (model: string) => void
  onToast?: (msg: string, type: "success" | "error" | "info") => void
}

export default function ModelSelector({ selected, onSelect, onToast }: Props) {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [online, setOnline] = useState(false)
  const [showPicker, setShowPicker] = useState(false)

  useEffect(() => {
    checkHealth().then((h) => setOnline(h.ok))
    loadModels()
  }, [])

  async function loadModels() {
    setLoading(true)
    try {
      const r = await fetchModels()
      if (r.error) { setError(r.error); setModels([]) }
      else {
        const chatModels = r.models.filter((m: string) => !EMBEDDING_PREFIXES.some((p) => m.split(":")[0] === p))
        setModels(chatModels)
        if (chatModels.length > 0 && (!selected || !chatModels.includes(selected))) {
          onSelect(chatModels[0])
        }
        setError(null)
      }
    } catch {
      setError("Failed")
    } finally {
      setLoading(false)
    }
  }

  function handleInstalled(modelId: string) {
    setShowPicker(false)
    onSelect(modelId)
    loadModels()
  }

  const noModels = !loading && !error && models.length === 0

  return (
    <>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full transition-colors duration-300 ${online ? "bg-accent-secondary shadow-[0_0_6px_rgba(56,178,172,0.4)]" : "bg-red-400"}`} />

        {noModels ? (
          <button
            onClick={() => setShowPicker(true)}
            className="neu-extruded-sm px-3 py-2 rounded-[16px] text-xs font-medium text-accent hover:text-fg transition-all animate-pulse"
          >
            Install a model…
          </button>
        ) : (
          <>
            <select
              value={selected}
              onChange={(e) => onSelect(e.target.value)}
              className="neu-inset-sm bg-[#E0E5EC] text-fg text-xs font-medium px-3 py-2 rounded-[16px] min-w-[120px] max-w-[180px] appearance-none cursor-pointer transition-all duration-300 hover:neu-inset focus:neu-inset-deep"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='%236B7280'%3E%3Cpath d='M0 0l5 6 5-6z'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 12px center",
                paddingRight: "32px",
              }}
            >
              {loading && <option value="" className="bg-[#E0E5EC]">Loading...</option>}
              {!loading && error && <option value="" className="bg-[#E0E5EC]">Offline</option>}
              {models.map((m) => (
                <option key={m} value={m} className="bg-[#E0E5EC]">{m}</option>
              ))}
            </select>
            <button
              onClick={() => setShowPicker(true)}
              title="Install more models"
              className="neu-extruded-sm w-7 h-7 rounded-full flex items-center justify-center text-[11px] text-muted hover:text-accent transition-all"
            >+</button>
          </>
        )}
      </div>

      {showPicker && (
        <ModelPicker
          onInstalled={handleInstalled}
          onClose={() => setShowPicker(false)}
          onToast={onToast}
        />
      )}
    </>
  )
}
