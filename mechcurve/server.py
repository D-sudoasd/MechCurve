"""Stdio tool interface for hosts with local file access."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .inputs import discover
from .pipeline import analyze, query, status

server = FastMCP("MechCurve")


@server.tool()
def inspect_directory(input_dir: str) -> list[dict]:
    """List acquisition IDs before analyzing or supplying a specimen note."""
    return [
        {
            "record": r["record"],
            "has_xml": bool(r["xml"]),
            "has_binary": bool(r["binary"]),
        }
        for r in discover(Path(input_dir).resolve(strict=True))
    ]


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
