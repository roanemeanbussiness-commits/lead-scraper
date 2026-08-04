from __future__ import annotations

from fastapi import FastAPI

from . import __version__

app = FastAPI(title="8-Thon Intelligence Lead Scraper")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "8-Thon Intelligence Lead Scraper",
        "version": __version__,
        "status": "ok",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

