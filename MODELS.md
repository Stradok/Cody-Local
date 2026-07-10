# AI Models for Cody-Local

This guide explains which models to use with Cody-Local, optimized for RAG (document search) and coding tasks.

---

## Quick Recommendation

**For most people:** Use `make portable` to auto-download everything

```bash
make portable   # Installs Ollama + recommended models
make run        # Start Cody-Local
```

This downloads:
- **qwen2.5-coder:1.5b** (900MB) — Main LLM, best all-rounder
- **nomic-embed-text** (274MB) — Embedding model for RAG/Library

---

## Model Selection

### Primary Chat Model

Choose **one** based on your hardware:

| Model | Size | RAM | Speed | Best For |
|---|---|---|---|---|
| **qwen2.5-coder:1.5b** ⭐ | 900MB | 2-3GB | ⚡ Fast | Coding + RAG (RECOMMENDED) |
| qwen2.5-coder:7b | 4.5GB | 6-8GB | Good | Best quality, more capable |
| llama3.2:1b | 635MB | 2GB | ⚡ Very fast | General tasks, smaller |
| smollm2:360m | 252MB | 1GB | ⚡⚡ Tiny | Ultra-low hardware |
| qwen2.5:1.5b | 900MB | 2-3GB | ⚡ Fast | Better reasoning |

**Why Qwen2.5-Coder 1.5B?**
- ✅ Optimized for code understanding
- ✅ Good for RAG with documentation
- ✅ Fast enough for real-time interaction
- ✅ Fits in 3GB RAM (most laptops)
- ✅ Small enough for offline distribution

### Embedding Model (for RAG)

Used automatically by the **Library** feature when you index books/docs:

| Model | Size | Speed | Best For |
|---|---|---|---|
| **nomic-embed-text** ⭐ | 274MB | ⚡ Fast | RAG, document search |
| jina-embeddings-v2 | 500MB | Medium | Better quality |
| bge-small | 200MB | ⚡ Very fast | Ultra-small |

---

## How to Manually Download Models

### Using Ollama CLI

```bash
# Main chat model
ollama pull qwen2.5-coder:1.5b

# Or if you prefer a different model
ollama pull llama3.2:1b
ollama pull qwen2.5-coder:7b    # Better quality, larger
ollama pull gemma2:2b           # Alternative
ollama pull phi3.5:latest       # Microsoft model

# Embedding model (for Library/RAG)
ollama pull nomic-embed-text
```

### List available models

```bash
ollama list
```

---

## Hardware Requirements

### RAM Needed (Approximate)

- **1GB RAM:** smollm2:360m only
- **2GB RAM:** llama3.2:1b, qwen2.5-coder:1.5b (tight)
- **3GB RAM:** qwen2.5-coder:1.5b (comfortable) ⭐
- **4GB+ RAM:** qwen2.5-coder:7b (recommended quality)
- **8GB+ RAM:** Anything, no compromise

### Storage Needed

- **Install base:** ~1.5GB (app code, dependencies)
- **1 small model:** 900MB (qwen2.5-coder:1.5b)
- **2 models:** 1.2GB (small model + embedding)
- **With docs indexed:** +size of documents

**Total for portable drive:** 3-4GB minimum

---

## Using Different Models

### Change primary model

Edit `backend/.env`:

```bash
# This doesn't change the model, just the API connection
OLLAMA_BASE_URL=http://localhost:11434
```

The model is selected in the UI **Model** dropdown after you start Cody-Local.

### Add/remove models

```bash
# Add a new model
ollama pull gemma2:2b

# It will appear in the UI dropdown automatically
# No restart needed
```

### Remove a model to save space

```bash
ollama rm qwen2.5-coder:1.5b
# Removes ~900MB
```

---

## RAG with Books/Documentation

The **Library** feature lets you index your own documents for semantic search:

1. Open Cody-Local
2. Click the **Library** tab
3. Add a book/PDF/document
4. The **nomic-embed-text** model automatically indexes it
5. Ask questions and get answers from your docs

**Works best with:**
- Technical documentation (code examples, API docs)
- PDFs with text content (scanned PDFs use OCR)
- Markdown files
- Technical books

**Large documents:**
- Can handle 100+ page PDFs
- Auto-chunks at paragraph boundaries
- Search is semantic (understands meaning, not just keywords)

---

## Performance Tips

### Make it faster

1. **Use smaller model + embedding:** smollm2:360m + bge-small
2. **Reduce concurrent tool calls:** Set `MAX_TOOL_CALLS=5` in .env
3. **Disable auto-save:** Reduces disk I/O

### Make it smarter

1. **Use larger model:** qwen2.5-coder:7b
2. **Add more models:** Use different models for different tasks
3. **Fine-tune prompts:** System prompts in `backend/main.py`

### Make it work offline

1. Pre-download models before going offline
2. Use local documents in the Library
3. Don't use GitHub features (require internet)

---

## Troubleshooting

### "Model not found" error

```bash
# Check what models you have
ollama list

# Download the model
ollama pull qwen2.5-coder:1.5b
```

### Models take forever to download

- Check your internet speed
- Models are large (900MB - 4.5GB)
- Consider using smaller models while testing

### Out of memory errors

- Reduce model size (use 1.5B instead of 7B)
- Close other applications
- Set `MAX_TOOL_CALLS=5` to reduce memory usage
- Add swap space (on Linux: `sudo fallocate -l 4G /swapfile`)

### Slow responses

- Smaller models are slower
- Upgrade model size or hardware
- Reduce concurrent requests (set `MAX_TOOL_CALLS=5`)

---

## Advanced: Using OpenRouter or Other APIs

Want to use cloud LLMs instead of local Ollama?

See `backend/main.py` — the code supports LangChain integrations. You can:
- Use OpenRouter's free models
- Use your own API keys
- Mix local + cloud models

(Requires code modification, not GUI-configurable yet)

---

## See Also

- **PORTABLE.md** — Offline deployment with pre-downloaded models
- **README.md** — Full project documentation
- **Ollama models:** https://ollama.ai/library
