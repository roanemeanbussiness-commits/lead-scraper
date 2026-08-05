from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


JobRunner = Callable[[Callable[[int, str, str], None]], dict[str, object]]


@dataclass
class SearchJob:
    id: str
    kind: str
    status: str = "queued"
    progress: int = 0
    stage: str = "Queued"
    message: str = "Waiting to start"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict[str, object] | None = None
    error: str = ""
    download_path: Path | None = None

    def snapshot(self) -> dict[str, object]:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
            "download_url": f"/api/jobs/{self.id}/download" if self.download_path else "",
        }


class JobManager:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, SearchJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lead-search")

    def submit(self, kind: str, runner: JobRunner) -> SearchJob:
        with self._lock:
            if any(job.status in {"queued", "running"} for job in self._jobs.values()):
                raise RuntimeError("A search is already running. Wait for it to finish before starting another.")
            job = SearchJob(id=uuid.uuid4().hex[:16], kind=kind)
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id, runner)
        return job

    def get(self, job_id: str) -> SearchJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, runner: JobRunner) -> None:
        self._update(job_id, status="running", progress=2, stage="Starting", message="Preparing the search")

        def progress(value: int, stage: str, message: str) -> None:
            self._update(job_id, progress=max(2, min(99, value)), stage=stage, message=message)

        try:
            result = runner(progress)
            csv_text = str(result.pop("csv", ""))
            download_path = None
            if csv_text:
                download_path = self.directory / f"{job_id}.csv"
                download_path.write_text(csv_text, encoding="utf-8")
            result_path = self.directory / f"{job_id}.json"
            result_path.write_text(json.dumps(result, ensure_ascii=True), encoding="utf-8")
            self._update(
                job_id,
                status="completed",
                progress=100,
                stage="Complete",
                message="Results are ready",
                result=result,
                download_path=download_path,
            )
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            self._update(
                job_id,
                status="failed",
                stage="Failed",
                message="The search could not be completed",
                error=str(detail or exc)[:500],
            )

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = datetime.now(timezone.utc).isoformat()
