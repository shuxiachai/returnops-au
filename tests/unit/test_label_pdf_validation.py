"""Canonical-byte validation and zero-render guards; all fixture creation is outside guards."""

from contextlib import ExitStack, contextmanager
import hashlib
from io import BytesIO
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from returnops_domain import label_pdf as renderer  # noqa: E402
from returnops_domain.label_pdf import LabelPdfFields  # noqa: E402
from returnops_domain.label_pdf_validation import verify_label_pdf  # noqa: E402


# Preserve aliases before any patch, so code-object instrumentation covers
# exactly the path that patching only a module attribute would miss.
_RENDER_ALIAS = renderer.render_label_pdf
_TEXT_ALIAS = renderer._text_line
_ASSEMBLY_ALIAS = renderer._assemble_pdf
_RENDER_CODES = {function.__code__ for function in (_RENDER_ALIAS, _TEXT_ALIAS, _ASSEMBLY_ALIAS)}
_SAFE_ERROR = "Invalid fixed-profile label PDF"


@contextmanager
def _forbid_rendering():
    observed = []
    previous_profiler = sys.getprofile()

    def guard(frame, event, argument):
        if event == "call" and frame.f_code in _RENDER_CODES:
            observed.append(frame.f_code.co_name)
            raise AssertionError("Actual renderer code invoked")

    with ExitStack() as stack:
        for name in ("render_label_pdf", "_text_line", "_assemble_pdf"):
            stack.enter_context(patch.object(renderer, name, side_effect=AssertionError("Renderer entry invoked")))
        try:
            sys.setprofile(guard)
            yield observed
        finally:
            sys.setprofile(previous_profiler)
    if observed:
        raise AssertionError("Actual renderer code invoked")


def _object_bodies(pdf):
    return {int(number): body for number, body in re.findall(
        rb"(?m)^([1-9][0-9]*) 0 obj\n(.*?)\nendobj\n", pdf, re.DOTALL,
    )}


def _stream(pdf):
    body = _object_bodies(pdf)[5]
    return body[body.index(b"stream\n") + len(b"stream\n"):-len(b"endstream")]


