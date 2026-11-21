"""Stdio tool interface for hosts with local file access."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .intake import catalog, inspect_records
from .pipeline import axial_summary, analyze, query, status

server = FastMCP("MechCurve")


@server.tool()
def inspect_directory(input_dir: str, notes: dict | None = None) -> list[dict]:
    """Inspect channel names, units, protocol evidence and unresolved coordinate choices."""
    return inspect_records(input_dir, notes)


@server.tool()
def list_protocols() -> dict:
    """List supported mechanical test types and their available coordinate pairs."""
    return catalog()


@server.tool()
def analyze_directory(
    input_dir: str,
    output_dir: str | None = None,
    notes: dict | None = None,
    lang: str = "zh",
) -> dict:
    """Create versioned figures, CSVs and PDF reports. Use record IDs from inspect_directory."""
    return analyze(input_dir, output_dir, notes, lang=lang)


@server.tool()
def summarize_axial(run: str, sample: str | None = None) -> dict:
    """Read first-loading modulus, recovery threshold landmarks and tensile fracture evidence by specimen."""
    return axial_summary(run, sample)


@server.tool()
def read_cycles(run: str, record: str, cycle: int | None = None) -> dict:
    """Read a segment summary or its physically numbered cycle and event rows."""
    return query(run, record, cycle=cycle)


@server.tool()
def review_rows(run: str, record: str, row: int, radius: int = 3) -> dict:
    """Return measured samples around an original CSV row; preserve equal-time rows."""
    return query(run, record, row=row, radius=radius)


@server.tool()
def verify_delivery(run: str) -> dict:
    """Verify output hashes and list deliverables including individual sample PDFs."""
    return status(Path(run))


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
