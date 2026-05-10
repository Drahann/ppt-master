import os
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "ppt-master" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ppt_automation.planner import (  # noqa: E402
    DEFAULT_SPEC_REDUCER_MAX_TOKENS,
    SPEC_REDUCER_MAX_TOKENS_ENV,
    resolve_spec_reducer_max_tokens,
)


class PlannerEnvTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop(SPEC_REDUCER_MAX_TOKENS_ENV, None)

    def test_uses_default_reducer_token_budget(self) -> None:
        os.environ.pop(SPEC_REDUCER_MAX_TOKENS_ENV, None)

        self.assertEqual(resolve_spec_reducer_max_tokens(), DEFAULT_SPEC_REDUCER_MAX_TOKENS)

    def test_reads_reducer_token_budget_from_env(self) -> None:
        os.environ[SPEC_REDUCER_MAX_TOKENS_ENV] = "160000"

        self.assertEqual(resolve_spec_reducer_max_tokens(), 160000)

    def test_clamps_reducer_token_budget_to_deepseek_v4_output_limit(self) -> None:
        os.environ[SPEC_REDUCER_MAX_TOKENS_ENV] = "999999"

        self.assertEqual(resolve_spec_reducer_max_tokens(), 384000)


if __name__ == "__main__":
    unittest.main()
