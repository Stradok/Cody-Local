"use client"

import { useState } from "react"
import { pullModel } from "@/lib/api"

interface Model {
  id: string
  label: string
  ram: string
  note: string
}

const TIERS: { tier: string; desc: string; models: Model[] }[] = [
  {
    tier: "Tiny",
    desc: "< 1 GB RAM — works on any device, even old phones via browser",
    models: [
      { id: "smollm2:135m",   label: "SmolLM2 135M",  ram: "~500 MB", note: "Fastest possible" },
      { id: "smollm2:360m",   label: "SmolLM2 360M",  ram: "~800 MB", note: "Better quality" },
      { id: "qwen2.5:0.5b",   label: "Qwen2.5 0.5B",  ram: "~1 GB",   note: "Best at this size" },
    ],
  },
  {
    tier: "Small",
    desc: "1–2 GB RAM — good for CPU-only laptops, Raspberry Pi",
    models: [
      { id: "llama3.2:1b",    label: "Llama 3.2 1B",  ram: "~2 GB",   note: "Meta, solid quality" },
      { id: "qwen2.5:1.5b",   label: "Qwen2.5 1.5B",  ram: "~2.5 GB", note: "Noticeably smarter" },
      { id: "gemma2:2b",      label: "Gemma 2 2B",    ram: "~3 GB",   note: "Google, surprisingly capable" },
    ],
  },
  {
    tier: "Balanced",
    desc: "3–5 GB RAM — for machines with 8 GB+ RAM, no GPU needed",
    models: [
      { id: "llama3.2:3b",    label: "Llama 3.2 3B",  ram: "~4 GB",   note: "Good all-rounder" },
      { id: "qwen2.5:3b",     label: "Qwen2.5 3B",    ram: "~4 GB",   note: "Strong instruction following" },
      { id: "phi3.5",         label: "Phi 3.5 Mini",  ram: "~5 GB",   note: "Microsoft, great for coding" },
    ],
  },
]

interface Props {
  onInstalled: (modelId: string) => void
  onClose: () => void
  onToast?: (msg: string, type: "success" | "error" | "info") => void
}

export default function ModelPicker({ onInstalled, onClose, onToast }: Props) {
  const [pulling, setPulling] = useState<string | null>(null)
  const [progress, setProgress] = useState("")

  async function handlePull(modelId: string) {
    if (pulling) return
    setPulling(modelId)
    setProgress("Starting…")

    await pullModel(
      modelId,
      (status, pct) => setProgress(pct != null ? `${status} — ${pct}%` : status),
      () => {
        setPulling(null)
        setProgress("")
        onToast?.(`"${modelId}" installed`, "success")
        onInstalled(modelId)
      },
      (err) => {
        setPulling(null)
        setProgress("")
        onToast?.(`Pull failed: ${err.slice(0, 80)}`, "error")
      },
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm">
      <div className="neu-extruded rounded-[32px] p-5 w-[480px] max-h-[80vh] overflow-auto mx-4">

        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-display font-extrabold text-sm text-fg tracking-tight">Install a Model</h2>
            <p className="text-[10px] text-muted mt-0.5">All run locally via Ollama — no internet needed after install</p>
          </div>
          <button onClick={onClose}
            className="neu-extruded-sm w-7 h-7 rounded-full flex items-center justify-center text-[10px] text-muted hover:text-fg transition-all"
          >✕</button>
        </div>

        <div className="space-y-4">
          {TIERS.map((t) => (
            <div key={t.tier}>
              <div className="flex items-baseline gap-2 mb-1.5">
                <span className="text-[9px] font-display font-bold text-accent uppercase tracking-widest">{t.tier}</span>
                <span className="text-[9px] text-muted">{t.desc}</span>
              </div>
              <div className="space-y-1">
                {t.models.map((m) => {
                  const isPulling = pulling === m.id
                  return (
                    <div key={m.id} className="flex items-center gap-3 px-3 py-2.5 rounded-[16px] neu-inset-sm">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-medium text-fg">{m.label}</span>
                          <span className="text-[9px] text-muted/60 font-mono">{m.ram}</span>
                        </div>
                        <p className="text-[9px] text-muted">{m.note}</p>
                        {isPulling && (
                          <p className="text-[9px] text-accent animate-pulse mt-0.5">{progress}</p>
                        )}
                      </div>
                      <button
                        onClick={() => handlePull(m.id)}
                        disabled={!!pulling}
                        className="shrink-0 px-3 py-1.5 rounded-[12px] text-[10px] font-medium neu-extruded-sm text-accent hover:text-fg transition-all disabled:opacity-40 flex items-center gap-1.5"
                      >
                        {isPulling
                          ? <><span className="w-2.5 h-2.5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />Pulling</>
                          : "Install"
                        }
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        <p className="text-[9px] text-muted/50 text-center mt-4">
          Tip: for phone access, run Cody-Local on a laptop and open it in the phone browser over Wi-Fi
        </p>
      </div>
    </div>
  )
}
