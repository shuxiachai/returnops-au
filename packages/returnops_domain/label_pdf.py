"""Fixed, read-only PDF renderer for the simulated label artifact profile."""

from __future__ import annotations

from dataclasses import dataclass
import re


PDF_PROFILE_ID = "mock-label-pdf-v1"
MAX_PDF_BYTES = 65_536

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,79}$")


@dataclass(frozen=True, slots=True, repr=False)
class LabelPdfFields:
    provider_label_id: str
    provider_return_id: str
    parcel_id: str


def pdf_profile_spec() -> dict:
    """Return the fresh declarative template and serialization used by the renderer.

    Keep every fixed output value here: the core hashes this complete profile.
    The renderer below only substitutes original IDs and derived PDF offsets.
    """
    return {
        "id": PDF_PROFILE_ID,
        "page": {"width_points": 612, "height_points": 792, "count": 1},
        "font": {
            "resource": "F1", "subtype": "Type1", "base_font": "Helvetica",
            "encoding": "WinAnsiEncoding",
        },
        # Forty 12 pt Helvetica W glyphs occupy 453.12 pt of the 500 pt content width.
        "line_wrap_characters": 40,
        "line_spacing_points": 16,
        "string_encoding": {"codec": "cp1252", "uppercase_hex": True},
        "template": (
            {"text": "SIMULATED — NOT VALID FOR POSTAGE", "x": 56, "y": 734, "size": 20, "color": "0.75 0 0 rg"},
            {"text": "MOCK RETURN LABEL", "x": 56, "y": 682, "size": 16, "color": "0 0 0 rg"},
            {"text": "Provider label ID", "x": 56, "y": 642, "size": 12, "color": "0 0 0 rg"},
            {"field": "provider_label_id", "x": 56, "y": 622, "size": 12, "color": "0 0 0 rg"},
            {"text": "Provider return ID", "x": 56, "y": 566, "size": 12, "color": "0 0 0 rg"},
            {"field": "provider_return_id", "x": 56, "y": 546, "size": 12, "color": "0 0 0 rg"},
            {"text": "Parcel ID", "x": 56, "y": 490, "size": 12, "color": "0 0 0 rg"},
            {"field": "parcel_id", "x": 56, "y": 470, "size": 12, "color": "0 0 0 rg"},
            {"text": "This document is simulated and has no postage value.", "x": 56, "y": 380, "size": 10, "color": "0 0 0 rg"},
        ),
        "serializer": {
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
        },
        "limits": {"pages": 1, "max_bytes": MAX_PDF_BYTES},
    }


def render_label_pdf(fields: LabelPdfFields) -> bytes:
    """Render one deterministic, simulated-label PDF from validated original IDs."""
    if not isinstance(fields, LabelPdfFields) or not _valid_fields(fields):
        raise ValueError("Invalid label PDF input")

    profile = pdf_profile_spec()
    if profile["page"]["count"] != profile["limits"]["pages"]:
        raise ValueError("Invalid label PDF input")
    lines = []
    wrap_at = profile["line_wrap_characters"]
    for element in profile["template"]:
        if "field" in element:
            value = getattr(fields, element["field"])
            chunks = tuple(value[index:index + wrap_at] for index in range(0, len(value), wrap_at))
        else:
            chunks = (element["text"],)
        for index, text in enumerate(chunks):
            y = element["y"] - index * profile["line_spacing_points"]
            lines.append(_text_line(profile, element, text, y))
    serializer = profile["serializer"]
    stream = serializer["line_separator"].join(lines) + serializer["stream_terminator"]
    substitutions = {
        "page_width": profile["page"]["width_points"],
        "page_height": profile["page"]["height_points"],
        "page_count": profile["page"]["count"],
        "font_resource": profile["font"]["resource"],
        "font_subtype": profile["font"]["subtype"],
        "base_font": profile["font"]["base_font"],
        "font_encoding": profile["font"]["encoding"],
        "stream_length": len(stream.encode(serializer["encoding"])),
        "stream": stream,
    }
    objects = tuple(template.format(**substitutions) for template in serializer["objects"])
    result = _assemble_pdf(serializer, objects)
    if len(result) > profile["limits"]["max_bytes"]:
        raise ValueError("Invalid label PDF input")
    return result


def _valid_fields(fields: LabelPdfFields) -> bool:
    return all(type(value) is str and _IDENTIFIER.fullmatch(value) is not None for value in
               (fields.provider_label_id, fields.provider_return_id, fields.parcel_id))


def _text_line(profile: dict, element: dict, text: str, y: int) -> str:
    # Hex strings avoid PDF literal-string escaping, using the bound codec/case.
    encoded = text.encode(profile["string_encoding"]["codec"]).hex()
    if profile["string_encoding"]["uppercase_hex"]:
        encoded = encoded.upper()
    return profile["serializer"]["text_operator"].format(
        font_resource=profile["font"]["resource"], size=element["size"],
        color=element["color"], x=element["x"], y=y, text_hex=encoded,
    )


def _assemble_pdf(serializer: dict, objects: tuple[str, ...]) -> bytes:
    encoding = serializer["encoding"]
    output = bytearray.fromhex(serializer["header_hex"])
    offsets = []
    for number, body in enumerate(objects, serializer["first_object_number"]):
        offsets.append(len(output))
        output.extend(serializer["object"].format(number=number, body=body).encode(encoding))
    xref_offset = len(output)
    count = len(objects) + len(serializer["xref_free_entries"])
    output.extend(serializer["xref_header"].format(count=count).encode(encoding))
    for entry in serializer["xref_free_entries"]:
        output.extend(entry.encode(encoding))
    for offset in offsets:
        output.extend(serializer["xref_entry"].format(offset=offset).encode(encoding))
    output.extend(serializer["trailer"].format(count=count, xref_offset=xref_offset).encode(encoding))
    return bytes(output)
