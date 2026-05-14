# LAIA Makefile
# Standard targets for development, testing, deployment, and maintenance.

LAIA_ROOT := $(shell pwd)
LAIA_HOME := $(HOME)/.laia
AGORA_DIR := $(LAIA_ROOT)/services/agora-backend
INFRA_DIR := $(LAIA_ROOT)/infra
UI_DIR := $(LAIA_ROOT)/laia-ui

.PHONY: help install test deploy backup clean status health

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────────────────────────

install: ## Install all dependencies
	@echo "Installing AGORA backend..."
	cd $(AGORA_DIR) && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	@echo "Installing LAIA UI..."
	cd $(UI_DIR) && pnpm install
	@echo "Done. Run 'make test' to verify."

test: ## Run all tests
	@echo "=== AGORA Backend ==="
	rm -f $(AGORA_DIR)/data/agora.db*
	cd $(AGORA_DIR) && .venv/bin/python -m pytest tests/ -q
	@echo "=== TypeScript ==="
	cd $(UI_DIR) && npx tsc --noEmit -p packages/arch-app/tsconfig.json 2>/dev/null
	cd $(UI_DIR) && npx tsc --noEmit -p packages/agora-app/tsconfig.json 2>/dev/null
	@echo "All tests passed."

# ── Deploy ───────────────────────────────────────────────────────────────

deploy-agora: ## Build and deploy AGORA (frontend + backend)
	@echo "=== AGORA Frontend ==="
	cd $(UI_DIR) && pnpm build:agora
	mkdir -p /srv/laia/agora/frontend/dist
	rm -rf /srv/laia/agora/frontend/dist/*
	cp -r $(UI_DIR)/packages/agora-app/dist/* /srv/laia/agora/frontend/dist/
	@echo "=== AGORA Backend ==="
	pkill -f "uvicorn app.main:app.*8088" 2>/dev/null || true
	sleep 1
	cd $(AGORA_DIR) && nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8088 > /dev/null 2>&1 &
	sleep 3
	@echo "AGORA deployed: http://localhost:8088"

deploy-arch: ## Build and deploy ARCH admin UI
	cd $(UI_DIR) && pnpm build:arch
	rm -rf $(LAIA_ROOT)/.laia-core/laia-ui-server/frontend/dist
	cp -r $(UI_DIR)/packages/arch-app/dist $(LAIA_ROOT)/.laia-core/laia-ui-server/frontend/dist
	@echo "ARCH deployed: http://localhost:8077"

# ── Backup ────────────────────────────────────────────────────────────────

backup: ## Full backup (DB, workspaces, config)
	@echo "=== Backup ==="
	mkdir -p $(LAIA_HOME)/backups
	tar czf $(LAIA_HOME)/backups/workspaces-$(shell date +%Y%m%d-%H%M%S).tar.gz $(LAIA_ROOT)/workspaces/
	tar czf $(LAIA_HOME)/backups/config-$(shell date +%Y%m%d-%H%M%S).tar.gz $(LAIA_HOME)/config.yaml $(LAIA_HOME)/.env
	cp $(AGORA_DIR)/data/agora.db $(LAIA_HOME)/backups/agora-$(shell date +%Y%m%d-%H%M%S).db
	@echo "Backups in $(LAIA_HOME)/backups/"

# ── Maintenance ───────────────────────────────────────────────────────────

clean: ## Clean build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(AGORA_DIR)/data/agora.db*
	@echo "Clean."

status: ## Show LAIA system status
	@$(INFRA_DIR)/bin/laia-status

health: ## Run health check
	@$(INFRA_DIR)/bin/laia-health

logs: ## Show recent logs (all services)
	@$(INFRA_DIR)/bin/laia-logs all

watch: ## Live resource monitor
	@$(INFRA_DIR)/bin/laia-watch 3
