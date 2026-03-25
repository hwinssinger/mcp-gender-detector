# mcp-gender-detector

An MCP server that detects the gender of a person from their first name and returns a title: **Mr**, **Ms**, or **unknown**.

Fully offline — uses a local database of 40,000+ first names via [gender-guesser](https://pypi.org/project/gender-guesser/). No API calls, no rate limits.

## Tools

### `detect_gender`

Detect gender for a single person.

**Parameters:**
- `first_name` (required) — the person's first name
- `last_name` (optional) — included in the response for context

**Returns:**
```json
{
  "title": "Mr",
  "full_name": "Jean Dupont",
  "first_name": "Jean"
}
```

### `detect_gender_batch`

Detect gender for multiple people at once.

**Parameters:**
- `names` — list of objects with `first_name` and optional `last_name`

**Returns:** list of results (same format as `detect_gender`)

## Installation

### With Claude Desktop / Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "gender-detector": {
      "command": "uvx",
      "args": ["mcp-gender-detector"]
    }
  }
}
```

### With pip

```bash
pip install mcp-gender-detector
```

Then run:

```bash
mcp-gender-detector
```

## Examples

| First name | Result |
|-----------|--------|
| Jean      | Mr     |
| Marie     | Ms     |
| Camille   | unknown |
| Alexander | Mr     |
| Yuki      | unknown |

## License

MIT
