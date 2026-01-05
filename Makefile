.PHONY: backend frontend dev test lint

# Start backend server
backend:
	PYTHONPATH=. uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend dev server
frontend:
	cd frontend && npm run dev

# Run both in parallel (requires tmux or separate terminals)
dev:
	@echo "Run in separate terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# Run tests
test:
	uv run pytest -v

# Run linter
lint:
	uv run ruff check backend tests
	cd frontend && npm run lint

# Type check
typecheck:
	uv run pyright backend
	cd frontend && npm run build

# Install dependencies
install:
	uv sync
	cd frontend && npm install

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	rm -rf frontend/dist frontend/node_modules/.vite
