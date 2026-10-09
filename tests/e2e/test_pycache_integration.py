"""Observe the cache used by real pytest children in a complete campaign."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
from pydantic import BaseModel

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project, run_cli

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class WorkerCacheObservation(BaseModel):
    """Environment recorded while a real child executes a fixture test."""

    mutant: str
    prefix: str | None
    writing_disabled: bool
    pid: int


class CampaignCacheEvidence(BaseModel):
    """Run-bound verdicts and observations from the same fresh campaign."""

    run_id: str
    verdict_mutants: set[str]
    observations: list[WorkerCacheObservation]


@pytest.fixture(scope="module")
def cache_campaign(tmp_path_factory: pytest.TempPathFactory) -> CampaignCacheEvidence:
    """Run a campaign whose fixture records the actual child cache environment."""
    temporary = tmp_path_factory.mktemp("native-shared-cache")
    project = copy_project(SIMPLE_LIB, temporary)
    observations = temporary / "observations"
    observations.mkdir()
    # The observer is part of the fixture before staging and only records data.
    # Each pytest process writes its own mutant-bound file, without shared writes.
    (project / "conftest.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "from pydantic import BaseModel\n"
        "class Observation(BaseModel):\n"
        "    mutant: str\n"
        "    prefix: str | None\n"
        "    writing_disabled: bool\n"
        "    pid: int\n"
        "def pytest_runtest_call(item):\n"
        "    mutant = os.environ.get('MUTANT_UNDER_TEST', '')\n"
        "    observation = Observation(mutant=mutant, prefix=sys.pycache_prefix,\n"
        "        writing_disabled=sys.dont_write_bytecode, pid=os.getpid())\n"
        f"    directory = Path({str(observations)!r})\n"
        "    name = f'{os.getpid()}-{mutant}.json'\n"
        "    (directory / name).write_text(observation.model_dump_json(), encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = run_cli(project, "run", "--no-progress", timeout=900)
    assert result.returncode == 0, result.stdout + result.stderr
    db_path = project / ".mutmut-cache" / "mutmut-cache.db"
    with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as connection:
        run = connection.execute(
            "SELECT run_id, status FROM mutation_run ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        assert run is not None
        assert run[1] == "completed", run
        verdicts = connection.execute(
            "SELECT mutant_name, result_status, duration FROM mutation_run_mutant"
            " WHERE run_id = ? ORDER BY ordinal",
            (run[0],),
        ).fetchall()
    assert len(verdicts) >= 5, verdicts
    assert all(status in {"killed", "survived"} for _, status, _ in verdicts), verdicts
    assert all(duration is not None and duration > 0 for _, _, duration in verdicts), verdicts
    evidence = CampaignCacheEvidence(
        run_id=run[0],
        verdict_mutants={name for name, _, _ in verdicts},
        observations=[
            WorkerCacheObservation.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(observations.glob("*.json"))
        ],
    )
    (temporary / "campaign-cache-evidence.json").write_text(
        evidence.model_dump_json(indent=2), encoding="utf-8"
    )
    return evidence


class TestDispatchWorkerSharedPycache:
    """Bind the configured shared cache to actual worker execution and verdicts."""

    def test_worker_verdicts_use_observed_clean_cache(
        self, cache_campaign: CampaignCacheEvidence
    ) -> None:
        """Every recorded verdict has a real child using the clean phase cache."""
        workers = [
            observation
            for observation in cache_campaign.observations
            if observation.mutant in cache_campaign.verdict_mutants
        ]
        assert {worker.mutant for worker in workers} == cache_campaign.verdict_mutants
        clean = [
            observation for observation in cache_campaign.observations if not observation.mutant
        ]
        assert clean, cache_campaign
        clean_prefixes = {observation.prefix for observation in clean}
        assert len(clean_prefixes) == 1
        assert None not in clean_prefixes
        for worker in workers:
            assert worker.pid > 0
            assert worker.prefix in clean_prefixes, worker
            assert worker.writing_disabled is False, worker

    def test_worker_env_has_shared_pycache_during_run(
        self, cache_campaign: CampaignCacheEvidence
    ) -> None:
        """Stats and worker children preserve writable sharing across the run."""
        stats = [
            observation
            for observation in cache_campaign.observations
            if observation.mutant == "stats"
        ]
        assert stats, cache_campaign
        stats_prefixes = {observation.prefix for observation in stats}
        assert len(stats_prefixes) == 1
        assert None not in stats_prefixes
        workers = [
            observation
            for observation in cache_campaign.observations
            if observation.mutant in cache_campaign.verdict_mutants
        ]
        assert workers
        assert {worker.prefix for worker in workers} == stats_prefixes
        assert all(not observation.writing_disabled for observation in [*stats, *workers])
