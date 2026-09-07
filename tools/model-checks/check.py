#!/usr/bin/env python3
"""Read-only repository document/model checks; Python standard library only."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zlib


ROOT = Path(__file__).resolve().parents[2]
WBS_PATH = "docs/08-delivery-work-packages.md"
WBS_ID = r"(?:F|[ABC][123]|M-[ABCS]|E|R)\.\d+"
UML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class CheckError(ValueError):
    """A failed static check with an actionable description."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def unique(values: list[str], label: str) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    require(not duplicates, f"{label}: duplicate IDs {duplicates}")


def without_fences(content: str) -> str:
    """Remove fenced blocks, preserving prose line numbers; not a full Markdown parser."""
    output, fence = [], None
    for line in content.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            output.append("")
        else:
            output.append(line if fence is None else "")
    require(fence is None, "unclosed Markdown code fence")
    return "\n".join(output)


def markdown_destinations(content: str):
    """Yield inline/image and reference-definition destinations, not code examples."""
    text = re.sub(r"(`+).*?\1", "", without_fences(content))
    pattern = r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s()]+(?:\([^()]*\)[^\s()]*)*))"
    for match in re.finditer(pattern, text):
        yield match.group(1) or match.group(2)
    for match in re.finditer(r"^\s{0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|(\S+))", text, re.M):
        yield match.group(1) or match.group(2)


def document_files(root: Path) -> list[Path]:
    files = set(root.glob("*.md"))
    for folder in ("docs", "contracts", "tools/model-checks"):
        files.update(p for p in (root / folder).rglob("*.md") if "node_modules" not in p.parts)
    return sorted(files)


def check_documents(root: Path) -> str:
    files = document_files(root)
    links = 0
    for file in files:
        for destination in markdown_destinations(read(file)):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", destination) or destination.startswith("//"):
                continue  # No network, application URI, or file URI checks.
            target = unquote(urlsplit(destination).path)
            if not target:
                continue  # Heading-anchor validation is deliberately separate.
            resolved = (root / target.lstrip("/") if target.startswith("/") else file.parent / target).resolve()
            require(resolved.is_relative_to(root), f"{file.relative_to(root)}: non-portable link outside repository: {destination}")
            require(resolved.exists(), f"{file.relative_to(root)}: missing local target {destination}")
            links += 1
    return f"{len(files)} Markdown files; {links} existing local file/directory targets (anchors and external URLs not checked)"


def requirement_ids(content: str, prefix: str) -> list[str]:
    return re.findall(rf"^\|\s*[`*]*({prefix}-\d{{3}})\b[^|]*\|", content, re.M)


def check_coverage(root: Path) -> str:
    baseline = read(root / "docs/00-project-definition-v1.md")
    derived = read(root / "docs/04-requirements-and-backlog.md")
    counts = []
    for prefix in ("FR", "NFR", "BR"):
        # docs/00 repeats IDs in evidence tables; docs/04 is the single definition index.
        expected, actual = set(requirement_ids(baseline, prefix)), requirement_ids(derived, prefix)
        require(expected, f"No {prefix} definition rows found in docs/00")
        unique(actual, f"docs/04 {prefix}")
        require(set(actual) == expected, f"{prefix} coverage: missing={sorted(expected-set(actual))}, extra={sorted(set(actual)-expected)}")
        counts.append(f"{prefix}={len(actual)}")
    expected_ucs = set(re.findall(r"^\|\s*[`*]*(UC-\d+(?:E)?)\b[^|]*\|", baseline, re.M))
    actual_ucs = re.findall(r"^###\s+\S+\s+(UC-\d+(?:E)?)\s+-", read(root / "docs/05-lab-3-requirement-modelling.md"), re.M)
    unique(actual_ucs, "use-case specifications")
    require(expected_ucs and set(actual_ucs) == expected_ucs, f"Use-case specifications differ from docs/00: {actual_ucs} vs {sorted(expected_ucs)}")
    return ", ".join(counts) + f"; UC={len(actual_ucs)} derived from current baseline IDs"


def allocation_rows(content: str) -> dict[str, tuple[str, ...]]:
    rows = {}
    for line in content.splitlines():
        if not re.match(rf"^\|\s*{WBS_ID}\s*\|", line):
            continue
        columns = tuple(column.strip() for column in line.split("|")[1:-1])
        require(len(columns) >= 7, f"Incomplete WBS row: {line}")
        key = columns[0]
        require(key not in rows, f"Duplicate WBS row {key}")
        rows[key] = columns[:5]  # ID, Owner, Reviewer, S, F; prose is not frozen here.
    require(bool(rows), "No WBS rows found")
    return rows


