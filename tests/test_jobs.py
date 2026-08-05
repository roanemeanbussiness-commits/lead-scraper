from __future__ import annotations

import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from lead_scraper.jobs import JobManager, SearchJob


class JobManagerTests(unittest.TestCase):
    def test_background_job_reports_progress_and_writes_download(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = JobManager(Path(tmp))

            def runner(progress):
                progress(55, "Ranking", "Scoring companies")
                return {"match_count": 1, "csv": "business_name,verified_email\nApex,a@apex.com\n"}

            job = manager.submit("lookalikes", runner)
            for _attempt in range(100):
                current = manager.get(job.id)
                assert current is not None
                if current.status in {"completed", "failed"}:
                    break
                time.sleep(0.01)

            self.assertEqual("completed", current.status)
            self.assertEqual(100, current.progress)
            self.assertEqual(1, current.result["match_count"])
            self.assertTrue(current.download_path.exists())

    def test_background_job_logs_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("lead_scraper.jobs.LOGGER.exception") as log:
            manager = JobManager(Path(tmp))

            def runner(_progress):
                raise ValueError("bad filters")

            job = SearchJob(id="failed-job", kind="ocean")
            manager._jobs[job.id] = job
            manager._run(job.id, runner)
            current = manager.get(job.id)
            assert current is not None

            self.assertEqual("failed", current.status)
            self.assertEqual("bad filters", current.error)
            log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
