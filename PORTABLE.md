# Portable & Offline Setup Guide

This guide helps you run Cody-Local from an external drive (USB, SSD, HDD) or in an offline environment where internet access is limited.

---

## Quick Start (With Internet)

If you have internet access where you'll use it:

```bash
# 1. Extract the cody-local folder to your external drive
# 2. Open terminal in that folder
cd /path/to/external-drive/cody-local

# 3. Run portable setup (one-time)
bash portable-setup.sh

# 4. Start everything
make run

# 5. Open http://localhost:3000
```

That's it! No special configuration needed.

---

## Offline Mode (No Internet on Destination)

Use this when deploying to a machine with no internet access.

### Prerequisites (Install on Machine with Internet)

You need to pre-download everything on a machine with internet, then transfer to the offline location.

**On the machine WITH internet:**

```bash
# 1. Install prerequisites
python3 --version    # Should be 3.11+
node --version       # Should be 18+
ollama --version     # Should be latest

# 2. Clone/download cody-local
git clone https://github.com/Stradok/Cody-Local.git
cd cody-local

# 3. Run setup
bash portable-setup.sh

# 4. Create bundle script
bash scripts/bundle-offline.sh ~/cody-local-offline.tar.gz
```

### Transfer to Offline Machine

```bash
# 1. Copy the bundle to external drive
cp ~/cody-local-offline.tar.gz /media/usb-drive/

# 2. On the offline machine, extract
tar -xzf /media/usb-drive/cody-local-offline.tar.gz
cd cody-local

# 3. Start
make run
```

---

## Pre-Download AI Models

Large AI models must be downloaded beforehand if you want them offline.

### On Machine with Internet

Models are stored in `~/.ollama/models/`. Pre-download them:

```bash
# Download common coding models
ollama pull qwen2.5-coder:7b      # 4.5 GB - Recommended for coding
ollama pull llama3.2:1b           # 635 MB - Small, fast
ollama pull smollm2:360m          # 252 MB - Tiny, runs on low-end devices
ollama pull gemma2:2b             # 1.6 GB - Balanced

# List what you have
ollama list
```

### Transfer Models to Offline Location

Models are large, so transfer them efficiently:

```bash
# On machine with internet:
# 1. Find Ollama models directory
ls ~/.ollama/models/blobs/

# 2. Create a models archive (select only models you need)
cd ~/.ollama/models/
tar -czf /media/usb-drive/ollama-models.tar.gz blobs/ manifests/

# On offline machine:
# 1. Extract to Ollama directory
mkdir -p ~/.ollama/models/
cd ~/.ollama/models/
tar -xzf /media/usb-drive/ollama-models.tar.gz

# 2. Verify models available
ollama list
```

---

## Directory Structure

When distributed on external drive, maintain this structure:

```
/media/usb-drive/cody-local/
├── backend/
│   ├── venv/                 (created by portable-setup.sh)
│   ├── main.py
│   ├── requirements.txt
│   └── .env                  (configure here)
├── frontend/
│   ├── node_modules/         (created by portable-setup.sh)
│   ├── src/
│   └── package.json
├── Makefile
├── portable-setup.sh
├── PORTABLE.md
└── README.md
```

---

## Configuration for Offline

Edit `backend/.env` to customize for offline use:

```bash
# For locally-running Ollama
OLLAMA_BASE_URL=http://localhost:11434

# No GitHub token needed for offline mode (leave empty)
GITHUB_TOKEN=

# Restrict to local commands
ALLOWED_COMMANDS=python,python3,node,npm,npx,git,ls,cat,echo,mkdir,cp,mv

# Adjust for low-end hardware (reduce concurrent tool calls)
MAX_TOOL_CALLS=10
```

---

## Running on Low-End Hardware

For devices with limited RAM (< 4GB):

1. **Use small models:**
   ```bash
   ollama pull smollm2:135m    # 400 MB, runs on 1GB RAM
   ollama pull qwen2.5:0.5b    # 350 MB, very fast
   ```

2. **Reduce backend overhead:**
   ```
   # In backend/.env
   MAX_TOOL_CALLS=5
   ```

3. **Disable frontend auto-refresh:**
   Edit `frontend/src/app/page.tsx` to reduce polling intervals.

---

## Troubleshooting Offline Setup

### "Python/Node not found"
Install them on the offline machine first, or use Docker.

### "Models not available"
Ensure you pre-downloaded them on a machine with internet and transferred them to `~/.ollama/models/`.

### "Cannot connect to Ollama"
Make sure Ollama is running:
```bash
ollama serve
```

### "Port 3000 already in use"
The app auto-selects the next free port (3001, 3002, etc.). Check terminal output for the actual URL.

---

## Docker Alternative (Most Portable)

For maximum portability across machines, use Docker:

```bash
# Build image (on machine with internet)
docker build -f Dockerfile.portable -t cody-local:portable .

# Save to external drive
docker save cody-local:portable | gzip > /media/usb/cody-local.tar.gz

# On offline machine, load and run
docker load < /media/usb/cody-local.tar.gz
docker run -p 3000:3000 -p 8000:8000 -v ~/.ollama:/root/.ollama cody-local:portable
```

See `Dockerfile.portable` for details.

---

## Syncing Updates

To update Cody-Local on your external drive:

```bash
# On machine with internet
cd cody-local
git pull origin main

# Re-run setup
bash portable-setup.sh

# Re-bundle if needed
bash scripts/bundle-offline.sh ~/cody-local-updated.tar.gz
```

---

## Tips for Village/Community Use

- **Distribute via USB stick:** Pre-load one stick, clone to others
- **Local model library:** Index local PDFs/docs in the Library tab
- **Workshops:** Use the Plan mode for educational collaboration
- **Offline docs:** Add your own documentation to `~/cody-local/Books/`

---

## Support

For issues with portable setup, check:
1. Are Python and Node.js installed? (`python3 -v`, `node -v`)
2. Is Ollama running? (`ollama serve`)
3. Do you have models downloaded? (`ollama list`)
4. Check logs: `backend/*.log` or browser console (F12)

See main `README.md` for architecture and full documentation.
