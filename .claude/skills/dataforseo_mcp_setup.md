# DataForSEO MCP Server — Setup Guide

Once configured, you can ask Claude directly:  
> *"Run an SEO audit on enricoviola.com"*  
and Claude will call the DataForSEO APIs, analyse the results, and write up findings — no Python script needed.

---

## Prerequisites

- Node.js 18+ installed (`node --version` to check)
- DataForSEO account with API credentials from https://app.dataforseo.com/api-access

---

## Option A — Claude Desktop (macOS / Windows)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`  
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "dataforseo": {
      "command": "npx",
      "args": ["-y", "dataforseo-mcp-server"],
      "env": {
        "DATAFORSEO_USERNAME": "your@email.com",
        "DATAFORSEO_PASSWORD": "your_api_password",
        "ENABLED_MODULES": "SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS",
        "DATAFORSEO_FULL_RESPONSE": "false"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see a 🔌 icon in the toolbar confirming the server connected.

---

## Option B — Claude Code (CLI)

```bash
claude mcp add dataforseo \
  --env DATAFORSEO_USERNAME=your@email.com \
  --env DATAFORSEO_PASSWORD=your_api_password \
  --env ENABLED_MODULES="SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS" \
  -- npx -y dataforseo-mcp-server
```

Verify it connected:
```bash
claude mcp list
```

---

## Modules

Enable only what your subscription covers to avoid 40204 (access denied) errors:

| Module             | What it provides                          | Subscription needed |
|--------------------|-------------------------------------------|---------------------|
| `DATAFORSEO_LABS`  | Domain rank, ranked keywords, competitors | DataForSEO Labs     |
| `ONPAGE`           | Technical crawl, page speed               | Any plan            |
| `SERP`             | Live SERP results                         | Any plan            |
| `KEYWORDS_DATA`    | Search volume, CPC, keyword ideas         | Any plan            |
| `BACKLINKS`        | Backlink profile, referring domains       | Backlinks add-on ⚠️ |
| `DOMAIN_ANALYTICS` | Whois, tech stack                         | Any plan            |

> **Note:** If you see `40204 Access denied` for Backlinks, remove `BACKLINKS` from  
> `ENABLED_MODULES` until you activate the backlinks subscription.

---

## Example prompts once connected

```
Run a complete SEO audit on enricoviola.com and summarise the findings.

What are the top 20 organic keywords for enricoviola.com by traffic?

Who are the main SEO competitors of enricoviola.com?

Check the page speed and Core Web Vitals for https://enricoviola.com

What technical SEO issues does enricoviola.com have?
```

---

## Keeping both approaches

The Python script (`dataforseo_audit_v2.py`) and the MCP server are complementary:

- **Python script** → automated, scheduled, generates a branded PDF for clients  
- **MCP + Claude** → ad-hoc research, quick questions, iterative analysis mid-project

Run the script for deliverables; use Claude conversationally for research.
