PREFIX ?= $(HOME)
KITTY_CONFIG_DIR ?= $(PREFIX)/.config/kitty
SKILL_SOURCE ?= .
SKILLS_FLAGS ?= -g -y -a universal
SKILLS_CLI ?= skills
PYTHON ?= $(shell command -v python3 2>/dev/null || echo python3)

.DEFAULT_GOAL := help
.PHONY: all

help: ## Show this help (default)
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install Kitty kitten and kitherd AI skill
	@echo "==> Installing herdr_panel.py to $(KITTY_CONFIG_DIR)..."
	@mkdir -p "$(KITTY_CONFIG_DIR)"
	@install -m 755 skills/kitherd/scripts/herdr_panel.py "$(KITTY_CONFIG_DIR)/herdr_panel.py"
	@echo "==> Installing kitherd skill via $(SKILLS_CLI)..."
	@$(SKILLS_CLI) add "$(SKILL_SOURCE)" $(SKILLS_FLAGS)
	@echo "==> Installation complete!"

uninstall: ## Remove Kitty kitten and uninstall kitherd AI skill
	@echo "==> Removing herdr_panel.py from $(KITTY_CONFIG_DIR)..."
	@rm -f "$(KITTY_CONFIG_DIR)/herdr_panel.py"
	@echo "==> Removing kitherd skill via $(SKILLS_CLI)..."
	@-$(SKILLS_CLI) remove kitherd -g -y 2>/dev/null || true
	@echo "==> Uninstall complete!"

test: ## Run validation tests for scripts and skill discovery
	@echo "==> Testing Python syntax..."
	@$(PYTHON) -m py_compile skills/kitherd/scripts/herdr_panel.py
	@echo "==> Testing herdr_panel.py --list output..."
	@$(PYTHON) skills/kitherd/scripts/herdr_panel.py --list
	@echo "==> Testing skill discovery via $(SKILLS_CLI)..."
	@$(SKILLS_CLI) add . --list
	@echo "==> All tests passed!"

clean: ## Remove temporary build and cache files
	@rm -rf skills/kitherd/scripts/__pycache__ __pycache__
