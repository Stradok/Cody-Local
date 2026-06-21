# ─────────────────────────────────────────────────────────────────────────────
# Cody Local — Makefile
# Usage: make setup && make run
# ─────────────────────────────────────────────────────────────────────────────

SHELL         := /bin/bash
BACKEND_DIR   := backend
FRONTEND_DIR  := frontend
VENV          := $(BACKEND_DIR)/venv

UVICORN       := $(CURDIR)/$(VENV)/bin/uvicorn
PIP           := $(CURDIR)/$(VENV)/bin/pip

# Base ports — if taken, the next free port is used automatically
BACKEND_BASE  := 8000
FRONTEND_BASE := 3000
OLLAMA_HOST   := http://localhost:11434

.PHONY: all setup setup-backend setup-frontend \
        run run-backend run-frontend \
        health check logs \
        clean clean-all help

.DEFAULT_GOAL := help

# ─── Port-finder shell function ───────────────────────────────────────────────
# Inline this at the top of any recipe that needs dynamic ports.
# Usage:  BPORT=$$(fp $(BACKEND_BASE))
#   fp()  scans port BASE … BASE+19, echoes the first one with nothing listening.
FP := fp() { local p=$$1 m=$$(($$1+20)); while (( p < m )); do \
    (echo >/dev/tcp/127.0.0.1/$$p) 2>/dev/null && (( p++ )) || { echo $$p; return 0; }; \
  done; echo $$1; };

# ─── Help ─────────────────────────────────────────────────────────────────────

help:
	@printf "\033[1mCody Local\033[0m — Local AI Coding Assistant\n\n"
	@printf "\033[36mSetup\033[0m\n"
	@printf "  make setup          Install all dependencies (run once)\n"
	@printf "  make setup-backend  Python venv + pip install only\n"
	@printf "  make setup-frontend npm install only\n\n"
	@printf "\033[36mRun\033[0m\n"
	@printf "  make run            Start backend + frontend (auto port, Ctrl+C to stop)\n"
	@printf "  make run-backend    Start FastAPI backend only\n"
	@printf "  make run-frontend   Start Next.js frontend only\n\n"
	@printf "\033[36mDiagnostics\033[0m\n"
	@printf "  make health         Scan ports $(BACKEND_BASE)-$(($(BACKEND_BASE)+19)) / $(FRONTEND_BASE)-$(($(FRONTEND_BASE)+19))\n"
	@printf "  make logs           Tail the backend log file\n\n"
	@printf "\033[36mCleanup\033[0m\n"
	@printf "  make clean          Remove Python caches\n"
	@printf "  make clean-all      Remove venv, node_modules, .next\n\n"
	@printf "\033[36mPorts\033[0m  (first free starting at base)\n"
	@printf "  Backend   starts at $(BACKEND_BASE)\n"
	@printf "  Frontend  starts at $(FRONTEND_BASE)\n"
	@printf "  Ollama    $(OLLAMA_HOST)\n\n"

# ─── Setup ────────────────────────────────────────────────────────────────────

setup: setup-backend setup-frontend
	@printf "\n\033[32m✓ Setup complete.\033[0m  Start the app:\n\n"
	@printf "    \033[1mmake run\033[0m\n\n"

setup-backend:
	@printf "\033[1m[backend]\033[0m Checking Python...\n"
	@command -v python3 >/dev/null 2>&1 || { printf "\033[31mError:\033[0m python3 not found\n"; exit 1; }
	@python3 -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null || \
		{ printf "\033[31mError:\033[0m Python 3.11+ required (found $$(python3 --version))\n"; exit 1; }
	@[ -d $(VENV) ] || python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip --quiet
	@$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@printf "\033[32m[backend]\033[0m Done\n"

setup-frontend:
	@printf "\033[1m[frontend]\033[0m Checking Node.js...\n"
	@command -v node >/dev/null 2>&1 || { printf "\033[31mError:\033[0m node not found — install from nodejs.org\n"; exit 1; }
	@node -e "const v=process.versions.node.split('.')[0]; if(+v<18){process.stderr.write('Error: Node 18+ required\n');process.exit(1)}" || exit 1
	@printf "\033[1m[frontend]\033[0m Installing packages...\n"
	@cd $(FRONTEND_DIR) && npm install --silent
	@printf "\033[32m[frontend]\033[0m Done\n"

# ─── Run ──────────────────────────────────────────────────────────────────────

