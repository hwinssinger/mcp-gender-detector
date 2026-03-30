from mcp.server.fastmcp import FastMCP
import gender_guesser.detector as gender
import httpx

mcp = FastMCP("gender-detector")
detector = gender.Detector()

MALE_RESULTS = {"male", "mostly_male"}
FEMALE_RESULTS = {"female", "mostly_female"}
GENDERIZE_URL = "https://api.genderize.io"


def _classify(result: str) -> str | None:
    """Map gender_guesser or genderize result to Mr/Ms or None."""
    if result in MALE_RESULTS:
        return "Mr"
    if result in FEMALE_RESULTS:
        return "Ms"
    return None


def _detect_local(name: str) -> str | None:
    """Try gender_guesser on a single name token."""
    result = detector.get_gender(name.strip().capitalize())
    return _classify(result)


def _detect_local_compound(first_name: str) -> str | None:
    """Try gender_guesser on compound/hyphenated names."""
    parts = first_name.strip().split()
    first = parts[0]

    # Try full first token
    title = _detect_local(first)
    if title:
        return title

    # Try each part of hyphenated name (e.g. Jan-Willem -> Jan, Willem)
    for hp in first.split("-"):
        if len(hp) < 2:
            continue
        title = _detect_local(hp)
        if title:
            return title

    # Try subsequent words (compound first names like "Burcu Aslihan")
    for p in parts[1:]:
        for sub in p.split("-"):
            if len(sub) < 2:
                continue
            title = _detect_local(sub)
            if title:
                return title

    return None


def _detect_genderize(first_name: str) -> str | None:
    """Fallback: call Genderize.io API for a single name."""
    # Use only the first token, stripped of hyphens
    name = first_name.strip().split()[0].split("-")[0]
    try:
        resp = httpx.get(GENDERIZE_URL, params={"name": name}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("gender") == "male" and (data.get("probability", 0) >= 0.7):
            return "Mr"
        if data.get("gender") == "female" and (data.get("probability", 0) >= 0.7):
            return "Ms"
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    return None


def _detect_genderize_batch(names: list[str]) -> dict[str, str | None]:
    """Fallback: call Genderize.io API for up to 10 names at once."""
    clean = {n: n.strip().split()[0].split("-")[0] for n in names}
    unique = list(set(clean.values()))
    results: dict[str, str | None] = {}

    # Genderize.io supports up to 10 names per request
    for i in range(0, len(unique), 10):
        batch = unique[i : i + 10]
        try:
            params = [("name[]", n) for n in batch]
            resp = httpx.get(GENDERIZE_URL, params=params, timeout=10)
            resp.raise_for_status()
            for item in resp.json():
                g = item.get("gender")
                prob = item.get("probability", 0)
                name_key = item.get("name", "")
                if g == "male" and prob >= 0.7:
                    results[name_key] = "Mr"
                elif g == "female" and prob >= 0.7:
                    results[name_key] = "Ms"
                else:
                    results[name_key] = None
        except (httpx.HTTPError, KeyError, ValueError):
            for n in batch:
                results[n] = None

    return {orig: results.get(c) for orig, c in clean.items()}


def _detect(first_name: str) -> str:
    """Detect gender: local first, then Genderize.io fallback."""
    title = _detect_local_compound(first_name)
    if title:
        return title

    title = _detect_genderize(first_name)
    return title or "unknown"


@mcp.tool()
def detect_gender(first_name: str, last_name: str = "") -> dict:
    """Detect the gender of a person from their first name and return Mr/Ms/unknown.

    Uses a local database of 40,000+ names with automatic fallback to Genderize.io
    API for non-Western and uncommon names.

    Args:
        first_name: The person's first name (required)
        last_name: The person's last name (optional, included in response for context)
    """
    title = _detect(first_name)
    full_name = f"{first_name.strip()} {last_name.strip()}".strip()
    return {
        "title": title,
        "full_name": full_name,
        "first_name": first_name.strip(),
    }


@mcp.tool()
def detect_gender_batch(names: list[dict]) -> list[dict]:
    """Detect gender for multiple people at once.

    Uses a local database first, then batches unknown names to Genderize.io API
    for broad international coverage.

    Args:
        names: List of objects with "first_name" and optional "last_name" keys.
              Example: [{"first_name": "Jean", "last_name": "Dupont"}, {"first_name": "Marie"}]
    """
    results = []
    unknowns: list[int] = []  # indices needing API fallback

    # Pass 1: local detection
    for i, entry in enumerate(names):
        first = entry.get("first_name", "")
        last = entry.get("last_name", "")
        full_name = f"{first.strip()} {last.strip()}".strip()

        if not first:
            results.append({"title": "unknown", "full_name": full_name, "first_name": ""})
            continue

        title = _detect_local_compound(first)
        results.append({
            "title": title or "unknown",
            "full_name": full_name,
            "first_name": first.strip(),
        })
        if not title:
            unknowns.append(i)

    # Pass 2: batch API fallback for unknowns
    if unknowns:
        unknown_names = [names[i].get("first_name", "") for i in unknowns]
        api_results = _detect_genderize_batch(unknown_names)
        for idx, orig_name in zip(unknowns, unknown_names):
            api_title = api_results.get(orig_name)
            if api_title:
                results[idx]["title"] = api_title

    return results


def main():
    mcp.run()


if __name__ == "__main__":
    main()
