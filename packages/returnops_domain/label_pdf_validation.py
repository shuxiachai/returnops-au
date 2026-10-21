"""Read and verify existing canonical label PDF bytes without rendering them."""

from __future__ import annotations

import re

from .label_pdf import MAX_PDF_BYTES, PDF_PROFILE_ID, LabelPdfFields, pdf_profile_spec


_ERROR = "Invalid fixed-profile label PDF"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{2,79}")


class _MalformedPdf(Exception):
    pass


def _require(condition: bool) -> None:
    if not condition:
        raise _MalformedPdf


class _Cursor:
    """A bounded view into the supplied bytes; it never builds output content."""

    __slots__ = ("data", "position", "end")

    def __init__(self, data: bytes, start: int = 0, end: int | None = None):
        self.data = data
        self.position = start
        self.end = len(data) if end is None else end

    def take(self, literal: bytes) -> None:
        _require(self.data.startswith(literal, self.position, self.end))
        self.position += len(literal)

    def until(self, delimiter: bytes) -> bytes:
        end = self.data.find(delimiter, self.position, self.end)
        _require(end >= 0)
        value = self.data[self.position:end]
        self.position = end + len(delimiter)
        return value

    def line(self) -> bytes:
        return self.until(b"\n")

    def done(self) -> None:
        _require(self.position == self.end)


def verify_label_pdf(content: bytes, fields: LabelPdfFields) -> None:
    """Verify this exact fixed-profile document, returning no content or metadata.

    This is a deliberately narrow parser, not a general PDF reader. It accepts
    only the canonical grammar of the frozen v1 profile and consumes all bytes.
    """
    try:
        _require(type(content) is bytes and 0 < len(content) <= MAX_PDF_BYTES)
        _require(type(fields) is LabelPdfFields)
        values = {
            "provider_label_id": fields.provider_label_id,
            "provider_return_id": fields.provider_return_id,
            "parcel_id": fields.parcel_id,
        }
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value) is not None
                     for value in values.values()))
        _verify(content, values, pdf_profile_spec())
    except _MalformedPdf:
        raise ValueError(_ERROR) from None


