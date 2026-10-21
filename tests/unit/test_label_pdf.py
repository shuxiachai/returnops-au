from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from returnops_domain.label_pdf import (  # noqa: E402
    MAX_PDF_BYTES, PDF_PROFILE_ID, LabelPdfFields, pdf_profile_spec, render_label_pdf,
)


class LabelPdfTests(unittest.TestCase):
    def assert_identifier_blocks(self, pdf, fields):
        reader = PdfReader(BytesIO(pdf), strict=True)
        self.assertEqual(len(reader.pages), 1)
        lines = reader.pages[0].extract_text().splitlines()
        expected = ["SIMULATED — NOT VALID FOR POSTAGE", "MOCK RETURN LABEL"]
        values = (fields.provider_label_id, fields.provider_return_id, fields.parcel_id)
        labels = ("Provider label ID", "Provider return ID", "Parcel ID")
        for label, value in zip(labels, values):
            chunks = [value[index:index + 40] for index in range(0, len(value), 40)]
            expected.extend((label, *chunks))
            # Reassemble only this field's ordered lines, not all document text.
            start = lines.index(label) + 1
            self.assertEqual("".join(lines[start:start + len(chunks)]), value)
        expected.append("This document is simulated and has no postage value.")
        self.assertEqual(lines, expected)

    def test_renders_deterministic_single_page_with_visible_marker(self):
        fields = LabelPdfFields("label_0123456789", "return_0123456789", "parcel_0123456789")
        first = render_label_pdf(fields)
        self.assertEqual(first, render_label_pdf(fields))
        self.assertLessEqual(len(first), MAX_PDF_BYTES)
        self.assertTrue(first.startswith(b"%PDF-1.4\n"))
        self.assertTrue(first.endswith(b"%%EOF\n"))
        reader = PdfReader(BytesIO(first), strict=True)
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(tuple(reader.pages[0].mediabox), (0, 0, 612, 792))
        text = reader.pages[0].extract_text()
        self.assertIn("SIMULATED — NOT VALID FOR POSTAGE", text)
        self.assertIn(fields.provider_label_id, text)
        self.assertIn(fields.provider_return_id, text)
        self.assertIn(fields.parcel_id, text)
        self.assert_identifier_blocks(first, fields)

    def test_longest_valid_identifiers_wrap_and_stay_within_profile_limit(self):
        original_value = "a" + "Z9_-" * 19 + "x" * 3
        mixed_value = "Az09_-" * 13 + "Z9"
        cases = (
            LabelPdfFields(original_value, original_value, original_value),
            LabelPdfFields("W" * 80, "M" * 80, mixed_value),
        )
        for fields in cases:
            with self.subTest(fields=cases.index(fields)):
                for value in (fields.provider_label_id, fields.provider_return_id, fields.parcel_id):
                    self.assertEqual(len(value), 80)
                pdf = render_label_pdf(fields)
                self.assertLessEqual(len(pdf), MAX_PDF_BYTES)
                self.assert_identifier_blocks(pdf, fields)

    def test_identifier_length_and_line_break_boundaries_preserve_every_character(self):
        for length in (3, 39, 40, 41, 79, 80):
            with self.subTest(length=length):
                fields = LabelPdfFields("W" * length, "M" * length, "a" + "_" * (length - 1))
                self.assert_identifier_blocks(render_label_pdf(fields), fields)

    def test_every_allowed_identifier_character_is_preserved(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        for character in alphabet:
            with self.subTest(character=character):
                value = "a" + character * 79
                fields = LabelPdfFields(value, value, value)
                self.assert_identifier_blocks(render_label_pdf(fields), fields)

    def test_rejects_invalid_or_non_string_identifiers_without_echoing_value(self):
        class StringSubclass(str):
            pass

        invalid = (
            "", "ab", "a" * 81, "abc!", "ümlaut", "_abc", "-abc", "a b",
            "abc\n", "abc\r", "a\tbc", "a\x00bc", "a/b", "a\\b", "a(b", "a)b", "a%b",
            42, True, None, b"abc", ["abc"], StringSubclass("abc"),
        )
        for position in range(3):
            for value in invalid:
                with self.subTest(position=position, value=repr(value)):
                    values = ["label_ok_1", "return_ok_1", "parcel_ok_1"]
                    values[position] = value
                    with self.assertRaisesRegex(ValueError, r"^Invalid label PDF input$"):
                        render_label_pdf(LabelPdfFields(*values))

    def test_rejects_other_input_containers_with_safe_error(self):
        for value in (None, object(), {"provider_label_id": "abc"}, ("abc", "def", "ghi")):
            with self.subTest(type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, r"^Invalid label PDF input$"):
                    render_label_pdf(value)

    def test_fields_are_frozen_slotted_and_do_not_echo_identifiers_in_repr(self):
        fields = LabelPdfFields("label_sensitive_1", "return_sensitive_1", "parcel_sensitive_1")
        with self.assertRaises(FrozenInstanceError):
            fields.parcel_id = "replacement"
        self.assertFalse(hasattr(fields, "__dict__"))
        for value in (fields.provider_label_id, fields.provider_return_id, fields.parcel_id):
            self.assertNotIn(value, repr(fields))

    def test_profile_is_fresh_and_fixed(self):
        first = pdf_profile_spec()
        second = pdf_profile_spec()
        self.assertIsNot(first, second)
        self.assertEqual(first["id"], PDF_PROFILE_ID)
        self.assertEqual(first["limits"], {"pages": 1, "max_bytes": MAX_PDF_BYTES})
        self.assertEqual(first["template"][0]["text"], "SIMULATED — NOT VALID FOR POSTAGE")
        self.assertEqual(first["line_wrap_characters"], 40)
        first["limits"]["max_bytes"] = 1
        first["template"][0]["text"] = "changed"
        first["page"]["count"] = 2
        first["font"]["base_font"] = "changed"
        first["serializer"]["header_hex"] = "00"
        self.assertEqual(second, pdf_profile_spec())
        self.assertEqual(pdf_profile_spec()["limits"]["max_bytes"], MAX_PDF_BYTES)

    def test_complete_profile_and_previously_rendered_bytes_are_golden_pair(self):
        profile = pdf_profile_spec()
        self.assertEqual(set(profile), {
            "id", "page", "font", "line_wrap_characters", "line_spacing_points",
            "string_encoding", "template", "serializer", "limits",
        })
        self.assertEqual(len(profile["template"]), 9)
        for element in profile["template"]:
            content = "field" if "field" in element else "text"
            self.assertEqual(set(element), {content, "x", "y", "size", "color"})
        self.assertEqual(len(profile["serializer"]["objects"]), 5)
        # Regression fixture only; the production profile digest stays in core.
        snapshot = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
                         "c9e9e3c4a970329095994bd157cf1ef64dfd47cfd0bc2b1878651c33b35be3d7")
        # These PDF hashes predate the profile refactor and were actually rendered.
        fixtures = (
            (LabelPdfFields("W" * 80, "M" * 80, "W" * 80),
             "b681db13021670582a07a711d4dac14f2c909927a1658b39a13aa7973c8bdda4"),
            (LabelPdfFields("a_1", "b-2", "C03"),
             "e0607c8bcc65fbb32b3254b5c3c2efa4462a660ea7fc06e3f75ccc77727e3a87"),
        )
        for fields, expected_hash in fixtures:
            self.assertEqual(hashlib.sha256(render_label_pdf(fields)).hexdigest(), expected_hash)

    def assert_profile_change_affects_pdf(self, path, value):
        fields = LabelPdfFields("W" * 80, "M" * 80, "a" + "Z9_-" * 19 + "xxx")
        original = pdf_profile_spec()
        changed = deepcopy(original)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        self.assertNotEqual(changed, original)
        original_pdf = render_label_pdf(fields)
        # Patching this internal factory is test instrumentation, not a public
        # caller-supplied profile or a new rendering capability.
        with patch("returnops_domain.label_pdf.pdf_profile_spec", return_value=changed):
            changed_pdf = render_label_pdf(fields)
        self.assertNotEqual(changed_pdf, original_pdf)
        return changed_pdf

    def test_every_template_value_is_consumed_by_renderer(self):
        profile = pdf_profile_spec()
        for index, element in enumerate(profile["template"]):
            for key, value in element.items():
                if key == "text":
                    replacement = value + "X"
                elif key == "field":
                    replacement = "parcel_id" if value != "parcel_id" else "provider_label_id"
                elif key == "color":
                    replacement = "0 0 1 rg"
                else:
                    replacement = value + 1
                with self.subTest(element=index, property=key):
                    self.assert_profile_change_affects_pdf(("template", index, key), replacement)

    def test_every_serialization_value_is_consumed_by_renderer(self):
        serializer = pdf_profile_spec()["serializer"]
        changes = {
            "encoding": "utf-16be",
            "header_hex": serializer["header_hex"].replace("312e34", "312e35"),
            "text_operator": serializer["text_operator"] + "\n",
            "line_separator": "\n\n",
            "stream_terminator": "\n\n",
            "first_object_number": 2,
            "object": serializer["object"] + "\n",
            "xref_header": "\n" + serializer["xref_header"],
            "xref_free_entries": ("0000000000 65534 f \n",),
            "xref_entry": "{offset:010d} 00000 n \r\n",
            "trailer": serializer["trailer"] + "\n",
        }
        self.assertEqual(set(changes) | {"objects"}, set(serializer))
        for key, value in changes.items():
            with self.subTest(property=key):
                self.assert_profile_change_affects_pdf(("serializer", key), value)
        for index in range(5):
            objects = list(serializer["objects"])
            objects[index] += "\n"
            with self.subTest(object=index):
                self.assert_profile_change_affects_pdf(("serializer", "objects"), tuple(objects))

    def test_layout_encoding_and_limits_are_consumed_by_renderer(self):
        changes = (
            (("page", "width_points"), 613),
            (("page", "height_points"), 793),
            (("font", "resource"), "F2"),
            (("font", "subtype"), "Type0"),
            (("font", "base_font"), "Courier"),
            (("font", "encoding"), "MacRomanEncoding"),
            (("line_wrap_characters",), 39),
            (("line_spacing_points",), 17),
            (("string_encoding", "codec"), "utf-8"),
            (("string_encoding", "uppercase_hex"), False),
        )
        for path, value in changes:
            with self.subTest(property=path):
                pdf = self.assert_profile_change_affects_pdf(path, value)
                if path == ("page", "width_points"):
                    self.assertEqual(PdfReader(BytesIO(pdf), strict=True).pages[0].mediabox.width, 613)
                elif path == ("font", "base_font"):
                    self.assertEqual(PdfReader(BytesIO(pdf), strict=True).pages[0]["/Resources"]["/Font"]["/F1"]["/BaseFont"], "/Courier")
        for path in (("limits", "max_bytes"), ("limits", "pages"), ("page", "count")):
            profile = pdf_profile_spec()
            profile[path[0]][path[1]] = 0
            with self.subTest(limit=path):
                with patch("returnops_domain.label_pdf.pdf_profile_spec", return_value=profile):
                    with self.assertRaisesRegex(ValueError, r"^Invalid label PDF input$"):
                        render_label_pdf(LabelPdfFields("abc", "def", "ghi"))


if __name__ == "__main__":
    unittest.main()
