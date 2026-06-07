FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e .

ENV MCP_TRANSPORT=sse
ENV MCP_API_KEY=""
ENV PORT=8000
ENV NTFY_URL=""
ENV NTFY_TOKEN=""

EXPOSE 8000

CMD ["ntfy-mcp-server"]