def validate_wbs(rows: dict[str, tuple[str, ...]]) -> None:
    dependencies = {}
    for key, (_, owner, reviewer, start, finish) in rows.items():
        require(owner in "ABC" and len(owner) == 1, f"{key}: invalid Owner {owner}")
        require(reviewer in "ABC" and len(reviewer) == 1 and reviewer != owner, f"{key}: invalid/self Reviewer {reviewer}")
        deps = set()
        for cell in (start, finish):
            if cell in ("", "—", "-"):
                continue
            tokens = re.split(r"[、,，\s]+", cell)
            require(all(re.fullmatch(WBS_ID, token) for token in tokens), f"{key}: unrecognised dependency cell {cell}")
            deps.update(tokens)
        require(deps <= rows.keys(), f"{key}: unknown dependencies {sorted(deps-rows.keys())}")
        dependencies[key] = deps
    visited, active = set(), []

    def visit(key: str) -> None:
        require(key not in active, f"WBS dependency cycle: {' -> '.join(active + [key])}")
        if key in visited:
            return
        active.append(key)
        for dependency in sorted(dependencies[key]):
            visit(dependency)
        active.pop()
        visited.add(key)

    for key in dependencies:
        visit(key)


def check_wbs(root: Path, baseline_ref: str | None) -> str:
    rows = allocation_rows(read(root / WBS_PATH))
    validate_wbs(rows)
    if baseline_ref is None:
        return f"{len(rows)} WBS rows; valid references and acyclic S/F graph; Git comparison SKIPPED explicitly"
    require(not baseline_ref.startswith("-"), "baseline-ref cannot start with '-' ")
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "show", "--no-ext-diff", f"{baseline_ref}:{WBS_PATH}"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    require(result.returncode == 0, f"Cannot read WBS Git baseline {baseline_ref}: {result.stderr.strip()}")
    before = allocation_rows(result.stdout)
    changed = sorted(key for key in before.keys() | rows.keys() if before.get(key) != rows.get(key))
    require(not changed, f"WBS ID/Owner/Reviewer/S/F differs from {baseline_ref}: {changed}")
    return f"{len(rows)} WBS rows; ID/Owner/Reviewer/S/F unchanged from {baseline_ref}; valid acyclic S/F graph"


def normalized_plantuml(content: str) -> str:
    content = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    # PlantUML's embedded source omits the outer diagram directives.
    return re.sub(r"^@(?:start|end)uml[^\n]*\n?", "", content, flags=re.M).strip("\n")


def embedded_plantuml(svg: str) -> str:
    match = re.search(r"<\?plantuml-src\s+([0-9A-Za-z_-]+)\?>", svg)
    if not match:
        match = re.search(r"<!--\s*SRC=\[([0-9A-Za-z_-]+)\]\s*-->", svg)
    require(match is not None, "SVG lacks supported embedded PlantUML source; render with source metadata enabled")
    encoded = match.group(1).translate(str.maketrans(UML_ALPHABET, BASE64_ALPHABET))
    try:
        compressed = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
        return zlib.decompress(compressed, -15).decode("utf-8")
    except (ValueError, zlib.error, UnicodeError) as exc:
        raise CheckError(f"Cannot decode embedded PlantUML source: {exc}") from exc


def check_svg_pair(source: Path) -> None:
    require(source.with_suffix(".svg").is_file(), f"Missing SVG for {source.name}")
    svg = read(source.with_suffix(".svg"))
    element = ET.fromstring(svg)
    require(element.tag == "{http://www.w3.org/2000/svg}svg", f"Not an SVG root: {source.name}")
    require("Syntax Error" not in "".join(element.itertext()), f"PlantUML error image: {source.name}")
    expected, embedded = normalized_plantuml(read(source)), normalized_plantuml(embedded_plantuml(svg))
    require(expected == embedded, f"SVG source differs from {source.name}; re-render this model (mtime is not used)")


