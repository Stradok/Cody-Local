"use client"

import { useEffect } from "react"

export interface ToastItem {
  id: string
  message: string
  type: "success" | "error" | "info" | "warning"
}

interface StackProps {
  toasts: ToastItem[]
  onDismiss: (id: string) => void
}

export default function ToastStack({ toasts, onDismiss }: StackProps) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 items-end pointer-events-none">
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: string) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), toast.type === "error" ? 6000 : 3000)
    return () => clearTimeout(t)
  }, [toast.id, toast.type, onDismiss])

  const icon = {
    success: "✓",
    error: "✕",
    info: "ℹ",
    warning: "⚠",
  }[toast.type]

  const iconColor = {
    success: "text-emerald-500",
    error: "text-red-400",
    info: "text-[#6c63ff]",
    warning: "text-amber-500",
  }[toast.type]

  const dot = {
    success: "bg-emerald-400",
    error: "bg-red-400",
    info: "bg-[#6c63ff]",
    warning: "bg-amber-400",
  }[toast.type]

  return (
    <div className="toast-enter pointer-events-auto flex items-start gap-3 neu-extruded bg-[#E0E5EC] rounded-[18px] px-4 py-3 max-w-[320px] min-w-[200px]">
      <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${dot} text-white mt-[1px]`}>
        {icon}
      </div>
      <p className="text-[11px] text-fg leading-snug flex-1">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 text-muted hover:text-fg text-[10px] transition-colors mt-[2px]"
      >
        ✕
      </button>
    </div>
  )
}
