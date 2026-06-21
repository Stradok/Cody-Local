import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Cody Local",
  description: "Local coding agent powered by Ollama",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
