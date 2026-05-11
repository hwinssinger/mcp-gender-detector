import os
import sys

from mcp.server.fastmcp import FastMCP
import gender_guesser.detector as gender
import httpx
from pydantic import BaseModel, Field

mcp = FastMCP("gender-detector")
detector = gender.Detector()

MALE_RESULTS = {"male", "mostly_male"}
FEMALE_RESULTS = {"female", "mostly_female"}
GENDERIZE_URL = "https://api.genderize.io"
GENDERIZE_API_KEY = os.environ.get("GENDERIZE_API_KEY") or None
GENDERIZE_CONFIDENCE = float(os.environ.get("GENDERIZE_CONFIDENCE", "0.7"))
HTTP_TIMEOUT = 10.0


class NameEntry(BaseModel):
    first_name: str = Field(..., description="The person's first name (required, non-empty)")
    last_name: str = Field("", description="Optional last name, echoed in the response for context")


def _classify(result: str) -> str | None:
    if result in MALE_RESULTS:
        return "Mr"
    if result in FEMALE_RESULTS:
        return "Ms"
    return None


def _title_each(name: str) -> str:
    """Title-case every hyphen- and space-separated part: 'jean-pierre' -> 'Jean-Pierre'."""
    return " ".join(
        "-".join(p.capitalize() for p in token.split("-"))
        for token in name.strip().split()
    )


def _detect_local(name: str) -> str | None:
    cleaned = _title_each(name)
    if not cleaned:
        return None
    return _classify(detector.get_gender(cleaned))


def _detect_local_compound(first_name: str) -> str | None:
    """Local detection with fallback on hyphenated / multi-token first names."""
    parts = first_name.strip().split()
    if not parts:
        return None
    first = parts[0]

    title = _detect_local(first)
    if title:
        return title

    for hp in first.split("-"):
        if len(hp) >= 2:
            title = _detect_local(hp)
            if title:
                return title

    for p in parts[1:]:
        for sub in p.split("-"):
            if len(sub) >= 2:
                title = _detect_local(sub)
                if title:
                    return title

    return None


def _clean_first_name(first_name: str) -> str:
    """Extract the first non-empty token suitable for Genderize.io lookup."""
    parts = first_name.strip().split()
    if not parts:
        return ""
    return next((p for p in parts[0].split("-") if p), "")


def _classify_api(item: dict) -> str | None:
    g = item.get("gender")
    prob = item.get("probability", 0)
    if g == "male" and prob >= GENDERIZE_CONFIDENCE:
        return "Mr"
    if g == "female" and prob >= GENDERIZE_CONFIDENCE:
        return "Ms"
    return None


def _detect_genderize(first_name: str) -> str | None:
    name = _clean_first_name(first_name)
    if not name:
        return None
    params: dict[str, str] = {"name": name}
    if GENDERIZE_API_KEY:
        params["apikey"] = GENDERIZE_API_KEY
    try:
        resp = httpx.get(GENDERIZE_URL, params=params, timeout=5)
        resp.raise_for_status()
        return _classify_api(resp.json())
    except (httpx.HTTPError, ValueError):
        return None


def _detect_genderize_batch(names: list[str]) -> dict[str, str | None]:
    clean = {n: _clean_first_name(n) for n in names}
    unique = [n for n in set(clean.values()) if n]
    api_results: dict[str, str | None] = {}

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for i in range(0, len(unique), 10):
            batch = unique[i : i + 10]
            params: list[tuple[str, str]] = [("name[]", n) for n in batch]
            if GENDERIZE_API_KEY:
                params.append(("apikey", GENDERIZE_API_KEY))
            try:
                resp = client.get(GENDERIZE_URL, params=params)
                resp.raise_for_status()
                for item in resp.json():
                    api_results[item.get("name", "")] = _classify_api(item)
            except (httpx.HTTPError, ValueError):
                continue

    return {orig: api_results.get(c) for orig, c in clean.items()}


@mcp.tool()
def detect_gender(first_name: str, last_name: str = "") -> dict:
    """Detect a person's gender from their first name and return Mr / Ms / unknown.

    Uses a local database of 40,000+ names with automatic fallback to the
    Genderize.io API (requires GENDERIZE_API_KEY) for non-Western or uncommon names.

    Args:
        first_name: The person's first name. Required.
        last_name: Optional last name, echoed in the response for context.
    """
    first = first_name.strip()
    last = last_name.strip()
    full_name = f"{first} {last}".strip()
    base = {"full_name": full_name, "first_name": first}

    if not first:
        return {"title": "unknown", **base}

    title = _detect_local_compound(first) or _detect_genderize(first)
    return {"title": title or "unknown", **base}


@mcp.tool()
def detect_gender_batch(names: list[NameEntry]) -> list[dict]:
    """Detect gender for multiple people in one call.

    Runs local detection first for speed, then batches unknown names
    (up to 10 per Genderize.io request, reusing one HTTP connection).

    Args:
        names: List of objects with first_name (required) and optional last_name.
    """
    results: list[dict] = []
    unknowns: list[int] = []

    for i, entry in enumerate(names):
        first = entry.first_name.strip()
        last = entry.last_name.strip()
        full_name = f"{first} {last}".strip()

        if not first:
            results.append({"title": "unknown", "full_name": full_name, "first_name": ""})
            continue

        title = _detect_local_compound(first)
        results.append({
            "title": title or "unknown",
            "full_name": full_name,
            "first_name": first,
        })
        if not title:
            unknowns.append(i)

    if unknowns:
        unknown_names = [names[i].first_name for i in unknowns]
        api_results = _detect_genderize_batch(unknown_names)
        for idx, orig_name in zip(unknowns, unknown_names):
            api_title = api_results.get(orig_name)
            if api_title:
                results[idx]["title"] = api_title

    return results


def main():
    if "--doctor" in sys.argv:
        key_status = f"set (length={len(GENDERIZE_API_KEY)})" if GENDERIZE_API_KEY else "NOT SET"
        print(f"mcp-gender-detector — config check")
        print(f"  GENDERIZE_API_KEY:    {key_status}")
        print(f"  GENDERIZE_CONFIDENCE: {GENDERIZE_CONFIDENCE}")
        print(f"  Python:               {sys.version.split()[0]}")
        sys.exit(0 if GENDERIZE_API_KEY else 1)

    if not GENDERIZE_API_KEY:
        sys.stderr.write(
            "ERROR: GENDERIZE_API_KEY environment variable is not set.\n"
            "\n"
            "This MCP server requires a Genderize.io API key for the international\n"
            "name fallback. Get a free key at https://genderize.io/ then either:\n"
            "  1. Re-run install.sh from the repository for guided setup, or\n"
            "  2. Add to your MCP client config:\n"
            '       \"env\": { \"GENDERIZE_API_KEY\": \"your-key-here\" }\n'
            "\n"
            "Run 'mcp-gender-detector --doctor' to verify your setup.\n"
        )
        sys.exit(2)

    mcp.run()


if __name__ == "__main__":
    main()
