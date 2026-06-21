"use client"

import { useEffect, useState } from "react"
import { fetchModels, checkHealth } from "@/lib/api"

interface Props {
  selected: string
  onSelect: (model: string) => void
}

export default function ModelSelector({ selected, onSelect }: Props) {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [online, setOnline] = useState(false)

  useEffect(() => {
    checkHealth().then((h) => setOnline(h.ok))
    fetchModels().then((r) => {
      if (r.error) { setError(r.error); setModels([]) }
      else {
        setModels(r.models)
        // Auto-select first model if nothing is selected OR if the selected model isn't installed
        if (r.models.length > 0 && (!selected || !r.models.includes(selected))) {
          onSelect(r.models[0])
        }
        setError(null)
      }
    }).catch(() => setError("Failed")).finally(() => setLoading(false))
  }, [])

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full transition-colors duration-300 ${online ? "bg-accent-secondary shadow-[0_0_6px_rgba(56,178,172,0.4)]" : "bg-red-400"}`} />
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
        {!loading && !error && models.length === 0 && <option value="" className="bg-[#E0E5EC]">No models</option>}
        {models.map((m) => (
          <option key={m} value={m} className="bg-[#E0E5EC]">{m}</option>
        ))}
      </select>
    </div>
  )
}
