"""
OAuth authentication for Larks API
Converted from Node.js auth.ts
"""
import os
import json
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)  # override=False means env vars take precedence

# Store user access token (in-memory, could be persisted)
user_access_token: Optional[str] = None
user_refresh_token: Optional[str] = None
user_access_token_expires_at: Optional[int] = None

# Store OAuth configuration (set from tool parameters)
stored_oauth_config: Optional[Dict[str, str]] = None


class OAuthConfig:
    """OAuth configuration"""
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        domain: Optional[str] = None,
        api_domain: Optional[str] = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.domain = domain or 'https://accounts.larksuite.com'
        self.api_domain = api_domain or 'https://open.larksuite.com'


def set_oauth_config(config: Dict[str, str]) -> None:
    """Set OAuth configuration from tool parameters"""
    global stored_oauth_config
    stored_oauth_config = config
    print('[setOAuthConfig] OAuth config stored', file=os.sys.stderr)
    print(f'[setOAuthConfig]   LARKS_CLIENT_ID: {config.get("clientId", "")[:10]}...' if config.get("clientId") else '[setOAuthConfig]   LARKS_CLIENT_ID: NOT SET', file=os.sys.stderr)
    print(f'[setOAuthConfig]   LARKS_CLIENT_SECRET: SET' if config.get("clientSecret") else '[setOAuthConfig]   LARKS_CLIENT_SECRET: NOT SET', file=os.sys.stderr)
    print(f'[setOAuthConfig]   LARKS_REDIRECT_URI: {config.get("redirectUri")}', file=os.sys.stderr)


def get_oauth_config(override_config: Optional[Dict[str, str]] = None) -> OAuthConfig:
    """
    Get OAuth configuration from stored config or environment variables
    
    Priority:
    1. Override config (highest priority) - from tool parameters
    2. Stored config (set via setOAuthConfig from tool parameters)
    3. Environment variables (fallback)
    """
    http_port = os.getenv('MCP_PORT', '48080')
    default_redirect_uri = f'http://localhost:{http_port}/oauth/callback'
    
    # Use override config if provided (highest priority)
    if override_config:
        return OAuthConfig(
            client_id=override_config.get('clientId', ''),
            client_secret=override_config.get('clientSecret', ''),
            redirect_uri=override_config.get('redirectUri') or default_redirect_uri,
            domain=override_config.get('domain') or os.getenv('LARKS_DOMAIN', 'https://accounts.larksuite.com'),
            api_domain=override_config.get('apiDomain') or os.getenv('LARKS_API_DOMAIN', 'https://open.larksuite.com'),
        )
    
    # Use stored config if available
    if stored_oauth_config:
        return OAuthConfig(
            client_id=stored_oauth_config.get('clientId', ''),
            client_secret=stored_oauth_config.get('clientSecret', ''),
            redirect_uri=stored_oauth_config.get('redirectUri') or default_redirect_uri,
            domain=stored_oauth_config.get('domain') or os.getenv('LARKS_DOMAIN', 'https://accounts.larksuite.com'),
            api_domain=stored_oauth_config.get('apiDomain') or os.getenv('LARKS_API_DOMAIN', 'https://open.larksuite.com'),
        )
    
    # Fallback to environment variables
    client_id = os.getenv('LARKS_CLIENT_ID', '')
    client_secret = os.getenv('LARKS_CLIENT_SECRET', '')
    redirect_uri = os.getenv('LARKS_REDIRECT_URI', default_redirect_uri)
    
    # Log configuration status (without sensitive data)
    print('[getOAuthConfig] Configuration check:', file=os.sys.stderr)
    print(f'[getOAuthConfig]   LARKS_CLIENT_ID: {client_id[:10] + "..." if client_id else "NOT SET"}', file=os.sys.stderr)
    print(f'[getOAuthConfig]   LARKS_CLIENT_SECRET: {"SET" if client_secret else "NOT SET"}', file=os.sys.stderr)
    print(f'[getOAuthConfig]   LARKS_REDIRECT_URI: {redirect_uri}', file=os.sys.stderr)
    print(f'[getOAuthConfig]   MCP_PORT: {http_port}', file=os.sys.stderr)
    
    return OAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        domain=os.getenv('LARKS_DOMAIN', 'https://accounts.larksuite.com'),
        api_domain=os.getenv('LARKS_API_DOMAIN', 'https://open.larksuite.com'),
    )


