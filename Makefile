# ============================================================
# UK Robo Advisor — Makefile
# ============================================================
# Usage: make <command>
# ============================================================

.PHONY: install dev seed backtest migrate update-prices backend frontend

# Install all dependencies (Python + Node)
install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# Start both backend and frontend for local development
dev:
	@echo "Starting backend on http://127.0.0.1:8000"
	@echo "Starting frontend on http://127.0.0.1:5173"
	@echo "Use Ctrl+C to stop."
	@start /B cmd /c "cd backend && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"
	cd frontend && npm run dev

# Start backend only
backend:
	cd .. && uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Start frontend only
frontend:
	cd frontend && npm run dev

# Seed ETF registry and fetch initial historical prices
seed:
	python scripts/seed_etf_registry.py

# Run a backtest from the CLI
backtest:
	python scripts/backtest_runner.py --risk 5 --amount 10000

# Refresh local price cache
update-prices:
	python scripts/update_prices.py

# Run Alembic database migrations
migrate:
	cd backend && alembic upgrade head
