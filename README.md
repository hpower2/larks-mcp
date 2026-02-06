# Larks Docs MCP Server

A simple Model Context Protocol (MCP) server for viewing Larks (Feishu) documents and returning raw content.

**Each user provides their own bearer token** - the server simply forwards requests with your token.

## Features

- **Get Document Raw Content**: Extract document ID from Larks URLs and fetch raw content using the docx API
- **Simple URL-based access**: Just provide a Larks document URL and get the raw content back
- **User-specific tokens**: Each user configures their own bearer token in MCP configuration

## Prerequisites

- Python 3.9 or higher
- A Larks (Feishu) account with API access
- Your own bearer token (tenant access token or user access token)

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd larks-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Getting Your Bearer Token

You need to obtain your own bearer token. There are a few ways:

1. **From Larks Open Platform**:
   - Go to [Larks Open Platform](https://open.feishu.cn/app)
   - Create an app or use an existing one
   - Get a tenant access token or user access token
   - Use that token as your bearer token

2. **Generate via API** (if you have App ID/Secret):
   ```bash
   curl -X POST 'https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal' \
     -H 'Content-Type: application/json' \
     -d '{"app_id":"your_app_id","app_secret":"your_app_secret"}'
   ```
   The response will contain `tenant_access_token` - use that as your bearer token.

3. **From your existing Larks integration**: If you already have a Larks app set up, use the access token you're already using.

## Usage

### Running the Server

Run the MCP server:
```bash
python server.py
```

The server will start and listen for MCP client connections via stdio.

### Using with MCP Clients

Configure your MCP client to use this server. **Each user must provide their own bearer token**.

#### For Cursor IDE

See **[CURSOR_SETUP.md](./CURSOR_SETUP.md)** for detailed step-by-step instructions.

Quick steps:
1. Go to `Cursor Settings` → `Features` → `MCP`
2. Click `+ Add New MCP Server`
3. Set Transport: `stdio`
4. Set Command: `python3` (or `python`)
5. Set Arguments: `/absolute/path/to/larks-mcp/server.py`
6. Add Environment Variable: `LARKS_BEARER_TOKEN` = `your_token_here`

#### For Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or similar:

```json
{
  "mcpServers": {
    "larks-docs": {
      "command": "python",
      "args": ["/path/to/larks-mcp/server.py"],
      "env": {
        "LARKS_BEARER_TOKEN": "your_bearer_token_here"
      }
    }
  }
}
```

**Important**: Replace `your_bearer_token_here` with your actual bearer token. Each user should use their own token.

### Testing Connection

Test your bearer token:
```bash
# Set your bearer token in .env first
echo "LARKS_BEARER_TOKEN=your_token_here" > .env

# Then test
python test_connection.py
```

## Available Tools

### `get_document_raw_content`

Get raw content from a Larks document URL. The tool automatically extracts the document ID from the URL and forwards the request to Larks API using your bearer token.

**Parameters:**
- `url` (required): Larks document URL (e.g., `https://advancegroup.sg.larksuite.com/wiki/JPfzwwtrui160NkKzCploKsog0f`)
- `lang` (optional): Language code (default: 0)

**Returns:**
- Dictionary with `success`, `document_id`, `url`, `raw_content`, and `content` fields

**Example:**
```python
result = get_document_raw_content("https://advancegroup.sg.larksuite.com/wiki/JPfzwwtrui160NkKzCploKsog0f")
# Returns raw content from the Larks docx API
```

## How It Works

1. User provides their bearer token via MCP configuration (`LARKS_BEARER_TOKEN` env var)
2. The tool extracts the document ID from the URL (the part after the last `/`)
3. Forwards the request to Larks API with the user's bearer token
4. Returns the raw content in JSON format

**The server is a simple proxy** - it doesn't store or share credentials. Each user uses their own token.

## API Endpoint

This server forwards requests to the Larks docx API endpoint:
```
GET /open-apis/docx/v1/documents/{document_id}/raw_content?lang=0
Authorization: Bearer {user_provided_token}
```

The server simply extracts the document ID from your URL and forwards the request with your bearer token.

## Troubleshooting

- **Import errors**: Make sure all dependencies are installed with `pip install -r requirements.txt`
- **Authentication errors**: 
  - Verify your bearer token is correct and not expired
  - Check that `LARKS_BEARER_TOKEN` is set in your MCP client configuration
  - Run `python test_connection.py` to validate your bearer token
  - Make sure your token has permission to access the document
- **Permission errors**: Ensure your bearer token has `docx:document:readonly` permission
- **URL parsing errors**: Make sure the URL is a valid Larks document URL ending with the document ID
- **Token expired**: Bearer tokens expire. Generate a new one if you get 401 errors

## License

MIT