def generate_auth_url(config: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Generate OAuth authorization URL"""
    oauth_config = get_oauth_config(config)
    
    if not oauth_config.client_id:
        raise ValueError(
            'LARKS_CLIENT_ID not configured. Please provide it as a parameter to login_interactive or set it in your MCP configuration (mcp.json) under the "env" section.'
        )
    
    if not oauth_config.client_secret:
        raise ValueError(
            'LARKS_CLIENT_SECRET not configured. Please provide it as a parameter to login_interactive or set it in your MCP configuration (mcp.json) under the "env" section.'
        )
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Build authorization URL
    # Use accounts.larksuite.com for OAuth authorization endpoint
    # Format: /open-apis/authen/v1/index with app_id parameter
    auth_domain = oauth_config.domain
    params = {
        'app_id': oauth_config.client_id,  # Use app_id instead of client_id for this endpoint
        'redirect_uri': oauth_config.redirect_uri,
        'state': state,
        'scope': 'board:whiteboard:node:read docs:document.content:read docs:document.media:download docx:document:readonly drive:drive.metadata:readonly sheets:spreadsheet:readonly',  # Required scopes for accessing various Larks resources
    }
    
    # Use /index endpoint instead of /oidc/authorize
    auth_url = f"{auth_domain}/open-apis/authen/v1/index?{urllib.parse.urlencode(params)}"
    
    return {'url': auth_url, 'state': state}


async def exchange_code_for_token(code: str, config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Exchange authorization code for user access token"""
    oauth_config = get_oauth_config(config)
    
    if not oauth_config.client_id or not oauth_config.client_secret:
        raise ValueError(
            'OAuth credentials not configured. Please provide LARKS_CLIENT_ID and LARKS_CLIENT_SECRET as parameters to login_interactive or set them in your MCP configuration (mcp.json) under the "env" section.'
        )
    
    try:
        # Use direct HTTP request for OAuth token exchange
        # Use API domain for token exchange, not the OAuth domain
        # Use v2 OAuth token endpoint (v1/oidc/access_token is deprecated)
        api_domain = oauth_config.api_domain
        token_url = f"{api_domain}/open-apis/authen/v2/oauth/token"
        
        request_body = {
            'grant_type': 'authorization_code',
            'client_id': oauth_config.client_id,  # v2 endpoint uses client_id
            'client_secret': oauth_config.client_secret,  # v2 endpoint uses client_secret
            'code': code,
            'redirect_uri': oauth_config.redirect_uri,
        }
        
        print('=== Token Exchange Request ===', file=os.sys.stderr)
        print(f'URL: {token_url}', file=os.sys.stderr)
        print(f'Request body: {json.dumps({**request_body, "client_secret": "***HIDDEN***", "code": code[:10] + "..."}, indent=2)}', file=os.sys.stderr)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                json=request_body,
                headers={'Content-Type': 'application/json'},
            )
        
        print(f'Response status: {response.status_code} {response.reason_phrase}', file=os.sys.stderr)
        print(f'Response headers: {json.dumps(dict(response.headers), indent=2)}', file=os.sys.stderr)
        
        response_text = response.text
        print(f'Response body: {response_text}', file=os.sys.stderr)
        
        try:
            response_data = response.json()
            print(f'Parsed response data: {json.dumps({"code": response_data.get("code"), "msg": response_data.get("msg"), "error": response_data.get("error"), "error_description": response_data.get("error_description"), "has_access_token": bool(response_data.get("access_token")), "has_data": bool(response_data.get("data"))}, indent=2)}', file=os.sys.stderr)
        except Exception as e:
            print(f'Failed to parse JSON: {e}', file=os.sys.stderr)
            raise ValueError(f'Invalid JSON response: {response_text[:200]}')
        
        if not response.is_success:
            error_msg = response_data.get('msg') or response_data.get('error_description') or response.reason_phrase
            print(f'HTTP error: {response.status_code} {error_msg}', file=os.sys.stderr)
            raise ValueError(f'Failed to get access token (HTTP {response.status_code}): {error_msg or response_text[:200]}')
        
        # v2 endpoint returns code: 0 for success, v1 also uses code: 0
        # v2 can also return error/error_description format
        if response_data.get('error'):
            error_desc = response_data.get('error_description', 'Unknown error')
            print(f'OAuth error: {response_data.get("error")} description: {error_desc}', file=os.sys.stderr)
            raise ValueError(f'OAuth error: {response_data.get("error")} - {error_desc}')
        
        if response_data.get('code') is not None and response_data.get('code') != 0:
            error_msg = response_data.get('msg', 'Unknown error')
            print(f'API error code: {response_data.get("code")} message: {error_msg}', file=os.sys.stderr)
            raise ValueError(f'Failed to get access token (code {response_data.get("code")}): {error_msg}')
        
        # v2 endpoint format: token is directly in response body (has access_token property)
        # v1 endpoint format: token is in data.data
        token_data = response_data if response_data.get('access_token') else response_data.get('data', {})
        
        if not token_data or not token_data.get('access_token'):
            raise ValueError('No access token in response')
        
        global user_access_token, user_refresh_token, user_access_token_expires_at
        user_access_token = token_data['access_token']
        user_refresh_token = token_data.get('refresh_token')
        
        # Calculate expiration timestamp (expires_in is in seconds)
        expires_in = token_data.get('expires_in')
        if expires_in:
            user_access_token_expires_at = int(time.time()) + expires_in
        else:
            user_access_token_expires_at = None
        
        return {
            'accessToken': user_access_token,
            'refreshToken': user_refresh_token,
            'expiresIn': expires_in,
        }
    except Exception as error:
        if isinstance(error, ValueError):
            raise
        raise ValueError(f'Login failed: {str(error)}')


