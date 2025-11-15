# Makefile for discord.wafer.space

.PHONY: help setup test export organize navigate clean all

# Variables
EXPORTER_DIR := bin/discord-exporter
EXPORTER := $(EXPORTER_DIR)/DiscordChatExporter.Cli
EXPORTER_VERSION := latest
EXPORTER_URL := https://github.com/Tyrrrz/DiscordChatExporter/releases/$(EXPORTER_VERSION)/download/DiscordChatExporter.Cli.linux-x64.zip
PYTHON := uv run python

help:
	@echo "discord.wafer.space Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  setup      - Download DiscordChatExporter.Cli if needed"
	@echo "  test       - Run all tests"
	@echo "  export     - Run Discord export script"
	@echo "  organize   - Organize exports into public/ directory"
	@echo "  navigate   - Generate navigation HTML pages"
	@echo "  all        - Run complete pipeline: export → organize → navigate"
	@echo "  clean      - Remove exports, public, and state.json"
	@echo "  clean-all  - Remove everything including DiscordChatExporter.Cli"
	@echo ""
	@echo "Requirements:"
	@echo "  - DISCORD_BOT_TOKEN environment variable must be set"
	@echo "  - config.toml must be configured with guild_id and channels"

# Check if DiscordChatExporter.Cli exists, download if not
setup: $(EXPORTER)

$(EXPORTER):
	@echo "Downloading DiscordChatExporter.Cli to $(EXPORTER_DIR)..."
	@mkdir -p $(EXPORTER_DIR)
	curl -L -o $(EXPORTER_DIR)/DiscordChatExporter.zip $(EXPORTER_URL)
	unzip -o $(EXPORTER_DIR)/DiscordChatExporter.zip -d $(EXPORTER_DIR)
	chmod +x $(EXPORTER)
	rm $(EXPORTER_DIR)/DiscordChatExporter.zip
	@echo "✓ DiscordChatExporter.Cli ready at $(EXPORTER)"

# Run tests
test:
	@echo "Running tests..."
	uv run pytest -v

# Export Discord channels
export: setup
	@echo "Exporting Discord channels..."
	@if [ -z "$$DISCORD_BOT_TOKEN" ]; then \
		echo "ERROR: DISCORD_BOT_TOKEN environment variable not set"; \
		exit 1; \
	fi
	PYTHONPATH=. $(PYTHON) scripts/export_channels.py

# Organize exports into public/ directory
organize:
	@echo "Organizing exports..."
	PYTHONPATH=. $(PYTHON) scripts/organize_exports.py

# Generate navigation HTML pages
navigate:
	@echo "Generating navigation pages..."
	PYTHONPATH=. $(PYTHON) scripts/generate_navigation.py

# Run complete pipeline
all: export organize navigate
	@echo ""
	@echo "✓ Complete pipeline finished!"
	@echo "  - Exports: exports/"
	@echo "  - Public site: public/"
	@echo "  - State: state.json"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf exports/ public/
	echo "{}" > state.json
	@echo "✓ Cleaned"

# Clean everything including DiscordChatExporter
clean-all: clean
	@echo "Removing DiscordChatExporter directory..."
	rm -rf $(EXPORTER_DIR)
	@echo "✓ Everything cleaned"
