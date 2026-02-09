# MCP Testing Guide

This guide provides a minimal setup for testing the MCP (Model Context Protocol) server.

## Prerequisites

- MCP server running on `http://localhost:48080`
- `curl` or any HTTP client

## Minimal Setup

### 1. Initialize MCP Session

Call the `initialize` method to start an MCP session:

```bash
curl -i -X POST http://localhost:48080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "init",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {
        "name": "curl-client",
        "version": "0.1.0"
      },
      "capabilities": {}
    }
  }'
```

**Important:** The `-i` flag includes response headers in the output.

### 2. Extract Session ID

From the response headers, extract the `mcp-session-id` value. For example:

```
mcp-session-id: 46728213ef0d4a72bb4cdaebc2792bd6
```

**Note:** Save this session ID as you'll need it for all subsequent requests.

### 3. Use Session ID in Subsequent Requests

#### List Available Tools

```bash
curl -X POST http://localhost:48080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'mcp-session-id: YOUR_SESSION_ID_HERE' \
  -d '{
    "jsonrpc": "2.0",
    "id": "tools",
    "method": "tools/list"
  }'
```

#### Call the `docs` Tool

```bash
curl -X POST http://localhost:48080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'mcp-session-id: YOUR_SESSION_ID_HERE' \
  -d '{
    "jsonrpc": "2.0",
    "id": "call-docs",
    "method": "tools/call",
    "params": {
      "name": "docs",
      "arguments": {
        "url": "https://advancegroup.sg.larksuite.com/wiki/Q4YXw99N8iqk7Gkr8rOuuDNPsLd"
      }
    }
  }'
```

## Quick Test Script

You can automate the session ID extraction:

```bash
# Step 1: Initialize and extract session ID
SESSION_ID=$(curl -s -i -X POST http://localhost:48080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "init",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {
        "name": "curl-client",
        "version": "0.1.0"
      },
      "capabilities": {}
    }
  }' | grep -i 'mcp-session-id' | cut -d' ' -f2 | tr -d '\r\n')

echo "Session ID: $SESSION_ID"

# Step 2: List tools
curl -X POST http://localhost:48080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H "mcp-session-id: $SESSION_ID" \
  -d '{
    "jsonrpc": "2.0",
    "id": "tools",
    "method": "tools/list"
  }'
```

## Notes

- The `mcp-session-id` header is required for all requests after initialization
- Each initialization creates a new session with a unique session ID
- The session ID is returned in the response headers, not in the JSON body
