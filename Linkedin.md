Building offline AI when the internet goes dark 🌍

A few weeks ago, AJK in Pakistan went offline for 35 days. My cousin was deep into learning with NotebookLM — suddenly, gone. No internet. No AI. No learning.

So I built Cody-Local: a fully offline AI coding assistant that runs on any machine. No cloud, no APIs, no internet required.

The Challenge: How do you get enterprise-grade AI capabilities into a world with unreliable connectivity?

The Solution:
- 🏃 Lightweight: Embedding model (274MB) + LLM (900MB) — total 1.2GB
- 📚 Universal database: Index survival guides, cooking recipes, code docs, anything — semantic search across your data
- 💻 Autonomous agent: Writes code, debugs, refactors — all locally
- 📱 Truly portable: External drive, USB stick, anywhere with Python + Node.js
- ⚡ Low hardware footprint: Runs on laptops, even modest hardware

What makes this different: We chose models like Qwen2.5-Coder (900MB) + Nomic Embed Text (274MB) — small enough to distribute worldwide, powerful enough to be useful. It's modular architecture means: need better performance? Swap in a 12B parameter model. Want ultra-small? Use a 360M model. Your choice.

The real win? A community in rural Pakistan, a student with no electricity, someone learning offline — they all get access to the same AI tools the world uses. Not watered down. Not locked behind paywalls. Just... available.

Open source, fully portable, works offline. This is what democratizing AI actually looks like.

GitHub: github.com/Stradok/Cody-Local