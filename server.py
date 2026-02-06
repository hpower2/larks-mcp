#!/usr/bin/env python3
"""
Larks Docs MCP Server
A simple MCP server for viewing Larks (Feishu) documents and returning raw content.
Each user provides their own bearer token via MCP configuration.
"""

import os
import json
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
from fastmcp import FastMCP
import requests

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("Larks Docs MCP Server")

# Larks API base URL
LARKS_API_BASE = "https://open.larksuite.com/open-apis"


def get_bearer_token() -> str:
    """
    Get bearer token from environment variable.
    Each user should set their own LARKS_BEARER_TOKEN in MCP configuration.
    
    Returns:
        Bearer token string
    
    Raises:
        ValueError if token is not set
    """
    bearer_token = os.getenv("LARKS_BEARER_TOKEN")
    
    if not bearer_token:
        raise ValueError(
            "LARKS_BEARER_TOKEN must be set in MCP configuration. "
            "Add it to your MCP client's env section."
        )
    
    return bearer_token


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
    
    # Parse URL to handle query parameters, fragments, etc.
    parsed = urlparse(url)
    
    # Get the path component (removes query params and fragments automatically)
    path = parsed.path
    
    # Remove leading/trailing slashes
    path = path.strip('/')
    
    # Extract the last part after the final '/'
    document_id = path.split('/')[-1] if path else ''
    
    # URL decode in case of encoded characters
    document_id = unquote(document_id)
    
    # Remove any remaining whitespace
    document_id = document_id.strip()
    
    return document_id


@mcp.tool()
def lark_docs(url: str, lang: int = 0) -> dict:
    """
    Get raw content from a Larks document URL.
    
    Extracts the document ID from the URL and forwards the request to Larks API
    using the user's bearer token from MCP configuration.
    
    Args:
        url: Larks document URL (e.g., https://advancegroup.sg.larksuite.com/wiki/JPfzwwtrui160NkKzCploKsog0f)
        lang: Language code (default: 0)
    
    Returns:
        Dictionary containing raw content and metadata
    """
    try:
        # Extract document ID from URL
        document_id = extract_document_id(url)
        
        if not document_id:
            return {
                "success": False,
                "error": "Could not extract document ID from URL"
            }
        
        # Get bearer token from environment (set by user in MCP config)
        bearer_token = get_bearer_token()
        
        # Forward request to Larks API
        api_url = f"{LARKS_API_BASE}/docx/v1/documents/{document_id}/raw_content"
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }
        params = {"lang": lang}
        
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("code") == 0:
            raw_data = data.get("data", {})
            return {
                "success": True,
                "document_id": document_id,
                "url": url,
                "raw_content": raw_data,
                "content": json.dumps(raw_data, indent=2, ensure_ascii=False) if isinstance(raw_data, dict) else str(raw_data)
            }
        else:
            return {
                "success": False,
                "error": f"API error: {data.get('msg', 'Unknown error')}",
                "code": data.get("code")
            }
            
    except ValueError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"HTTP request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Note: Resource handlers in FastMCP work best with simple identifiers
# For full URLs, use the get_document_raw_content tool instead


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
