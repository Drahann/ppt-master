import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "ppt-master" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ppt_automation.planner import SpecParseError, extract_json_marker, resolve_spec_retries  # noqa: E402


class PlannerSpecRetryTest(unittest.TestCase):
    def test_invalid_marked_json_is_retryable_spec_parse_error(self) -> None:
        response = "---DESIGN_PLAN_JSON_START---\n{\"title\":\"bad\x01json\"}\n---DESIGN_PLAN_JSON_END---"

        with self.assertRaises(SpecParseError):
            extract_json_marker(response, "---DESIGN_PLAN_JSON_START---", "---DESIGN_PLAN_JSON_END---")

    def test_spec_retries_env_default_and_override(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_spec_retries(), 2)
        with patch.dict(os.environ, {"PPT_MASTER_SPEC_RETRIES": "4"}, clear=True):
            self.assertEqual(resolve_spec_retries(), 4)
        with patch.dict(os.environ, {"PPT_MASTER_SPEC_RETRIES": "-1"}, clear=True):
            self.assertEqual(resolve_spec_retries(), 0)


if __name__ == "__main__":
    unittest.main()
