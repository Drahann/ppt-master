import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "ppt-master" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ppt_automation.cookbook import RANDOM_THEME_CHOICES, resolve_cookbook_selection  # noqa: E402


class CookbookSelectionTest(unittest.TestCase):
    def test_random_theme_pool_keeps_all_supported_theme_modes(self) -> None:
        self.assertEqual(
            RANDOM_THEME_CHOICES,
            (
                "default",
                "figma_65cm_default",
                "figma_colorblock_modern",
                "figma_lime_serif_grid",
            ),
        )

    def test_env_can_force_default_theme(self) -> None:
        with patch.dict(os.environ, {"PPT_MASTER_COOKBOOK": "default"}, clear=True):
            selection = resolve_cookbook_selection(None)
        self.assertEqual(selection.theme_id, "default")
        self.assertIsNone(selection.cookbook)
        self.assertFalse(selection.random)

    def test_explicit_cookbook_still_resolves(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            selection = resolve_cookbook_selection("figma_colorblock_modern")
        self.assertEqual(selection.theme_id, "figma_colorblock_modern")
        self.assertIsNotNone(selection.cookbook)
        self.assertFalse(selection.random)


if __name__ == "__main__":
    unittest.main()