def _verify(content: bytes, values: dict[str, str], profile: dict) -> None:
    _supported_profile(profile)
    cursor = _Cursor(content)
    cursor.take(bytes.fromhex(profile["serializer"]["header_hex"]))
    offsets = []

    _begin_object(cursor, 1, offsets)
    cursor.take(b"<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    _begin_object(cursor, 2, offsets)
    cursor.take(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

    _begin_object(cursor, 3, offsets)
    cursor.take(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ")
    cursor.take(str(profile["page"]["width_points"]).encode("ascii"))
    cursor.take(b" ")
    cursor.take(str(profile["page"]["height_points"]).encode("ascii"))
    cursor.take(b"] /Resources << /Font << /")
    cursor.take(profile["font"]["resource"].encode("ascii"))
    cursor.take(b" 4 0 R >> >> /Contents 5 0 R >>\nendobj\n")

    _begin_object(cursor, 4, offsets)
    cursor.take(b"<< /Type /Font /Subtype /")
    cursor.take(profile["font"]["subtype"].encode("ascii"))
    cursor.take(b" /BaseFont /")
    cursor.take(profile["font"]["base_font"].encode("ascii"))
    cursor.take(b" /Encoding /")
    cursor.take(profile["font"]["encoding"].encode("ascii"))
    cursor.take(b" >>\nendobj\n")

    _begin_object(cursor, 5, offsets)
    cursor.take(b"<< /Length ")
    declared_length = _unsigned(cursor.until(b" >>\nstream\n"))
    stream_end = cursor.position + declared_length
    _require(stream_end <= cursor.end)
    stream = _Cursor(content, cursor.position, stream_end)
    _verify_stream(stream, values, profile)
    stream.done()
    cursor.position = stream_end
    cursor.take(b"endstream\nendobj\n")

    xref_offset = cursor.position
    cursor.take(b"xref\n0 6\n0000000000 65535 f \n")
    for actual_offset in offsets:
        entry = cursor.line()
        _require(len(entry) == 19 and entry[:10].isdigit()
                 and entry[10:] == b" 00000 n ")
        _require(int(entry[:10]) == actual_offset)
    cursor.take(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    _require(_unsigned(cursor.line()) == xref_offset)
    cursor.take(b"%%EOF\n")
    cursor.done()


def _begin_object(cursor: _Cursor, number: int, offsets: list[int]) -> None:
    offsets.append(cursor.position)
    cursor.take(str(number).encode("ascii"))
    cursor.take(b" 0 obj\n")


def _unsigned(token: bytes) -> int:
    _require(1 <= len(token) <= 5 and token.isdigit())
    _require(len(token) == 1 or token[0] != ord("0"))
    value = int(token)
    _require(value <= MAX_PDF_BYTES)
    return value


def _verify_stream(cursor: _Cursor, values: dict[str, str], profile: dict) -> None:
    wrap = profile["line_wrap_characters"]
    for element in profile["template"]:
        if "field" in element:
            value = values[element["field"]]
            # Compare one original-ID fragment at a time; no expected stream is
            # constructed, retained, returned, or handed to a PDF assembler.
            for start in range(0, len(value), wrap):
                y = element["y"] - (start // wrap) * profile["line_spacing_points"]
                _verify_text_block(cursor, element, value[start:start + wrap], y, profile)
        else:
            _verify_text_block(cursor, element, element["text"], element["y"], profile)


def _verify_text_block(cursor: _Cursor, element: dict, text: str, y: int, profile: dict) -> None:
    cursor.take(b"BT\n")
    font = cursor.line().split(b" ")
    _require(len(font) == 3 and font[0] == b"/" + profile["font"]["resource"].encode("ascii")
             and font[1] == str(element["size"]).encode("ascii") and font[2] == b"Tf")
    _require(cursor.line() == element["color"].encode("ascii"))
    matrix = cursor.line().split(b" ")
    _require(len(matrix) == 7 and matrix[:4] == [b"1", b"0", b"0", b"1"]
             and matrix[4] == str(element["x"]).encode("ascii")
             and matrix[5] == str(y).encode("ascii") and matrix[6] == b"Tm")
    line = cursor.line()
    _require(line.startswith(b"<") and line.endswith(b"> Tj"))
    digits = line[1:-4]
    _require(0 < len(digits) <= 160 and len(digits) % 2 == 0
             and all(character in b"0123456789ABCDEF" for character in digits))
    try:
        decoded = bytes.fromhex(digits.decode("ascii")).decode(profile["string_encoding"]["codec"])
    except UnicodeError:
        raise _MalformedPdf from None
    _require(decoded == text)
    cursor.take(b"ET\n")


def _supported_profile(profile: dict) -> None:
    """Fail closed if a later profile needs a different parsing grammar.

    These are grammar declarations, never a document or a content-stream
    construction. Layout and literal text are read from the fixed profile.
    """
    _require(profile["id"] == PDF_PROFILE_ID
             and profile["page"] == {"width_points": 612, "height_points": 792, "count": 1}
             and profile["font"] == {"resource": "F1", "subtype": "Type1", "base_font": "Helvetica", "encoding": "WinAnsiEncoding"}
             and profile["line_wrap_characters"] == 40
             and profile["line_spacing_points"] == 16
             and profile["string_encoding"] == {"codec": "cp1252", "uppercase_hex": True}
             and profile["limits"] == {"pages": 1, "max_bytes": MAX_PDF_BYTES})
    _require(profile["serializer"] == {
        "encoding": "ascii",
        "header_hex": "255044462d312e340a25e2e3cfd30a",
        "text_operator": "BT\n/{font_resource} {size} Tf\n{color}\n1 0 0 1 {x} {y} Tm\n<{text_hex}> Tj\nET",
        "line_separator": "\n",
        "stream_terminator": "\n",
        "objects": (
            "<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count {page_count} >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Resources << /Font << /{font_resource} 4 0 R >> >> /Contents 5 0 R >>",
            "<< /Type /Font /Subtype /{font_subtype} /BaseFont /{base_font} /Encoding /{font_encoding} >>",
            "<< /Length {stream_length} >>\nstream\n{stream}endstream",
        ),
        "first_object_number": 1,
        "object": "{number} 0 obj\n{body}\nendobj\n",
        "xref_header": "xref\n0 {count}\n",
        "xref_free_entries": ("0000000000 65535 f \n",),
        "xref_entry": "{offset:010d} 00000 n \n",
        "trailer": "trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n",
    })
