"""Regression tests for failure detection in the checker, not product tests."""
import base64
import os
from pathlib import Path
import tempfile
import unittest
import zlib

from check import (BASE64_ALPHABET, UML_ALPHABET, CheckError, allocation_rows,
                   check_documents, check_svg_pair, composite_structure, markdown_destinations,
                   scenario_ids, validate_wbs)


def svg_for(source):
    compressor = zlib.compressobj(wbits=-15)
    encoded = base64.b64encode(compressor.compress(source.encode()) + compressor.flush()).decode().rstrip("=")
    encoded = encoded.translate(str.maketrans(BASE64_ALPHABET, UML_ALPHABET))
    return f'<svg xmlns="http://www.w3.org/2000/svg"><?plantuml-src {encoded}?></svg>'


class CheckerTests(unittest.TestCase):
    def test_mtime_and_line_endings_do_not_invalidate_matching_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "model.puml"
            source.write_bytes(b"@startuml\r\nAlice -> Bob\r\n@enduml\r\n")
            svg = source.with_suffix(".svg")
            svg.write_text(svg_for("Alice -> Bob"), encoding="utf-8")
            os.utime(svg, (1, 1))
            check_svg_pair(source)
            source.write_text("@startuml\nAlice -> Charlie\n@enduml\n", encoding="utf-8")
            with self.assertRaisesRegex(CheckError, "source differs"):
                check_svg_pair(source)

    def test_missing_source_metadata_is_not_called_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "model.puml"
            source.write_text("@startuml\nAlice -> Bob\n@enduml", encoding="utf-8")
            source.with_suffix(".svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
            with self.assertRaisesRegex(CheckError, "lacks supported"):
                check_svg_pair(source)

    def test_scenario_registry_expands_without_a_frozen_count(self):
        content = "\n".join(f"| MA-T{number:02d} scenario | evidence |" for number in range(1, 17))
        self.assertEqual(len(scenario_ids(content, "MA")), 16)
        with self.assertRaisesRegex(CheckError, "duplicate"):
            scenario_ids(content + "\n| MA-T16 duplicate |", "MA")
        with self.assertRaisesRegex(CheckError, "Undeclared"):
            scenario_ids(content + "\nSee MA-T99", "MA")

    def test_wbs_tracks_ownership_dependencies_not_prose_or_row_order(self):
        first = "| F.01 | A | C | — | — | old title | old acceptance |\n| F.02 | A | C | F.01 | — | title | acceptance |"
        second = "| F.02 | A | C | F.01 | — | revised | revised |\n| F.01 | A | C | — | — | changed | changed |"
        self.assertEqual(allocation_rows(first), allocation_rows(second))
        validate_wbs(allocation_rows(first))
        self.assertNotEqual(allocation_rows(first), allocation_rows(first.replace("| A | C |", "| B | A |", 1)))
        with self.assertRaisesRegex(CheckError, "cycle"):
            validate_wbs(allocation_rows(first.replace("| — | — |", "| F.02 | — |", 1)))
        with self.assertRaisesRegex(CheckError, "unknown"):
            validate_wbs(allocation_rows(first.replace("| F.01 | — |", "| F.99 | — |")))
        with self.assertRaisesRegex(CheckError, "unrecognised"):
            validate_wbs(allocation_rows(first.replace("| F.01 | — |", "| typo | — |")))

    def test_links_ignore_fenced_and_inline_code_but_handle_references(self):
        text = '[doc](../docs/a.md#part) ![view](<image name.svg>)\n`[code](absent.md)`\n```md\n[example](absent.md)\n```\n[ref]: b.md "title"'
        self.assertEqual(list(markdown_destinations(text)), ["../docs/a.md#part", "image name.svg", "b.md"])

    def test_missing_local_link_is_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / "README.md").write_text('[missing](missing.md)', encoding="utf-8")
            with self.assertRaisesRegex(CheckError, "missing local target"):
                check_documents(root)

    def test_delegation_and_assembly_scope_and_polarity(self):
        source = '''component "Whole" as Whole {
 portin "entry (P)" as ENTRY
 component "left : Left [1]" as Left {
  portin "entry (P)" as LEFT_IN
  portout "other (R)" as LEFT_OUT
 }
 component "right : Right [1]" as Right {
  portin "other (P)" as RIGHT_IN
 }
}
ENTRY -- LEFT_IN : D01
LEFT_OUT -- RIGHT_IN : A01
'''
        ports, edges = composite_structure(source)
        self.assertEqual((len(ports), len(edges)), (4, 2))
        with self.assertRaisesRegex(CheckError, "assembly"):
            composite_structure(source.replace('other (R)', 'other (P)'))
        with self.assertRaisesRegex(CheckError, "delegation"):
            composite_structure(source.replace('LEFT_OUT -- RIGHT_IN : A01', 'LEFT_OUT -- RIGHT_IN : D02'))
        with self.assertRaisesRegex(CheckError, "undeclared"):
            composite_structure(source.replace('RIGHT_IN : A01', 'MISSING : A01'))


if __name__ == "__main__":
    unittest.main()
