"""
Utility functions for Larks MCP server
Converted from Node.js utils.ts
"""
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)  # override=False means env vars take precedence

import auth


def extract_document_id(url: str) -> str:
    """
    Extract document ID from a Larks document URL.
    
    Handles URLs with query parameters, fragments, trailing slashes, and whitespace.
    
    Args:
        url: Larks document URL (e.g., https://advancegroup.sg.larksuite.com/wiki/JPfzwwtrui160NkKzCploKsog0f?fromScene=spaceOverview)
    
    Returns:
        Document ID (the last part after the final '/')
    """
    # Strip whitespace
    url = url.strip()
    
    try:
        # Parse URL to handle query parameters, fragments, etc.
        parsed_url = urllib.parse.urlparse(url)
        
        # Get the path component (removes query params and fragments automatically)
        path = parsed_url.path
        
        # Remove leading/trailing slashes
        path = path.strip('/')
        
        # Extract the last part after the final '/'
        document_id = path.split('/')[-1] if path else ''
        
        # URL decode in case of encoded characters
        decoded_id = urllib.parse.unquote(document_id)
        
        # Remove any remaining whitespace
        return decoded_id.strip()
    except Exception:
        # If URL parsing fails, try simple string manipulation
        trimmed = url.strip()
        without_query = trimmed.split('?')[0].split('#')[0]
        parts = [p for p in without_query.split('/') if p]
        return parts[-1] if parts else ''


def get_bearer_token(provided_token: Optional[str] = None) -> str:
    """
    Get bearer token from parameter, OAuth user token, or environment variable.
    Priority: Parameter > OAuth user token > Environment variable
    
    Args:
        provided_token: Optional bearer token provided as parameter
    
    Returns:
        Bearer token string
    
    Raises:
        ValueError: if token is not set
    """
    # First priority: Use provided token parameter
    if provided_token:
        return provided_token
    
    # Second priority: OAuth user access token (from login_interactive)
    user_token = auth.get_user_access_token()
    if user_token:
        return user_token
    
    # Third priority: Environment variable (from mcp.json or .env)
    bearer_token = os.getenv('LARKS_BEARER_TOKEN')
    
    if not bearer_token:
        raise ValueError(
            'No access token available. Please either:\n'
            '1. Provide LARKS_BEARER_TOKEN as a parameter, or\n'
            '2. Use the login tool to authenticate via OAuth, or\n'
            '3. Set LARKS_BEARER_TOKEN in MCP configuration or .env file.'
        )
    
    return bearer_token
