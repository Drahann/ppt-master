from __future__ import annotations

import sys
import unittest
from pathlib import Path

from api_service.svg_scheduler import compute_scheduler_grants


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_SCRIPTS_DIR = REPO_ROOT / "skills" / "ppt-master" / "scripts"
if str(RUNNER_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_SCRIPTS_DIR))

from qwen_ppt_runner import SlidePlanEntry, split_plan_into_batches  # type: ignore  # noqa: E402


class ComputeSchedulerGrantsTests(unittest.TestCase):
    def test_distributes_base_share_and_remainder_without_wasting_slots(self) -> None:
        requested = {f"job_{index:02d}": 7 for index in range(25)}
        demand = {f"job_{index:02d}": 6 for index in range(25)}
        oldest = {job_id: float(index) for index, job_id in enumerate(requested)}
        history = {job_id: 0 for job_id in requested}

        decision = compute_scheduler_grants(
            total_slots=72,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        grants = decision.granted_slots_by_job
        self.assertEqual(decision.base_share, 2)
        self.assertEqual(decision.remainder_slots, 22)
        self.assertEqual(sum(grants.values()), 72)
        self.assertEqual(sum(1 for value in grants.values() if value == 3), 22)
        self.assertEqual(sum(1 for value in grants.values() if value == 2), 3)
        self.assertEqual(decision.underutilized_slots, 0)

    def test_respects_requested_workers_and_exhausted_batches(self) -> None:
        requested = {
            "job_a": 7,
            "job_b": 7,
            "job_c": 2,
        }
        demand = {
            "job_a": 1,
            "job_b": 4,
            "job_c": 2,
        }
        oldest = {
            "job_a": 1.0,
            "job_b": 2.0,
            "job_c": 3.0,
        }
        history = {
            "job_a": 10,
            "job_b": 2,
            "job_c": 1,
        }

        decision = compute_scheduler_grants(
            total_slots=10,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        self.assertEqual(decision.granted_slots_by_job["job_a"], 1)
        self.assertEqual(decision.granted_slots_by_job["job_b"], 4)
        self.assertEqual(decision.granted_slots_by_job["job_c"], 2)
        self.assertEqual(sum(decision.granted_slots_by_job.values()), 7)
        self.assertEqual(decision.underutilized_slots, 3)

    def test_requested_worker_limit_caps_distribution(self) -> None:
        requested = {
            "job_a": 1,
            "job_b": 3,
            "job_c": 7,
        }
        demand = {
            "job_a": 6,
            "job_b": 6,
            "job_c": 6,
        }
        oldest = {
            "job_a": 1.0,
            "job_b": 2.0,
            "job_c": 3.0,
        }
        history = {
            "job_a": 0,
            "job_b": 0,
            "job_c": 0,
        }

        decision = compute_scheduler_grants(
            total_slots=10,
            job_requested_workers=requested,
            job_total_demand=demand,
            job_oldest_pending_at=oldest,
            historical_grants=history,
        )

        self.assertEqual(decision.granted_slots_by_job["job_a"], 1)
        self.assertEqual(decision.granted_slots_by_job["job_b"], 3)
        self.assertEqual(decision.granted_slots_by_job["job_c"], 6)
        self.assertEqual(sum(decision.granted_slots_by_job.values()), 10)


class AnchorEvenBatchingTests(unittest.TestCase):
    def test_anchor_even_splits_32_pages_into_expected_groups(self) -> None:
        plan = [
            SlidePlanEntry(
                index=index + 1,
                filename=f"slide_{index + 1:02d}.svg",
                heading=f"slide-{index + 1}",
                kind="content",
                source_h2=None,
                source_h3=None,
            )
            for index in range(32)
        ]

        batches = split_plan_into_batches(plan, 5, "anchor_even")

        self.assertEqual([len(batch) for batch in batches], [2, 6, 6, 6, 6, 6])
        self.assertEqual(batches[0][0].filename, "slide_01.svg")
        self.assertEqual(batches[-1][-1].filename, "slide_32.svg")


if __name__ == "__main__":
    unittest.main()
