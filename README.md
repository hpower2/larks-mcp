# Larks MCP Server - Python Implementation

Python implementation of the Larks MCP server using FastMCP, converted from Node.js/TypeScript.

## Installation

```bash
cd python
pip install -r requirements.txt
```

## Running the Server

### Option 1: Using Docker Compose (Recommended)

```bash
# Copy .env.example to .env and fill in your credentials
cp .env.example .env
# Edit .env with your credentials

# Build and start the container
docker compose up -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

### Option 2: Using .env file (Local)

```bash
# Copy .env.example to .env and fill in your credentials
cp .env.example .env
# Edit .env with your credentials

# Run the server
python server.py
```

### Option 3: Using environment variables

```bash
# Set environment variables
export LARKS_CLIENT_ID=your_client_id
export LARKS_CLIENT_SECRET=your_client_secret
export MCP_PORT=48080

# Run the server
python server.py
```

**Note**: Environment variables take precedence over `.env` file values.

## Configuration

The server loads configuration from `.env` file and environment variables (env vars take precedence):

- `LARKS_CLIENT_ID`: OAuth app ID (required)
- `LARKS_CLIENT_SECRET`: OAuth app secret (required)
- `LARKS_REDIRECT_URI`: OAuth redirect URI (default: `http://localhost:48080/oauth/callback`)
- `LARKS_BEARER_TOKEN`: Direct bearer token (optional, fallback if OAuth not used)
- `LARKS_DOMAIN`: OAuth domain (default: `https://open.larksuite.com`)
- `LARKS_API_DOMAIN`: API domain (default: `https://open.larksuite.com`)
- `MCP_PORT`: Server port (default: `48080`)
- `MCP_HOST`: Server host (default: `0.0.0.0`)

## Cursor MCP Configuration

Use streamable HTTP transport:

```json
{
  "mcpServers": {
    "larks-docs": {
      "transport": "streamableHttp",
      "url": "http://localhost:48080/mcp"
    }
  }
}
```

Start the server separately:
```bash
python server.py
```

## Docker

### Building the Image

```bash
docker build -t larks-mcp-python .
```

### Running with Docker Compose

```bash
# Start the service
docker compose up -d

# View logs
docker compose logs -f larks-mcp-python

# Stop the service
docker compose down
```

### Environment Variables in Docker

You can provide environment variables in several ways:

1. **Via docker-compose.yml** (recommended for Docker):
   ```yaml
   environment:
     - LARKS_CLIENT_ID=your_client_id
     - LARKS_CLIENT_SECRET=your_client_secret
   ```

2. **Via .env file** (mounted as volume):
   ```yaml
   volumes:
     - ./.env:/app/.env:ro
   ```

3. **Via host environment variables**:
   ```bash
   export LARKS_CLIENT_ID=your_client_id
   export LARKS_CLIENT_SECRET=your_client_secret
   docker compose up -d
   ```

## Features

- ✅ Streamable HTTP transport (plain HTTP POST, no SSE)
- ✅ OAuth authentication flow
- ✅ Document content fetching
- ✅ Same API as Node.js version
- ✅ Environment variable and .env file configuration
- ✅ Automatic token refresh handling
- ✅ Docker support with docker-compose

## Differences from Node.js Version

- Uses FastMCP for easier server setup
- Async/await pattern throughout
- Python-native HTTP client (httpx)
- Same functionality, cleaner Python code
- Uses python-dotenv for .env file support
