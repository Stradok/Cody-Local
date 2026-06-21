"use client"

import { ToolCall } from "@/types"

interface Props {
  toolCall: ToolCall
}

export default function ToolCallCard({ toolCall }: Props) {
  let args: string
  try {
    const parsed = JSON.parse(toolCall.arguments)
    args = JSON.stringify(parsed, null, 2)
  } catch {
    args = toolCall.arguments
  }

  return (
    <div className="my-2 rounded-[16px] overflow-hidden">
      <div className="neu-extruded-sm bg-[#E0E5EC]">
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-muted/10">
          <span className="text-[10px] font-bold text-accent uppercase tracking-wider">🛠 TOOL</span>
          <span className="text-xs font-mono font-medium text-fg">{toolCall.name}</span>
        </div>
        <pre className="px-3 py-2 text-[11px] text-muted font-mono whitespace-pre-wrap overflow-x-auto max-h-32">{args}</pre>
      </div>
      {toolCall.result && (
        <div className="neu-inset-sm bg-[#E0E5EC] mt-[2px]">
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-muted/10">
            <span className="text-[10px] font-bold text-accent-secondary uppercase tracking-wider">RESULT</span>
          </div>
          <pre className="px-3 py-2 text-[11px] text-muted font-mono whitespace-pre-wrap overflow-x-auto max-h-40">{toolCall.result}</pre>
        </div>
      )}
    </div>
  )
}