def _rewrite_fixture(pdf, *, stream=None, objects=None, order=None, extra=None, header_extra=b""):
    """TEST ONLY: repair lengths/offsets after deliberate semantic corruption.

    This mutates existing fixture bytes. It is never used by the production
    verifier, and always runs before zero-render verification guards begin.
    """
    bodies = _object_bodies(pdf)
    if stream is not None:
        bodies[5] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"
    bodies.update(objects or {})
    bodies.update(extra or {})
    order = sorted(bodies) if order is None else order
    output = bytearray(pdf[:pdf.index(b"1 0 obj\n")] + header_extra)
    offsets = {}
    for number in order:
        offsets[number] = len(output)
        output.extend(str(number).encode("ascii") + b" 0 obj\n" + bodies[number] + b"\nendobj\n")
    xref = len(output)
    count = max(bodies) + 1
    output.extend(f"xref\n0 {count}\n0000000000 65535 f \n".encode("ascii"))
    for number in range(1, count):
        output.extend(f"{offsets[number]:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def _replace_text(stream, original, replacement):
    old = b"<" + original.encode("cp1252").hex().upper().encode("ascii") + b"> Tj"
    new = b"<" + replacement.encode("cp1252").hex().upper().encode("ascii") + b"> Tj"
    assert old in stream
    return stream.replace(old, new)


class LabelPdfValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fields = LabelPdfFields("label_0123456789", "return_0123456789", "parcel_0123456789")
        cls.pdf = _RENDER_ALIAS(cls.fields)
        cls.long_fields = LabelPdfFields("W" * 80, "M" * 80, "W" * 80)
        cls.long_pdf = _RENDER_ALIAS(cls.long_fields)

    def assert_valid_without_rendering(self, content, fields):
        with _forbid_rendering() as observed:
            self.assertIsNone(verify_label_pdf(content, fields))
        self.assertEqual(observed, [])

    def assert_invalid_without_rendering(self, content, fields=None):
        fields = self.fields if fields is None else fields
        with _forbid_rendering() as observed:
            with self.assertRaisesRegex(ValueError, r"^Invalid fixed-profile label PDF$") as error:
                verify_label_pdf(content, fields)
        self.assertEqual(str(error.exception), _SAFE_ERROR)
        self.assertEqual(observed, [])

    def test_original_visual_goldens_validate_without_renderer_calls(self):
        minimum = LabelPdfFields("a_1", "b-2", "C03")
        mixed = LabelPdfFields("a" + "Z9_-" * 19 + "xxx", "Az09_-" * 13 + "Z9",
                               "A" + "abcdefghijklmnopqrstuvwxyz0123456789_-" * 2 + "zzz")
        fixtures = (
            (self.long_pdf, self.long_fields, "b681db13021670582a07a711d4dac14f2c909927a1658b39a13aa7973c8bdda4"),
            (_RENDER_ALIAS(minimum), minimum, "e0607c8bcc65fbb32b3254b5c3c2efa4462a660ea7fc06e3f75ccc77727e3a87"),
            (_RENDER_ALIAS(mixed), mixed, "8bea25729063ff3871409960cce68ebfc68aceb314877f56108feb141ecb3de9"),
        )
        for pdf, fields, expected_hash in fixtures:
            with self.subTest(golden=expected_hash):
                self.assertEqual(hashlib.sha256(pdf).hexdigest(), expected_hash)
                self.assert_valid_without_rendering(pdf, fields)

    def test_id_length_and_wrap_boundaries(self):
        fixtures = []
        for length in (3, 39, 40, 41, 79, 80):
            fields = LabelPdfFields("W" * length, "M" * length, "a" + "_" * (length - 1))
            fixtures.append((length, fields, _RENDER_ALIAS(fields)))
        for length, fields, pdf in fixtures:
            with self.subTest(length=length):
                self.assert_valid_without_rendering(pdf, fields)

    def test_all_allowed_identifier_characters(self):
        fixtures = []
        for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-":
            fields = LabelPdfFields("a" + character * 79, "b" + character * 79, "C" + character * 79)
            fixtures.append((character, fields, _RENDER_ALIAS(fields)))
        for character, fields, pdf in fixtures:
            with self.subTest(character=character):
                self.assert_valid_without_rendering(pdf, fields)

    def test_each_original_ledger_id_is_required(self):
        for position in range(3):
            values = [self.fields.provider_label_id, self.fields.provider_return_id, self.fields.parcel_id]
            values[position] = "different_original_id"
            with self.subTest(field=position):
                self.assert_invalid_without_rendering(self.pdf, LabelPdfFields(*values))

    def test_invalid_input_types_and_identifiers_have_fixed_safe_errors(self):
        class TextSubclass(str):
            pass

        class BytesSubclass(bytes):
            pass

        for content in (None, "PDF", bytearray(self.pdf), memoryview(self.pdf), BytesSubclass(self.pdf), b"", b"x" * 65537):
            with self.subTest(content_type=type(content).__name__):
                self.assert_invalid_without_rendering(content)
        for fields in (object(), {"provider_label_id": "abc"}, ("abc", "def", "ghi")):
            with self.subTest(fields_type=type(fields).__name__):
                self.assert_invalid_without_rendering(self.pdf, fields)
        for position in range(3):
            for value in ("ab", "a" * 81, "private bad value", "_abc", "-abc", "abc\n", "ümlaut", None, 7, b"abc", TextSubclass("abc")):
                values = ["label_ok", "return_ok", "parcel_ok"]
                values[position] = value
                with self.subTest(field=position, invalid_type=type(value).__name__):
                    self.assert_invalid_without_rendering(self.pdf, LabelPdfFields(*values))
        with _forbid_rendering():
            with self.assertRaisesRegex(ValueError, r"^Invalid fixed-profile label PDF$"):
                verify_label_pdf(self.pdf, None)

    def test_self_consistent_text_font_layout_and_encoding_forgery_is_rejected(self):
        stream = _stream(self.pdf)
        bodies = _object_bodies(self.pdf)
        streams = {
            "original_label": _replace_text(stream, self.fields.provider_label_id, "label_forged"),
            "original_return": _replace_text(stream, self.fields.provider_return_id, "return_forged"),
            "original_parcel": _replace_text(stream, self.fields.parcel_id, "parcel_forged"),
            "watermark": _replace_text(stream, "SIMULATED — NOT VALID FOR POSTAGE", "SIMULATED - NOT VALID FOR POSTAGE"),
            "title": _replace_text(stream, "MOCK RETURN LABEL", "OTHER RETURN LABEL"),
            "field_label": _replace_text(stream, "Provider label ID", "Provider other ID"),
            "footer": _replace_text(stream, "This document is simulated and has no postage value.", "This document has postage value."),
            "font_size": stream.replace(b"/F1 20 Tf", b"/F1 21 Tf"),
            "color": stream.replace(b"0.75 0 0 rg", b"0.5 0 0 rg"),
            "x": stream.replace(b"1 0 0 1 56 734 Tm", b"1 0 0 1 57 734 Tm"),
            "y": stream.replace(b"1 0 0 1 56 622 Tm", b"1 0 0 1 56 621 Tm"),
            "matrix": stream.replace(b"1 0 0 1 56 734 Tm", b"2 0 0 1 56 734 Tm"),
            "noncanonical_hex_case": re.sub(rb"<([0-9A-F]+)> Tj", lambda match: b"<" + match[1].lower() + b"> Tj", stream),
            "extra_operator_whitespace": stream.replace(b"> Tj", b">  Tj"),
            "extra_operator": b"q\n" + stream + b"Q\n",
            "comment": b"% forbidden comment\n" + stream,
        }
        fixtures = [(name, _rewrite_fixture(self.pdf, stream=value)) for name, value in streams.items()]
        fixtures.extend((
            ("font_face", _rewrite_fixture(self.pdf, objects={4: bodies[4].replace(b"/Helvetica", b"/Courier")})),
            ("font_encoding", _rewrite_fixture(self.pdf, objects={4: bodies[4].replace(b"/WinAnsiEncoding", b"/MacRomanEncoding")})),
            ("page_size", _rewrite_fixture(self.pdf, objects={3: bodies[3].replace(b"612 792", b"613 792")})),
            ("font_resource", _rewrite_fixture(self.pdf, stream=stream.replace(b"/F1", b"/F2"), objects={3: bodies[3].replace(b"/F1", b"/F2")})),
        ))
        for name, pdf in fixtures:
            with self.subTest(forgery=name):
                self.assertNotEqual(pdf, self.pdf)
                # General parsing and repaired offsets/lengths alone are not the oracle.
                self.assertEqual(len(PdfReader(BytesIO(pdf), strict=True).pages), 1)
                self.assert_invalid_without_rendering(pdf)
        changed_spacing = _rewrite_fixture(self.long_pdf, stream=_stream(self.long_pdf).replace(b"56 606 Tm", b"56 605 Tm"))
        self.assertEqual(len(PdfReader(BytesIO(changed_spacing), strict=True).pages), 1)
        self.assert_invalid_without_rendering(changed_spacing, self.long_fields)

    def test_self_consistent_extra_structure_actions_and_comments_are_rejected(self):
        bodies = _object_bodies(self.pdf)
        fixtures = (
            ("extra_object", _rewrite_fixture(self.pdf, extra={6: b"<< /Type /Example >>"})),
            ("object_order", _rewrite_fixture(self.pdf, order=[1, 3, 2, 4, 5])),
            ("catalog_action", _rewrite_fixture(self.pdf, objects={1: bodies[1][:-3] + b" /OpenAction [3 0 R /Fit] >>"})),
            ("outside_comment", _rewrite_fixture(self.pdf, header_extra=b"% extra comment\n")),
        )
        for name, pdf in fixtures:
            with self.subTest(structure=name):
                self.assertEqual(len(PdfReader(BytesIO(pdf), strict=True).pages), 1)
                self.assert_invalid_without_rendering(pdf)
        two_pages = _rewrite_fixture(self.pdf, objects={2: b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>"}, extra={6: bodies[3]})
        self.assertEqual(len(PdfReader(BytesIO(two_pages), strict=True).pages), 2)
        self.assert_invalid_without_rendering(two_pages)

    def test_lengths_xref_offsets_trailer_and_full_consumption_are_exact(self):
        pdf = self.pdf
        length = re.search(rb"/Length ([0-9]+)", pdf)[1]
        xref = re.search(rb"startxref\n([0-9]+)\n", pdf)[1]
        first_offset = re.search(rb"xref\n0 6\n0000000000 65535 f \n([0-9]{10})", pdf)[1]
        fixtures = {
            "version": pdf.replace(b"%PDF-1.4", b"%PDF-1.5", 1),
            "binary_header": pdf.replace(b"\xe2\xe3\xcf\xd3", b"\xe2\xe3\xcf\xd2", 1),
            "object_number": pdf.replace(b"1 0 obj\n", b"01 0 obj\n", 1),
            "object_generation": pdf.replace(b"1 0 obj\n", b"1 1 obj\n", 1),
            "short_stream": pdf.replace(b"/Length " + length, b"/Length " + str(int(length) - 1).encode(), 1),
            "long_stream": pdf.replace(b"/Length " + length, b"/Length " + str(int(length) + 1).encode(), 1),
            "noncanonical_length": pdf.replace(b"/Length " + length, b"/Length 0" + length, 1),
            "xref_count": pdf.replace(b"xref\n0 6\n", b"xref\n0 5\n", 1),
            "xref_offset": pdf.replace(first_offset + b" 00000 n", f"{int(first_offset) + 1:010d} 00000 n".encode(), 1),
            "xref_generation": pdf.replace(first_offset + b" 00000 n", first_offset + b" 00001 n", 1),
            "startxref_offset": pdf.replace(b"startxref\n" + xref, b"startxref\n" + str(int(xref) + 1).encode(), 1),
            "noncanonical_startxref": pdf.replace(b"startxref\n" + xref, b"startxref\n0" + xref, 1),
            "trailer_size": pdf.replace(b"/Size 6", b"/Size 7", 1),
            "trailer_root": pdf.replace(b"/Root 1 0 R", b"/Root 2 0 R", 1),
            "missing_eof": pdf[:-6],
            "trailing_lf": pdf + b"\n",
            "trailing_nul": pdf + b"\x00",
            "trailing_data": pdf + b"additional private data",
            "noncanonical_crlf": pdf.replace(b"\n", b"\r\n"),
        }
        for name, value in fixtures.items():
            with self.subTest(corruption=name):
                self.assert_invalid_without_rendering(value)

    def test_hex_and_text_operator_grammar_is_exact(self):
        stream = _stream(self.pdf)
        match = re.search(rb"<([0-9A-F]+)> Tj", stream)
        token = match[0]
        digits = match[1]
        replacements = (
            b"<" + digits[:-1] + b"> Tj",
            b"<" + digits[:2] + b" " + digits[2:] + b"> Tj",
            b"<GG" + digits[2:] + b"> Tj",
            b"<81" + digits[2:] + b"> Tj",
            b"<" + digits + b"> TJ",
            b"(" + b"SIMULATED" + b") Tj",
            token + b"\n0 0 m",
        )
        fixtures = [_rewrite_fixture(self.pdf, stream=stream.replace(token, value, 1)) for value in replacements]
        for index, pdf in enumerate(fixtures):
            with self.subTest(grammar=index):
                self.assert_invalid_without_rendering(pdf)

    def test_code_guard_positive_control_detects_all_preimported_aliases(self):
        # This is the instrumentation positive control, not a verifier invocation.
        for function, arguments in (
            (_RENDER_ALIAS, (self.fields,)),
            (_TEXT_ALIAS, ({}, {}, "sample", 0)),
            (_ASSEMBLY_ALIAS, ({}, ())),
        ):
            with self.subTest(alias=function.__name__):
                with self.assertRaisesRegex(AssertionError, "Actual renderer code invoked"):
                    with _forbid_rendering():
                        function(*arguments)


if __name__ == "__main__":
    unittest.main()
