"""Regression tests for failure detection in the checker, not product tests."""
import base64
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zlib

from check import (BASE64_ALPHABET, UML_ALPHABET, ROOT, CheckError, allocation_rows,
                   check_documents, check_operation_statuses, check_svg_pair, composite_structure, markdown_destinations,
                   check_shared, scenario_ids, validate_wbs)


def svg_for(source):
    compressor = zlib.compressobj(wbits=-15)
    encoded = base64.b64encode(compressor.compress(source.encode()) + compressor.flush()).decode().rstrip("=")
    encoded = encoded.translate(str.maketrans(BASE64_ALPHABET, UML_ALPHABET))
    return f'<svg xmlns="http://www.w3.org/2000/svg"><?plantuml-src {encoded}?></svg>'


class CheckerTests(unittest.TestCase):
    def test_operation_status_vocabulary_catches_stale_or_missing_definition(self):
        schema = json.loads((ROOT / "contracts/v1/schemas.json").read_text(encoding="utf-8"))
        expected = set(schema["$defs"]["OperationAttempt"]["properties"]["status"]["enum"])
        row = "| `OperationStatus` | " + ", ".join(f"`{state}`" for state in sorted(expected)) + " |"
        check_operation_statuses(row, expected)
        with self.assertRaisesRegex(CheckError, "differs from schema"):
            check_operation_statuses(row.replace("`EXECUTING`", "`RUNNING`"), expected)
        with self.assertRaisesRegex(CheckError, "definition row"):
            check_operation_statuses("", expected)

    def test_indented_extra_connector_cannot_hide_from_registry_or_boundary(self):
        source = ROOT / "docs/diagrams/shared/governed-case-composite.puml"
        registry = ROOT / "docs/13-shared-composite-structure.md"
        source_text = source.read_text(encoding="utf-8")
        registry_text = registry.read_text(encoding="utf-8")
        for connector in ("AN_DOMAIN -- REPO_CASE : A99", "    AN_DOMAIN -- REPO_CASE : A99",
                          "\tAN_DOMAIN -- REPO_CASE : A99", "AN_DOMAIN--REPO_CASE:A99"):
            for registered in (False, True):
                with self.subTest(connector=connector, registered=registered):
                    changed = source_text.replace("\nlegend bottom", f"\n{connector}\n\nlegend bottom")
                    def changed_read(path):
                        if path == source:
                            return changed
                        if path == registry and registered:
                            return registry_text + "\n| A99 | test-only direct repository connection |\n"
                        return path.read_text(encoding="utf-8-sig")
                    with patch("check.read", side_effect=changed_read):
                        message = "REPO_CASE neighbors" if registered else "Connector registry mismatch"
                        with self.assertRaisesRegex(CheckError, message):
                            check_shared(ROOT)

    def test_suspected_unsupported_connectors_fail_instead_of_disappearing(self):
        source = (ROOT / "docs/diagrams/shared/governed-case-composite.puml").read_text(encoding="utf-8")
        for connector in ("    AN_DOMAIN -- REPO_CASE", "AN_DOMAIN -- REPO_CASE : wrong",
                          "AN_DOMAIN --> REPO_CASE : A99", "AN_DOMAIN ..> REPO_CASE : A99",
                          "AN_DOMAIN -[#red]-> REPO_CASE : A99", "AN_DOMAIN -right- REPO_CASE : A99",
                          '"AN_DOMAIN" -- REPO_CASE : A99', "AN_DOMAIN -- MISSING : A99"):
            with self.subTest(connector=connector):
                changed = source.replace("\nlegend bottom", f"\n{connector}\n\nlegend bottom")
                with self.assertRaisesRegex(CheckError, "unsupported connector|undeclared connector endpoint"):
                    composite_structure(changed)

    def test_connector_indentation_preserves_shape_and_legend_is_not_code(self):
        source = (ROOT / "docs/diagrams/shared/governed-case-composite.puml").read_text(encoding="utf-8")
        expected = composite_structure(source)
        indented = "\n".join("\t" + line if " -- " in line else line for line in source.splitlines())
        self.assertEqual(composite_structure(indented), expected)
        prose = source.replace("\nlegend bottom", "\n' AN_DOMAIN --> REPO_CASE : comment\nlegend bottom\nAN_DOMAIN --> REPO_CASE : prose")
        self.assertEqual(composite_structure(prose), expected)
        with self.assertRaisesRegex(CheckError, "Unclosed composite legend"):
            composite_structure(source.replace("endlegend", ""))

    def test_other_shared_views_do_not_hide_or_inflate_composite_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shared = root / "docs/diagrams/shared"
            shared.mkdir(parents=True)
            for source in (ROOT / "docs/diagrams/shared").glob("*-composite.puml"):
                shutil.copyfile(source, shared / source.name)
            shutil.copyfile(ROOT / "docs/13-shared-composite-structure.md",
                            root / "docs/13-shared-composite-structure.md")
            (shared / "package-dependencies.puml").write_text(
                '@startuml\npackage "Planned" {}\n@enduml\n', encoding="utf-8")
            self.assertIn("3 CS views", check_shared(root))
            # Other diagrams cannot substitute for a missing protected CS view.
            (shared / "governed-case-composite.puml").unlink()
            with self.assertRaises(CheckError):
                check_shared(root)

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
