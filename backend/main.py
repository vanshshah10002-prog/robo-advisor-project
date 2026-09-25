"""
UK Robo Advisor — FastAPI Application Entrypoint
=================================================
Main application file that configures FastAPI, CORS, and mounts all route modules.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import HOST, PORT, DEBUG
from backend.api.routes.onboarding import router as onboarding_router
from backend.api.routes.portfolio import router as portfolio_router
from backend.api.routes.simulate import router as simulate_router
from backend.api.routes.performance import router as performance_router
from backend.api.routes.market import router as market_router
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables and add any new ledger columns before the first request.
    init_db()
    yield


app = FastAPI(
    title="UK Robo Advisor",
    description=(
        "A sophisticated, UK-focused robo-advisory engine inspired by Wealthfront's "
        "methodology. Provides algorithmic portfolio construction, optimisation, and "
        "monitoring using UK-listed ETFs on the London Stock Exchange. "
        "For educational/personal use only — not FCA registered."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(onboarding_router, prefix="/api", tags=["Onboarding"])
app.include_router(portfolio_router, prefix="/api", tags=["Portfolio"])
app.include_router(simulate_router, prefix="/api", tags=["Simulation"])
app.include_router(performance_router, prefix="/api", tags=["Performance"])
app.include_router(market_router, prefix="/api", tags=["Market Data"])


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "UK Robo Advisor",
        "version": "1.0.0",
        "disclaimer": (
            "This application is for educational/personal use only. "
            "Not registered with the FCA. Not financial advice."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=DEBUG)
