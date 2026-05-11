#!/usr/bin/env bash
# Interactive installer for mcp-gender-detector.
# Usage:
#   ./install.sh                                (after cloning the repo)
#   curl -fsSL https://raw.githubusercontent.com/hwinssinger/mcp-gender-detector/main/install.sh | bash
set -euo pipefail

REPO_URL="https://github.com/hwinssinger/mcp-gender-detector"
GIT_URL="git+${REPO_URL}.git"
MCP_NAME="gender-detector"

err()  { printf "ERROR: %s\n" "$*" >&2; exit 1; }
info() { printf "==> %s\n" "$*"; }

# --- 1. Prerequisites ------------------------------------------------------
command -v claude >/dev/null 2>&1 || err "Claude Code CLI not found. Install it first: https://docs.claude.com/en/docs/agents-and-tools/claude-code/overview"
command -v uv     >/dev/null 2>&1 || err "uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
command -v curl   >/dev/null 2>&1 || err "curl required."

info "Setting up the '${MCP_NAME}' MCP server"
cat <<'EOF'

This server requires a Genderize.io API key for the international name fallback.
Free tier: 1000 names/day. Sign up at https://genderize.io/

The key is stored in YOUR local Claude Code MCP config only — it is never
transmitted anywhere except to api.genderize.io when a lookup is performed.

EOF

# --- 2. Prompt for key (loop until non-empty) ------------------------------
KEY=""
while [ -z "${KEY}" ]; do
    if [ -t 0 ]; then
        read -r -p "Genderize API key: " KEY
    else
        # curl | bash mode: stdin is the pipe, read from terminal directly
        read -r -p "Genderize API key: " KEY </dev/tty
    fi
    [ -z "${KEY}" ] && echo "Key cannot be empty. Please try again."
done

# --- 3. Validate key against Genderize.io ----------------------------------
info "Validating key against api.genderize.io"
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "https://api.genderize.io/?name=test&apikey=${KEY}")

case "${CODE}" in
    200)
        echo "    Key accepted."
        ;;
    401|403)
        err "Genderize.io rejected this key (HTTP ${CODE}). Verify it and retry."
        ;;
    429)
        echo "    Warning: HTTP 429 (rate limited). Key looks valid but quota may be near."
        ;;
    *)
        echo "    Warning: unexpected HTTP ${CODE}. Proceeding anyway."
        ;;
esac

# --- 4. Replace existing registration if present ---------------------------
if claude mcp list 2>/dev/null | grep -qE "^\s*${MCP_NAME}\b"; then
    if [ -t 0 ]; then
        read -r -p "An existing '${MCP_NAME}' MCP is registered. Replace it? [y/N] " REPLACE
    else
        read -r -p "An existing '${MCP_NAME}' MCP is registered. Replace it? [y/N] " REPLACE </dev/tty
    fi
    [[ "${REPLACE}" =~ ^[yY] ]] || err "Aborted by user."
    info "Removing previous registration"
    claude mcp remove "${MCP_NAME}" >/dev/null
fi

# --- 5. Register the MCP ---------------------------------------------------
info "Registering the MCP with Claude Code"
claude mcp add "${MCP_NAME}" \
    -e "GENDERIZE_API_KEY=${KEY}" \
    -- uvx --from "${GIT_URL}" mcp-gender-detector

# --- 6. Done ---------------------------------------------------------------
cat <<EOF

Done. The '${MCP_NAME}' MCP is registered.

Next steps:
  - Restart your Claude Code session (or run /mcp) to load it.
  - Verify your install at any time:
      uvx --from ${GIT_URL} mcp-gender-detector --doctor

Optional environment variables (set via 'claude mcp add ... -e KEY=VAL'):
  GENDERIZE_CONFIDENCE   minimum probability for API results (default 0.7)
EOF
