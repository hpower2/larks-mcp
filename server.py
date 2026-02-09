#!/usr/bin/env python3
"""
MCP Server for Larks API
Converted from Node.js server.ts using FastMCP
Supports streamable HTTP transport
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Any

# Load environment variables from .env file
# This must be done BEFORE any other imports that might use environment variables
from dotenv import load_dotenv

# Load .env file from the same directory as this script
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)  # override=False means env vars take precedence

try:
    from mcp.server.fastmcp import FastMCP
    from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
    from fastapi import Request
    FASTMCP_AVAILABLE = True
except ImportError as e:
    FASTMCP_AVAILABLE = False
    print(f'FastMCP not available: {e}', file=sys.stderr)
    print('Install with: pip install "mcp[fastmcp]"', file=sys.stderr)
    sys.exit(1)

import tools
import auth

# Create FastMCP server
port = int(os.getenv('MCP_PORT', '48080'))
host = os.getenv('MCP_HOST', '0.0.0.0')
mcp = FastMCP('larks-docs-mcp', json_response=True, host=host, port=port)


# OAuth callback endpoint
@mcp.custom_route('/oauth/callback', methods=['GET'])
async def oauth_callback(request: Request):
    """Handle OAuth callback"""
    try:
        query_params = dict(request.query_params)
        code = query_params.get('code')
        state = query_params.get('state')
        error = query_params.get('error')
        
        if error:
            error_html = f'''
            <html>
                <head><title>OAuth Error</title></head>
                <body>
                    <h1>❌ OAuth Authorization Failed</h1>
                    <p>Error: {error}</p>
                    <p>You can close this window.</p>
                </body>
            </html>
            '''
            return HTMLResponse(content=error_html, status_code=400)
        
        if not code:
            error_html = '''
            <html>
                <head><title>OAuth Error</title></head>
                <body>
                    <h1>❌ Missing Authorization Code</h1>
                    <p>No authorization code received from OAuth provider.</p>
                    <p>You can close this window.</p>
                </body>
            </html>
            '''
            return HTMLResponse(content=error_html, status_code=400)
        
        # Exchange code for token using the callback tool
        result = await tools.lark_login_callback(code, state)
        
        if result.get('success'):
            success_html = f'''
            <html>
                <head><title>Login Success</title></head>
                <body style="font-family: Arial, sans-serif; padding: 40px; text-align: center;">
                    <h1 style="color: green;">✅ Login Successful!</h1>
                    <p>You have been authenticated with Larks.</p>
                    <p><strong>Access Token:</strong> {result.get('access_token', 'Received')}</p>
                    <p><strong>Expires In:</strong> {result.get('expires_in', 'N/A')} seconds</p>
                    <p style="margin-top: 30px; color: #666;">You can now close this window and use the MCP tools.</p>
                    <p style="margin-top: 20px;">
                        <button onclick="window.close()" style="padding: 10px 20px; font-size: 16px; cursor: pointer;">
                            Close Window
                        </button>
                    </p>
                </body>
            </html>
            '''
            return HTMLResponse(content=success_html)
        else:
            error_msg = result.get('error', 'Unknown error')
            error_html = f'''
            <html>
                <head><title>Login Failed</title></head>
                <body>
                    <h1>❌ Login Failed</h1>
                    <p>Error: {error_msg}</p>
                    <p>You can close this window.</p>
                </body>
            </html>
            '''
            return HTMLResponse(content=error_html, status_code=400)
    except Exception as error:
        error_html = f'''
        <html>
            <head><title>Login Error</title></head>
            <body>
                <h1>❌ Login Error</h1>
                <p>Failed to exchange authorization code: {str(error)}</p>
                <p>You can close this window.</p>
            </body>
        </html>
        '''
        return HTMLResponse(content=error_html, status_code=500)


# Health check endpoint
@mcp.custom_route('/health', methods=['GET'])
async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        'status': 'ok',
        'service': 'larks-mcp',
        'transport': 'streamableHttp',
        'port': port,
    })


# Token status endpoint
@mcp.custom_route('/auth/status', methods=['GET'])
async def token_status(request: Request):
    """Check bearer token status and expiration"""
    # Get token status from auth module
    token_status = auth.get_token_status()
    
    # Also check environment variable token
    env_token = os.getenv('LARKS_BEARER_TOKEN')
    has_env_token = env_token is not None
    
    response = {
        'userToken': token_status,
        'environmentToken': {
            'hasToken': has_env_token,
            'tokenLength': len(env_token) if env_token else 0,
            'token': env_token[:20] + '...' if env_token and len(env_token) > 20 else env_token if env_token else None,
        },
        'currentTime': int(time.time()),
        'currentTimeISO': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
    }
    
    return JSONResponse(response)


# Static file serving for images
@mcp.custom_route('/static/{filename:path}', methods=['GET'])
async def serve_static(request: Request):
    """Serve static image files"""
    # Extract filename from request path
    path = request.url.path
    if not path.startswith('/static/'):
        return JSONResponse({'error': 'Invalid path'}, status_code=400)
    
    filename = path[8:]  # Remove '/static/' prefix
    if not filename:
        return JSONResponse({'error': 'Filename required'}, status_code=400)
    
    static_dir = Path(__file__).parent / 'static'
    filepath = static_dir / filename
    
    # Security check: ensure file is within static directory
    try:
        filepath.resolve().relative_to(static_dir.resolve())
    except ValueError:
        return JSONResponse({'error': 'Invalid file path'}, status_code=403)
    
    if not filepath.exists():
        return JSONResponse({'error': 'File not found'}, status_code=404)
    
    return FileResponse(filepath)


# MCP Tools
@mcp.tool()
async def login_interactive(
    LARKS_CLIENT_ID: Optional[str] = None,
    LARKS_CLIENT_SECRET: Optional[str] = None,
    LARKS_REDIRECT_URI: Optional[str] = None,
) -> str:
    """Interactive OAuth login flow. This tool will guide you through the login process step by step.
    
    Credentials can be provided via tool parameters, environment variables, or .env file.
    """
    result = await tools.lark_login_interactive(
        LARKS_CLIENT_ID,
        LARKS_CLIENT_SECRET,
        LARKS_REDIRECT_URI
    )
    
    if result.get('success') and result.get('authorization_url'):
        auth_url = result.get('authorization_url', '')
        message = result.get('message') or f"Please open this URL to authorize: {auth_url}"
        return (
            f"{message}\n\n"
            f"🔗 Authorization URL: {auth_url}\n\n"
            f"State: {result.get('state')}\n\n"
            f"{result.get('next_step') or ''}"
        )
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def docs(
    url: str,
    lang: int = 0,
    LARKS_BEARER_TOKEN: Optional[str] = None,
    LARKS_CLIENT_ID: Optional[str] = None,
    LARKS_CLIENT_SECRET: Optional[str] = None,
    LARKS_REDIRECT_URI: Optional[str] = None,
) -> str:
    """Get structured content from a Larks document URL. Extracts the document ID from the URL, fetches blocks recursively, and includes image URLs.
    
    Returns formatted markdown content with images. Uses the blocks API for better structure.
    
    Credentials can be provided via tool parameters, environment variables, or .env file.
    """
    if not url:
        return json.dumps({
            'success': False,
            'error': 'URL is required',
        }, indent=2)
    
    oauth_config = None
    if LARKS_CLIENT_ID or LARKS_CLIENT_SECRET or LARKS_REDIRECT_URI:
        oauth_config = {
            'LARKS_CLIENT_ID': LARKS_CLIENT_ID,
            'LARKS_CLIENT_SECRET': LARKS_CLIENT_SECRET,
            'LARKS_REDIRECT_URI': LARKS_REDIRECT_URI,
        }
    
    result = await tools.lark_docs(url, lang, oauth_config, LARKS_BEARER_TOKEN)
    
    if result.get('needsLogin') and result.get('authorization_url'):
        auth_url = result.get('authorization_url', '')
        message = result.get('message') or f"Authentication required. Please open this URL to authorize: {auth_url}"
        return (
            f"{message}\n\n"
            f"🔗 Authorization URL: {auth_url}\n\n"
            f"State: {result.get('state')}\n\n"
            f"{result.get('next_step') or ''}"
        )
    
    # Return formatted content if available
    # FastMCP will automatically wrap string returns in MCP content format
    # The markdown content with actual newlines will be properly preserved
    if result.get('success') and result.get('content'):
        return result.get('content', '')
    
    # Return error as JSON
    return json.dumps(result, indent=2)


def main():
    """Main entry point - start server with streamable HTTP transport"""
    # Log which .env file was loaded (if any)
    if env_path.exists():
        print(f'Loaded environment variables from: {env_path}', file=sys.stderr)
    else:
        print(f'No .env file found at {env_path}, using environment variables only', file=sys.stderr)
    
    print(f'Larks MCP Server starting...', file=sys.stderr)
    print(f'Transport: streamable-http', file=sys.stderr)
    print(f'MCP endpoint: http://{host}:{port}/mcp', file=sys.stderr)
    print(f'OAuth callback: http://{host}:{port}/oauth/callback', file=sys.stderr)
    print(f'Health check: http://{host}:{port}/health', file=sys.stderr)
    print(f'Token status: http://{host}:{port}/auth/status', file=sys.stderr)
    
    # Log configuration status
    config_status = {
        'LARKS_CLIENT_ID': 'SET' if os.getenv('LARKS_CLIENT_ID') else 'NOT SET',
        'LARKS_CLIENT_SECRET': 'SET' if os.getenv('LARKS_CLIENT_SECRET') else 'NOT SET',
        'LARKS_REDIRECT_URI': os.getenv('LARKS_REDIRECT_URI', 'NOT SET'),
        'LARKS_BEARER_TOKEN': 'SET' if os.getenv('LARKS_BEARER_TOKEN') else 'NOT SET',
    }
    print(f'Configuration:', file=sys.stderr)
    for key, value in config_status.items():
        print(f'  {key}: {value}', file=sys.stderr)
    
    # Start FastMCP server with streamable HTTP transport
    mcp.run(transport='streamable-http')


if __name__ == '__main__':
    main()
