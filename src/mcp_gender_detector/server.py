from mcp.server.fastmcp import FastMCP
import gender_guesser.detector as gender

mcp = FastMCP("gender-detector")
detector = gender.Detector()

MALE_RESULTS = {"male", "mostly_male"}
FEMALE_RESULTS = {"female", "mostly_female"}


def _detect(first_name: str) -> str:
    """Detect gender from first name and return Mr/Ms/unknown."""
    result = detector.get_gender(first_name.strip().capitalize())
    if result in MALE_RESULTS:
        return "Mr"
    if result in FEMALE_RESULTS:
        return "Ms"
    return "unknown"


@mcp.tool()
def detect_gender(first_name: str, last_name: str = "") -> dict:
    """Detect the gender of a person from their first name and return Mr/Ms/unknown.

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

    Args:
        names: List of objects with "first_name" and optional "last_name" keys.
              Example: [{"first_name": "Jean", "last_name": "Dupont"}, {"first_name": "Marie"}]
    """
    results = []
    for entry in names:
        first = entry.get("first_name", "")
        last = entry.get("last_name", "")
        if not first:
            results.append({"title": "unknown", "full_name": last, "first_name": ""})
            continue
        title = _detect(first)
        full_name = f"{first.strip()} {last.strip()}".strip()
        results.append({
            "title": title,
            "full_name": full_name,
            "first_name": first.strip(),
        })
    return results


def main():
    mcp.run()


if __name__ == "__main__":
    main()
