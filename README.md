# ntfy-mcp-server

> MCP-Server für selbst gehostetes [ntfy.sh](https://ntfy.sh). Push-Notifications senden und lesen aus Claude.

## Tools

| Tool | Zweck |
|---|---|
| `ntfy_send` | Notification senden (Topic, Title, Priority, Tags, Click, Delay, Markdown, Icon) |
| `ntfy_send_with_actions` | Mit View/HTTP/Broadcast-Action-Buttons |
| `ntfy_get_messages` | Gecachte Messages eines Topics holen |
| `ntfy_list_topics` | Account-Profil + Zugriffsrechte |

## Auth (identisch zu whisper-mcp / hero-mcp / paperless-mcp)

1. **Statischer Bearer** (`MCP_API_KEY`) — Claude Desktop / direkte Clients
2. **JWT via Authelia OIDC Introspection** — Claude.ai

## Deploy

`docker compose up -d` — env-vars siehe [.env.example](./.env.example).
