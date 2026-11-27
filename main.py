import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.seed_data import seed_database
from app.routers import items, consumption, predictions, anomalies, shopping, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and Seed if empty
    init_db()
    seed_database(force=False)
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title="SmartStock AI",
    description="An Intelligent Household Consumption and Waste Prevention System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(items.router)
app.include_router(consumption.router)
app.include_router(predictions.router)
app.include_router(anomalies.router)
app.include_router(shopping.router)
app.include_router(analytics.router)

# Mount Static Files (CSS, JS, Assets)
static_dir = os.path.join(os.path.dirname(__file__), "app", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serves the main single-page web dashboard."""
    index_file = os.path.join(static_dir, "index.html")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