def clear_tokens() -> None:
    """Clear stored tokens (logout)"""
    global user_access_token, user_refresh_token, user_access_token_expires_at
    user_access_token = None
    user_refresh_token = None
    user_access_token_expires_at = None


def is_token_expired() -> bool:
    """Check if the current access token is expired"""
    global user_access_token, user_access_token_expires_at
    
    if not user_access_token:
        return True
    
    if user_access_token_expires_at is None:
        # If expires_at is not set, assume token is valid (backward compatibility)
        return False
    
    # Check if token has expired (with 60 second buffer to refresh before actual expiration)
    current_time = int(time.time())
    return current_time >= (user_access_token_expires_at - 60)


def get_user_access_token() -> Optional[str]:
    """Get current user access token, returns None if expired"""
    if is_token_expired():
        return None
    return user_access_token


def get_token_status() -> Dict[str, Any]:
    """Get current token status including expiration info"""
    global user_access_token, user_access_token_expires_at
    
    has_token = user_access_token is not None
    expired = is_token_expired()
    
    status = {
        'hasToken': has_token,
        'isExpired': expired,
        'token': user_access_token[:20] + '...' if user_access_token and len(user_access_token) > 20 else user_access_token if user_access_token else None,
        'tokenLength': len(user_access_token) if user_access_token else 0,
    }
    
    if user_access_token_expires_at:
        current_time = int(time.time())
        expires_at = user_access_token_expires_at
        expires_in = expires_at - current_time
        status['expiresAt'] = expires_at
        status['expiresIn'] = expires_in
        status['expiresInSeconds'] = expires_in
        status['expiresInMinutes'] = round(expires_in / 60, 2) if expires_in > 0 else 0
        status['expiresAtISO'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at))
    else:
        status['expiresAt'] = None
        status['expiresIn'] = None
        status['expiresInSeconds'] = None
        status['expiresInMinutes'] = None
        status['expiresAtISO'] = None
    
    return status