def check_svg_sources(root: Path) -> str:
    sources = sorted((root / "docs/diagrams").rglob("*.puml"))
    require(bool(sources), "No PlantUML sources found")
    for source in sources:
        content = read(source)
        require(len(re.findall(r"^@startuml\b", content, re.M)) == 1 and len(re.findall(r"^@enduml\b", content, re.M)) == 1,
                f"{source.name}: expected one self-contained PlantUML diagram")
        require(not re.search(r"^\s*!include", content, re.M), f"{source.name}: include expansion needs a renderer-aware check; unsupported here")
        require(all(line == line.rstrip() for line in content.splitlines()), f"{source.name}: trailing whitespace")
        check_svg_pair(source)
    orphans = [p.relative_to(root).as_posix() for folder in ("member-a", "shared")
               for p in (root / "docs/diagrams" / folder).glob("*.svg") if not p.with_suffix(".puml").exists()]
    require(not orphans, f"SVG files without matching source: {orphans}")
    return f"{len(sources)} SVG/source pairs match embedded source; no rendering or visual review performed"


def scenario_ids(content: str, prefix: str) -> list[str]:
    ids = re.findall(rf"^\|\s*({prefix}-T\d+)\b", content, re.M)
    require(bool(ids), f"No {prefix} scenario rows found")
    unique(ids, f"{prefix} scenario registry")
    numbers = [int(value.rsplit("T", 1)[1]) for value in ids]
    require(numbers == list(range(1, len(numbers) + 1)), f"{prefix} scenario IDs must be sequential and ordered: {ids}")
    references = set(re.findall(rf"\b{prefix}-T\d+\b", content))
    require(references <= set(ids), f"Undeclared {prefix} scenario references: {sorted(references-set(ids))}")
    return ids


def check_member_a(root: Path) -> str:
    folder = root / "docs/diagrams/member-a"
    model = read(root / "docs/12-member-a-model-chain.md")
    scenarios = scenario_ids(model, "MA")
    activity = read(folder / "governed-execution-activity.puml")
    actions = re.findall(r"^\s*:(A\d+[a-z]?)\s", activity, re.M)
    require(bool(actions), "No Member A activity action IDs found")
    unique(actions, "activity actions")
    references = set(re.findall(r"\bA\d{2,}[a-z]?\b", model))
    require(references <= set(actions), f"MA document references absent activity actions: {sorted(references-set(actions))}")
    schema = json.loads(read(root / "contracts/v1/schemas.json"))
    expected = set(schema["$defs"]["OperationAttempt"]["properties"]["status"]["enum"])
    state_source = read(folder / "operation-attempt-state.puml")
    states = re.findall(r"^state\s+([A-Z][A-Z_]*)\s*$", state_source, re.M)
    unique(states, "OperationAttempt states")
    require(set(states) == expected, f"OperationAttempt states differ from schema: {sorted(states)} vs {sorted(expected)}")
    endpoints = re.findall(r"^(\[\*\]|[A-Z_]+)\s*-->\s*(\[\*\]|[A-Z_]+)", state_source, re.M)
    used_states = {name for pair in endpoints for name in pair if name != "[*]"}
    require(used_states <= expected, f"Undeclared transition states: {sorted(used_states-expected)}")
    return f"{len(scenarios)} MA scenarios; {len(actions)} unique action IDs; {len(states)} schema-matching states"


def composite_structure(content: str):
    stack, parents, ports, edges = [], {}, {}, []
    for number, line in enumerate(content.splitlines(), 1):
        part = re.match(r'\s*component\s+"(?:\\.|[^"\\])*"\s+as\s+(\w+)\s*\{', line)
        if part:
            alias = part.group(1)
            require(alias not in parents, f"line {number}: duplicate part {alias}")
            parents[alias] = stack[-1] if stack else None
            stack.append(alias)
        elif line.strip() == "}":
            require(bool(stack), f"line {number}: unmatched closing part brace")
            stack.pop()
        elif re.match(r"\s*port(?:in|out)?\b", line):
            port = re.match(r'\s*port(?:in|out)?\s+"((?:\\.|[^"\\])*)"\s+as\s+(\w+)\s*$', line)
            require(port is not None and bool(stack), f"line {number}: unsupported/unowned port declaration")
            label, alias = port.groups()
            direction = re.search(r"[\[(]([PR])[\])]\s*$", label)
            require(direction is not None, f"line {number}: port requires explicit local P/R annotation")
            require(alias not in ports, f"line {number}: duplicate port {alias}")
            ports[alias] = (stack[-1], direction.group(1))
        elif re.match(r"\w+\s+--\s+\w+", line):
            edge = re.fullmatch(r"(\w+)\s+--\s+(\w+)\s*:\s*([DA]\d+)\s*", line)
            require(edge is not None, f"line {number}: connector needs a D/A registry ID")
            edges.append(edge.groups())
    require(not stack, f"Unclosed part boxes: {stack}")
    require(sum(parent is None for parent in parents.values()) == 1, "Expected one outer structured classifier per CS view")
    used = set()
    for left, right, identifier in edges:
        require(left in ports and right in ports, f"{identifier}: undeclared connector endpoint")
        used.update((left, right))
        lo, ld = ports[left]
        ro, rd = ports[right]
        if identifier.startswith("D"):
            require((parents.get(lo) == ro or parents.get(ro) == lo) and ld == rd,
                    f"{identifier}: delegation must link a boundary to its direct part with matching external P/R")
        else:
            require(lo != ro and parents[lo] is not None and parents[lo] == parents[ro] and {ld, rd} == {"P", "R"},
                    f"{identifier}: assembly must link sibling parts with complementary P/R")
    require(used == set(ports), f"Ports absent from connector registry: {sorted(set(ports)-used)}")
    return ports, edges


