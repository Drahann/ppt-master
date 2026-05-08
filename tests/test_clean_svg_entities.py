import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills" / "ppt-master" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from clean_svg_entities import clean_svg_entities  # noqa: E402


class CleanSvgEntitiesTest(unittest.TestCase):
    def test_repairs_broken_inline_text_and_tspan_tags(self) -> None:
        raw = """<svg xmlns="http://www.w3.org/2000/svg">
  <text x="10" y="20">alpha?/text>
  <text x="10" y="40">beta < tspan fill="#1D4ED8">85%</tspan>?/text>
  <text x="10" y="60">gamma? tspan fill="#0F766E">20ms</tspan>?/text>
</svg>"""

        cleaned = clean_svg_entities(raw)

        ET.fromstring(cleaned)
        self.assertIn("alpha?</text>", cleaned)
        self.assertIn("beta <tspan", cleaned)
        self.assertIn("gamma?<tspan", cleaned)


if __name__ == "__main__":
    unittest.main()