run: _require-venv _require-node-modules
	@$(FP) \
	BPORT=$$(fp $(BACKEND_BASE)); \
	FPORT=$$(fp $(FRONTEND_BASE)); \
	printf "\033[1mStarting Cody Local\033[0m\n\n"; \
	printf "  \033[32mBackend:\033[0m  http://127.0.0.1:$$BPORT\n"; \
	printf "  \033[32mFrontend:\033[0m http://localhost:$$FPORT\n"; \
	printf "  \033[32mAPI docs:\033[0m http://127.0.0.1:$$BPORT/docs\n\n"; \
	printf "Press \033[1mCtrl+C\033[0m to stop both services\n\n"; \
	( cd $(CURDIR)/$(BACKEND_DIR) && $(UVICORN) main:app \
	    --host 127.0.0.1 --port $$BPORT --reload ) & BPID=$$!; \
	( cd $(CURDIR)/$(FRONTEND_DIR) && \
	    NEXT_PUBLIC_API_URL=http://127.0.0.1:$$BPORT npx next dev --port $$FPORT ) & FPID=$$!; \
	trap "printf '\n\033[33mStopping...\033[0m\n'; kill $$BPID $$FPID 2>/dev/null; wait $$BPID $$FPID 2>/dev/null; exit 0" INT TERM; \
	wait $$BPID $$FPID

run-backend: _require-venv
	@$(FP) \
	BPORT=$$(fp $(BACKEND_BASE)); \
	printf "\033[1m[backend]\033[0m Starting on 127.0.0.1:$$BPORT\n"; \
	cd $(CURDIR)/$(BACKEND_DIR) && $(UVICORN) main:app \
	    --host 127.0.0.1 --port $$BPORT --reload --log-level info

run-frontend: _require-node-modules
	@$(FP) \
	FPORT=$$(fp $(FRONTEND_BASE)); \
	printf "\033[1m[frontend]\033[0m Starting on port $$FPORT\n"; \
	printf "\033[33m[frontend]\033[0m Backend URL: $${NEXT_PUBLIC_API_URL:-http://127.0.0.1:$(BACKEND_BASE) (default)}\n"; \
	cd $(CURDIR)/$(FRONTEND_DIR) && \
	    NEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_API_URL:-http://127.0.0.1:$(BACKEND_BASE)} npx next dev --port $$FPORT

# ─── Health ───────────────────────────────────────────────────────────────────
# Scans the full port range so it finds the service regardless of which port it landed on.

health:
	@printf "\033[1mHealth Check\033[0m\n"
	@printf "  Backend   "; \
	found=0; \
	for p in $$(seq $(BACKEND_BASE) $$(($(BACKEND_BASE)+19))); do \
	    if curl -sf http://127.0.0.1:$$p/api/health -o /dev/null 2>/dev/null; then \
	        printf "\033[32mOK\033[0m — http://127.0.0.1:$$p\n"; found=1; break; \
	    fi; \
	done; \
	[ $$found -eq 1 ] || printf "\033[31mOFFLINE\033[0m — run: make run-backend\n"
	@printf "  Ollama    "; \
	curl -sf $(OLLAMA_HOST)/api/tags -o /dev/null 2>/dev/null \
	    && printf "\033[32mOK\033[0m — $(OLLAMA_HOST)\n" \
	    || printf "\033[31mOFFLINE\033[0m — run: ollama serve\n"
	@printf "  Frontend  "; \
	found=0; \
	for p in $$(seq $(FRONTEND_BASE) $$(($(FRONTEND_BASE)+19))); do \
	    if curl -sf http://localhost:$$p -o /dev/null 2>/dev/null; then \
	        printf "\033[32mOK\033[0m — http://localhost:$$p\n"; found=1; break; \
	    fi; \
	done; \
	[ $$found -eq 1 ] || printf "\033[31mOFFLINE\033[0m — run: make run-frontend\n"

check: health

logs:
	@LOG=$$(ls -t logs/*.log 2>/dev/null | head -1); \
	[ -n "$$LOG" ] && tail -f "$$LOG" || printf "No log files found in logs/\n"

# ─── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	@find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find $(BACKEND_DIR) -name "*.pyc" -delete 2>/dev/null; true
	@printf "\033[32m✓ Cleaned\033[0m Python caches\n"

clean-all: clean
	@printf "Removing venv, node_modules, .next...\n"
	@rm -rf $(VENV)
	@rm -rf $(FRONTEND_DIR)/.next
	@rm -rf $(FRONTEND_DIR)/node_modules
	@printf "\033[32m✓ Done\033[0m\n"

# ─── Guards ───────────────────────────────────────────────────────────────────

_require-venv:
	@[ -d $(VENV) ] || { \
		printf "\033[31mError:\033[0m virtualenv not found — run: \033[1mmake setup\033[0m\n"; \
		exit 1; \
	}

_require-node-modules:
	@[ -d $(FRONTEND_DIR)/node_modules ] || { \
		printf "\033[31mError:\033[0m node_modules not found — run: \033[1mmake setup\033[0m\n"; \
		exit 1; \
	}
