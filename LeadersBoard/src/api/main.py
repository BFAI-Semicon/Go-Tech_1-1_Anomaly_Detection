"""LeadersBoard API - Main entry point."""

from fastapi import FastAPI

from src.api.jobs import router as jobs_router
from src.api.submissions import router as submissions_router

app = FastAPI(
    title="LeadersBoard API",
    description="ML Experiment Platform with LeaderBoard",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "LeadersBoard API is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


app.include_router(submissions_router)
app.include_router(jobs_router)
