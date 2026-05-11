# mcp-gender-detector

An [MCP](https://modelcontextprotocol.io/) server that detects the gender of a person from their first name and returns a polite title: **Mr**, **Ms**, or **unknown**.

- **Offline-first** — uses [gender-guesser](https://pypi.org/project/gender-guesser/) (40,000+ first names, no API call, no rate limit)
- **International fallback** — calls [Genderize.io](https://genderize.io/) for non-Western or uncommon names (your API key required)
- **Compound names** — handles `Jean-Pierre`, `Marie-Claire`, `Burcu Aslihan`, etc.
- **Batch mode** — process hundreds of names in a single tool call with HTTP connection reuse

## Requirements

- [Claude Code CLI](https://docs.claude.com/en/docs/agents-and-tools/claude-code/overview)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (provides `uvx`)
- A **Genderize.io API key** — free tier covers 1000 names/day. Sign up at https://genderize.io/

> The key is required: it powers the international fallback that catches the ~20% of names the local database misses (Turkish, Arabic, Japanese, modern compound first names, etc.).

## Install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/hwinssinger/mcp-gender-detector/main/install.sh | bash
```

Or clone first:

```bash
git clone https://github.com/hwinssinger/mcp-gender-detector.git
cd mcp-gender-detector
./install.sh
```

The installer prompts for your Genderize key, validates it against the API, and registers the MCP with `claude mcp add`. Restart your Claude Code session to load it.

## Install (manual)

If you prefer to edit your MCP config by hand:

```json
{
  "mcpServers": {
    "gender-detector": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/hwinssinger/mcp-gender-detector.git",
        "mcp-gender-detector"
      ],
      "env": {
        "GENDERIZE_API_KEY": "your-key-here"
      }
    }
  }
}
```

Verify your install at any time:

```bash
uvx --from git+https://github.com/hwinssinger/mcp-gender-detector.git mcp-gender-detector --doctor
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GENDERIZE_API_KEY` | *(required)* | Your Genderize.io API key |
| `GENDERIZE_CONFIDENCE` | `0.7` | Minimum probability (0.0–1.0) for an API result to be accepted |

## Tools

### `detect_gender`

Detect gender for a single person.

**Parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `first_name` | string | yes | The person's first name |
| `last_name`  | string | no  | Included in the response for context |

**Returns**
```json
{
  "title": "Mr",
  "full_name": "Jean Dupont",
  "first_name": "Jean"
}
```

### `detect_gender_batch`

Detect gender for many people in one call. Local detection runs first; remaining unknowns are batched (up to 10 names per Genderize.io request, single HTTP connection reused).

**Parameters**
| Name | Type | Description |
|---|---|---|
| `names` | array of `{first_name, last_name?}` | List of people to classify |

**Returns** — array of objects (same shape as `detect_gender`).

## Examples

| First name  | Result    | Source           |
|-------------|-----------|------------------|
| Jean        | Mr        | local            |
| Marie       | Ms        | local            |
| Jean-Pierre | Mr        | local (compound) |
| Marie-Claire| Ms        | local (compound) |
| Burcu       | Ms        | Genderize.io     |
| Yuki        | unknown   | both ambiguous   |
| Camille     | unknown   | both ambiguous (FR unisex) |

## How it works

```
first_name
    │
    ▼
┌─────────────────────────────┐
│ 1. gender-guesser (local)   │  ◄── 40k names, instant, offline
│    - title-cased lookup     │
│    - hyphenated parts       │
│    - compound first names   │
└─────────────────────────────┘
    │ unknown?
    ▼
┌─────────────────────────────┐
│ 2. Genderize.io API         │  ◄── international, ≥ GENDERIZE_CONFIDENCE
└─────────────────────────────┘
    │
    ▼
  Mr / Ms / unknown
```

## Privacy

- **No data stored** by this server, no telemetry, no analytics
- Local detection (~80% of Western names) never leaves your machine
- Only first names that fail locally are sent to Genderize.io
- Your API key is stored only in your local Claude Code MCP config

## Local development

```bash
git clone https://github.com/hwinssinger/mcp-gender-detector.git
cd mcp-gender-detector
uv sync
export GENDERIZE_API_KEY=your-key
uv run mcp-gender-detector --doctor  # verify config
uv run mcp-gender-detector            # start server on stdio
```

Inspect with the MCP Inspector:

```bash
uv run mcp dev src/mcp_gender_detector/server.py
```

## License

MIT — see [LICENSE](LICENSE).
