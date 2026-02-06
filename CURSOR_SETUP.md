# Installing Larks MCP Server in Cursor

This guide will help you install and configure the Larks MCP server in Cursor IDE.

## Prerequisites

1. **Python 3.9+ installed** - Check with `python3 --version`
2. **Dependencies installed** - Run `pip install -r requirements.txt` in this directory
3. **Your Larks Bearer Token** - See [README.md](./README.md) for how to get one

## Step-by-Step Installation

### Step 1: Install Dependencies

Open a terminal in this directory and run:

```bash
pip install -r requirements.txt
```

Or if you prefer to use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Note Your Server Path

Find the absolute path to `server.py`. For example:
- macOS/Linux: `/Users/yourname/personal/repository/larks-mcp/server.py`
- Windows: `C:\Users\yourname\personal\repository\larks-mcp\server.py`

You can get the full path by running:
```bash
# macOS/Linux
pwd
# Then append /server.py

# Or use realpath
realpath server.py
```

### Step 3: Configure in Cursor

1. **Open Cursor Settings**:
   - Press `Cmd+,` (macOS) or `Ctrl+,` (Windows/Linux)
   - Or go to `Cursor` → `Settings` → `Features` → `MCP`

2. **Add New MCP Server**:
   - Click the `+ Add New MCP Server` button
   - A configuration modal will appear

3. **Fill in the Configuration**:
   
   **Transport Type**: Select `stdio`
   
   **Name**: `larks-docs` (or any name you prefer)
   
   **Command**: 
   ```
   python3
   ```
   (or `python` on Windows, or full path like `/usr/bin/python3`)
   
   **Arguments**: 
   ```
   /absolute/path/to/larks-mcp/server.py
   ```
   Replace with your actual path from Step 2.
   
   **Environment Variables**: Click to add environment variables, then add:
   - **Key**: `LARKS_BEARER_TOKEN`
   - **Value**: Your bearer token (e.g., `u-f9el8G4Ph5DUZfKGDVm_3AlljflKg1UjVWaaaxoyyFq2`)

4. **Save**: Click Save/OK to add the server

### Step 4: Verify Installation

1. **Restart Cursor** (if needed)
2. **Check MCP Status**: 
   - Go back to `Settings` → `Features` → `MCP`
   - You should see `larks-docs` in your servers list
   - The status should show as connected/running

3. **Test the Tool**:
   - Open the Composer or Chat in Cursor
   - Try asking: "Get the raw content from this Larks document: https://advancegroup.sg.larksuite.com/wiki/JPfzwwtrui160NkKzCploKsog0f"
   - The MCP tool should be available and work

## Troubleshooting

### Server Not Appearing

- **Check Python Path**: Make sure `python3` (or `python`) is in your PATH
- **Check File Path**: Verify the path to `server.py` is correct and absolute
- **Check Permissions**: Make sure `server.py` is executable: `chmod +x server.py`

### Authentication Errors

- **Verify Token**: Make sure your `LARKS_BEARER_TOKEN` is correct
- **Test Token**: Run `python test_connection.py` to verify your token works
- **Token Expired**: Bearer tokens expire. Generate a new one if needed

### Import Errors

- **Install Dependencies**: Run `pip install -r requirements.txt` again
- **Check Python Version**: Ensure Python 3.9+ is being used
- **Virtual Environment**: If using venv, make sure Cursor uses the venv's Python

### Server Crashes

- **Check Logs**: Look at Cursor's MCP server logs in Settings
- **Test Manually**: Run `python server.py` in terminal to see error messages
- **Check Token Format**: Ensure token doesn't have extra spaces or quotes

## Alternative: Manual Config File (Advanced)

If you prefer editing config files directly, Cursor may store MCP config in:

- **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/mcp.json` or similar
- **Windows**: `%APPDATA%\Cursor\User\globalStorage\mcp.json` or similar
- **Linux**: `~/.config/Cursor/User/globalStorage/mcp.json` or similar

The format should be similar to:

```json
{
  "mcpServers": {
    "larks-docs": {
      "command": "python3",
      "args": ["/absolute/path/to/larks-mcp/server.py"],
      "env": {
        "LARKS_BEARER_TOKEN": "your_bearer_token_here"
      }
    }
  }
}
```

**Note**: The exact location may vary. Use Cursor's GUI settings when possible.

## Next Steps

Once installed, you can use the `get_document_raw_content` tool in Cursor's Composer or Chat to fetch Larks document content!