def check_shared(root: Path) -> str:
    sources = sorted((root / "docs/diagrams/shared").glob("*.puml"))
    require(bool(sources), "No shared composite sources")
    structures = {source.name: composite_structure(read(source)) for source in sources}
    edges = [edge for _, diagram_edges in structures.values() for edge in diagram_edges]
    identifiers = [edge[2] for edge in edges]
    unique(identifiers, "composite connectors across all views")
    document = read(root / "docs/13-shared-composite-structure.md")
    registered = re.findall(r"^\|\s*([DA]\d+)\s*\|", document, re.M)
    unique(registered, "documented composite connector registry")
    require(set(identifiers) == set(registered), f"Connector registry mismatch: source-only={sorted(set(identifiers)-set(registered))}, doc-only={sorted(set(registered)-set(identifiers))}")
    scenarios = scenario_ids(document, "MS")
    # Named project-boundary checks, not generic UML semantics or runtime proof.
    protected = {
        "governed-case-composite.puml": {"REPO_CASE": {"DOM_STORE"}, "AUD_APPEND": {"DOM_AUDIT"}},
        "governed-analysis-composite.puml": {"RI_CALL": {"OR_RISK"}},
        "governed-execution-composite.puml": {"RE_EFFECT": {"OP_RET"}, "NO_DELIVER": {"OP_NOTIFY"}},
    }
    for filename, boundary in protected.items():
        require(filename in structures, f"Missing boundary model {filename}")
        ports, diagram_edges = structures[filename]
        for endpoint, expected_peers in boundary.items():
            require(endpoint in ports, f"{filename}: required boundary port {endpoint} absent")
            peers = {right if left == endpoint else left for left, right, _ in diagram_edges if endpoint in (left, right)}
            require(peers == expected_peers, f"{filename}: {endpoint} neighbors {peers} differ from {expected_peers}")
    appearances = sum(len(ports) for ports, _ in structures.values())
    return f"{len(sources)} CS views; {appearances} port appearances; {len(edges)} registered connectors; {len(scenarios)} scenarios; five named boundary adjacencies"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: derive from this script)")
    parser.add_argument("--baseline-ref", default="HEAD", help="read-only Git ref for WBS ownership/dependency comparison")
    parser.add_argument("--skip-baseline", action="store_true", help="explicitly skip only the Git comparison, e.g. a source archive")
    args = parser.parse_args()
    root = args.root.resolve()
    checks = [
        ("documents", lambda: check_documents(root)),
        ("requirement/use-case IDs", lambda: check_coverage(root)),
        ("WBS", lambda: check_wbs(root, None if args.skip_baseline else args.baseline_ref)),
        ("SVG source correspondence", lambda: check_svg_sources(root)),
        ("Member A references", lambda: check_member_a(root)),
        ("composite references", lambda: check_shared(root)),
    ]
    failures = 0
    for label, action in checks:
        try:
            print(f"PASS {label}: {action()}")
        except (CheckError, OSError, ValueError, KeyError, ET.ParseError) as exc:
            print(f"FAIL {label}: {exc}", file=sys.stderr)
            failures += 1
    print(f"Static check groups: {len(checks)-failures}/{len(checks)} passed.")
    print("No renderer, HTTP/provider tests, external URL checks, UML metamodel validation or human review was performed.")
    return 1 if failures else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
