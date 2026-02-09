"""
MCP tool implementations for Larks
Converted from Node.js tools.ts
"""
import os
import base64
import io
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import httpx
from urllib.parse import quote

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)  # override=False means env vars take precedence

import auth
import utils


async def ensure_authenticated(
    oauth_config: Optional[Dict[str, str]] = None,
    LARKS_BEARER_TOKEN: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ensure user is authenticated. If not, automatically trigger login_interactive.
    Returns dict with needsLogin flag and optional loginResult.
    """
    print('[ensure_authenticated] Checking authentication status...', file=os.sys.stderr)
    
    # If bearer token is provided as parameter, skip authentication check
    if LARKS_BEARER_TOKEN:
        return {'needsLogin': False}
    
    # Check if user access token exists
    user_token = auth.get_user_access_token()
    if user_token:
        return {'needsLogin': False}
    
    # Check if environment variable token exists
    bearer_token = os.getenv('LARKS_BEARER_TOKEN')
    if bearer_token:
        return {'needsLogin': False}
    
    # No token available, trigger login_interactive
    login_result = await lark_login_interactive(
        oauth_config.get('LARKS_CLIENT_ID') if oauth_config else None,
        oauth_config.get('LARKS_CLIENT_SECRET') if oauth_config else None,
        oauth_config.get('LARKS_REDIRECT_URI') if oauth_config else None,
    )
    return {
        'needsLogin': True,
        'loginResult': login_result,
    }


async def handle_token_expiration(
    oauth_config: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Handle token expiration by clearing tokens and triggering login"""
    # Clear expired tokens
    auth.clear_tokens()
    
    # Trigger login
    login_result = await lark_login_interactive(
        oauth_config.get('LARKS_CLIENT_ID') if oauth_config else None,
        oauth_config.get('LARKS_CLIENT_SECRET') if oauth_config else None,
        oauth_config.get('LARKS_REDIRECT_URI') if oauth_config else None,
    )
    return {
        'needsLogin': True,
        'loginResult': login_result,
    }


async def lark_login_interactive(
    LARKS_CLIENT_ID: Optional[str] = None,
    LARKS_CLIENT_SECRET: Optional[str] = None,
    LARKS_REDIRECT_URI: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tool: login_interactive
    Interactive OAuth login flow.
    """
    try:
        print('[larkLoginInteractive] Starting OAuth login flow...', file=os.sys.stderr)
        
        # Build OAuth config from parameters or fallback to environment variables
        oauth_config: Dict[str, Optional[str]] = {}
        
        if LARKS_CLIENT_ID:
            oauth_config['clientId'] = LARKS_CLIENT_ID
        if LARKS_CLIENT_SECRET:
            oauth_config['clientSecret'] = LARKS_CLIENT_SECRET
        if LARKS_REDIRECT_URI:
            oauth_config['redirectUri'] = LARKS_REDIRECT_URI
        
        # Store the config for later use (e.g., in exchangeCodeForToken)
        if oauth_config.get('clientId') and oauth_config.get('clientSecret') and oauth_config.get('redirectUri'):
            auth.set_oauth_config(oauth_config)
        
        # Validate that required credentials are available (from params or env)
        config = auth.get_oauth_config(oauth_config if oauth_config else None)
        if not config.client_id:
            return {
                'success': False,
                'error': 'LARKS_CLIENT_ID not provided. Please provide it as a parameter to login_interactive or set it in your MCP configuration (mcp.json) under the "env" section.',
            }
        if not config.client_secret:
            return {
                'success': False,
                'error': 'LARKS_CLIENT_SECRET not provided. Please provide it as a parameter to login_interactive or set it in your MCP configuration (mcp.json) under the "env" section.',
            }
        
        auth_result = auth.generate_auth_url(oauth_config if oauth_config else None)
        
        print('[larkLoginInteractive] Generated authorization URL', file=os.sys.stderr)
        print(f'[larkLoginInteractive] Redirect URI: {config.redirect_uri}', file=os.sys.stderr)
        
        return {
            'success': True,
            'step': 'authorization',
            'authorization_url': auth_result['url'],
            'state': auth_result['state'],
            'message': (
                '🔐 Interactive Login Started\n\n'
                f'📋 Please open this URL in your browser:\n\n{auth_result["url"]}\n\n'
                'After you authorize, you\'ll be redirected with an authorization code.\n'
                'The OAuth callback will be handled automatically.'
            ),
            'next_step': 'After opening the URL and authorizing, the OAuth callback will complete the login automatically.',
        }
    except Exception as error:
        print(f'[larkLoginInteractive] Error: {error}', file=os.sys.stderr)
        return {
            'success': False,
            'error': str(error) if isinstance(error, Exception) else str(error),
        }


async def lark_login_callback(
    code: str,
    state: Optional[str] = None,
    LARKS_CLIENT_ID: Optional[str] = None,
    LARKS_CLIENT_SECRET: Optional[str] = None,
    LARKS_REDIRECT_URI: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tool: login_callback
    Exchange authorization code for user access token.
    """
    try:
        oauth_config: Dict[str, Optional[str]] = {}
        
        if LARKS_CLIENT_ID:
            oauth_config['clientId'] = LARKS_CLIENT_ID
        if LARKS_CLIENT_SECRET:
            oauth_config['clientSecret'] = LARKS_CLIENT_SECRET
        if LARKS_REDIRECT_URI:
            oauth_config['redirectUri'] = LARKS_REDIRECT_URI
        
        result = await auth.exchange_code_for_token(code, oauth_config if oauth_config else None)
        
        return {
            'success': True,
            'message': '✅ Login successful! You are now authenticated with Larks.',
            'access_token': result['accessToken'][:20] + '...',
            'expires_in': result.get('expiresIn'),
            'refresh_token': '***' if result.get('refreshToken') else None,
            'next_steps': 'You can now use docs() to fetch document content.',
        }
    except Exception as error:
        return {
            'success': False,
            'error': str(error) if isinstance(error, Exception) else str(error),
        }


async def _fetch_blocks_page(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    document_id: str,
    block_id: Optional[str] = None,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch a single page of blocks.
    """
    # Build API URL
    if block_id:
        api_url = f'{api_domain}/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children'
    else:
        api_url = f'{api_domain}/open-apis/docx/v1/documents/{document_id}/blocks'
    
    # Add pagination token if provided
    params = {}
    if page_token:
        params['page_token'] = page_token
    
    response = await client.get(
        api_url,
        params=params,
        headers={
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        },
    )
    
    if not response.is_success:
        raise Exception(f'Failed to fetch blocks: {response.status_code} {response.text}')
    
    data = response.json()
    if data.get('code') != 0:
        raise Exception(f'API error: {data.get("msg") or "Unknown error"}')
    
    return data.get('data', {})


async def _fetch_blocks_recursive(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    document_id: str,
    block_id: Optional[str] = None,
    all_blocks: Optional[Dict[str, Any]] = None,
) -> list:
    """
    Fetch all blocks from a document.
    The main blocks query already returns all blocks including children, so we don't need to recursively fetch children separately.
    Returns a flat list of all blocks.
    """
    if all_blocks is None:
        all_blocks = {}  # Use dict to avoid duplicates by block_id
    
    # Fetch all pages for the main blocks query
    # When block_id is None, this fetches all blocks including children
    page_token = None
    while True:
        page_data = await _fetch_blocks_page(
            client, api_domain, bearer_token, document_id, block_id, page_token
        )
        
        items = page_data.get('items', [])
        
        # Add items to our collection (avoid duplicates)
        for block in items:
            block_id_key = block.get('block_id')
            if block_id_key and block_id_key not in all_blocks:
                all_blocks[block_id_key] = block
        
        # Check if there are more pages
        has_more = page_data.get('has_more', False)
        page_token = page_data.get('page_token')
        
        if not has_more or not page_token:
            break
    
    # Return as list
    return list(all_blocks.values())


def _extract_text_from_elements(elements: list) -> str:
    """
    Extract text content from a list of text elements.
    """
    text_parts = []
    for elem in elements:
        text_run = elem.get('text_run', {})
        content = text_run.get('content', '')
        if content:
            text_parts.append(content)
    return ''.join(text_parts)


def _column_number_to_letters(n: int) -> str:
    """
    Convert column number (1-based) to Excel column letters (1 -> A, 2 -> B, ..., 26 -> Z, 27 -> AA, etc.)
    """
    result = ''
    while n > 0:
        n -= 1
        result = chr(65 + (n % 26)) + result
        n //= 26
    return result


def _extract_text_from_block(block: Dict[str, Any]) -> str:
    """
    Extract text content from a block based on its type.
    """
    block_type = block.get('block_type')
    
    # Page (title) - block_type 1
    if block_type == 1 and 'page' in block:
        elements = block['page'].get('elements', [])
        return _extract_text_from_elements(elements)
    
    # Text - block_type 2
    if block_type == 2 and 'text' in block:
        elements = block['text'].get('elements', [])
        return _extract_text_from_elements(elements)
    
    # Heading1 - block_type 3
    if block_type == 3 and 'heading1' in block:
        elements = block['heading1'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'# {text}' if text else ''
    
    # Heading2 - block_type 4
    if block_type == 4 and 'heading2' in block:
        elements = block['heading2'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'## {text}' if text else ''
    
    # Heading3 - block_type 5
    if block_type == 5 and 'heading3' in block:
        elements = block['heading3'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'### {text}' if text else ''
    
    # Heading4 - block_type 6
    if block_type == 6 and 'heading4' in block:
        elements = block['heading4'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'#### {text}' if text else ''
    
    # Heading5 - block_type 7
    if block_type == 7 and 'heading5' in block:
        elements = block['heading5'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'##### {text}' if text else ''
    
    # Heading6 - block_type 8
    if block_type == 8 and 'heading6' in block:
        elements = block['heading6'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'###### {text}' if text else ''
    
    # Heading7 - block_type 9
    if block_type == 9 and 'heading7' in block:
        elements = block['heading7'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'####### {text}' if text else ''
    
    # Heading8 - block_type 10
    if block_type == 10 and 'heading8' in block:
        elements = block['heading8'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'######## {text}' if text else ''
    
    # Heading9 - block_type 11
    if block_type == 11 and 'heading9' in block:
        elements = block['heading9'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'######### {text}' if text else ''
    
    # Bullet - block_type 12
    if block_type == 12 and 'bullet' in block:
        elements = block['bullet'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'- {text}' if text else ''
    
    # Ordered list - block_type 13
    if block_type == 13 and 'ordered' in block:
        elements = block['ordered'].get('elements', [])
        text = _extract_text_from_elements(elements)
        return f'1. {text}' if text else ''
    
    # Code - block_type 14
    if block_type == 14 and 'code' in block:
        elements = block['code'].get('elements', [])
        code_text = _extract_text_from_elements(elements)
        if code_text:
            language = block['code'].get('style', {}).get('language', '')
            return f'```{language}\n{code_text}\n```'
        return ''
    
    # Image - block_type 27
    if block_type == 27 and 'image' in block:
        token = block['image'].get('token', '')
        if token:
            return f'[IMAGE_TOKEN:{token}]'  # Placeholder, will be replaced with URL
        return ''
    
    # Table - block_type 31
    if block_type == 31 and 'table' in block:
        table_info = block['table']
        row_size = table_info.get('property', {}).get('row_size', 0)
        col_size = table_info.get('property', {}).get('column_size', 0)
        return f'[TABLE: {row_size}x{col_size} cells]'
    
    # Sheet - block_type 30
    if block_type == 30 and 'sheet' in block:
        token = block['sheet'].get('token', '')
        if token:
            return f'[SHEET_TOKEN:{token}]'  # Placeholder, will be replaced with sheet content
        return '[SHEET]'
    
    # Board - block_type 43
    if block_type == 43 and 'board' in block:
        return '[BOARD]'
    
    return ''


async def _download_and_compress_image(
    client: httpx.AsyncClient,
    image_url: str,
    static_dir: Path,
) -> Optional[str]:
    """
    Download an image from URL and save to disk without compression.
    
    Args:
        client: HTTP client for downloading
        image_url: URL to download image from
        static_dir: Directory to save images to
    
    Returns:
        Filename (relative to static_dir) or None if download fails
    """
    try:
        # Download image
        response = await client.get(image_url, timeout=30.0)
        if not response.is_success:
            print(f'[_download_and_compress_image] Failed to download {image_url}: {response.status_code}', file=os.sys.stderr)
            return None
        
        image_data = response.content
        if not image_data:
            print(f'[_download_and_compress_image] Empty response from {image_url}', file=os.sys.stderr)
            return None
        
        # Detect MIME type from content or image data
        content_type = response.headers.get('content-type', '')
        if 'image/jpeg' in content_type or 'image/jpg' in content_type:
            mime_type = 'image/jpeg'
        elif 'image/png' in content_type:
            mime_type = 'image/png'
        elif 'image/webp' in content_type:
            mime_type = 'image/webp'
        elif 'image/gif' in content_type:
            mime_type = 'image/gif'
        else:
            # Try to detect from image data
            if image_data.startswith(b'\xff\xd8\xff'):
                mime_type = 'image/jpeg'
            elif image_data.startswith(b'\x89PNG'):
                mime_type = 'image/png'
            elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                mime_type = 'image/webp'
            elif image_data.startswith(b'GIF'):
                mime_type = 'image/gif'
            else:
                print(f'[_download_and_compress_image] Unknown image format for {image_url}, defaulting to jpg', file=os.sys.stderr)
                mime_type = 'image/jpeg'
        
        # Generate random filename
        file_extension = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
        }.get(mime_type, '.jpg')
        
        filename = f'{uuid.uuid4().hex}{file_extension}'
        filepath = static_dir / filename
        
        # Ensure static directory exists
        static_dir.mkdir(parents=True, exist_ok=True)
        
        # Save original image to disk without compression
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        print(f'[_download_and_compress_image] Saved image to {filepath} ({len(image_data)} bytes)', file=os.sys.stderr)
        return filename
        
    except Exception as e:
        print(f'[_download_and_compress_image] Error downloading/processing {image_url}: {e}', file=os.sys.stderr)
        return None


async def _fetch_board_nodes(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    board_token: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch board nodes data using the board API endpoint.
    
    Args:
        client: HTTP client for fetching
        api_domain: API domain (e.g., https://open.larksuite.com)
        bearer_token: Bearer token for authentication
        board_token: Board token/ID
    
    Returns:
        Board nodes data dict or None if fetch fails
    """
    try:
        # Build API URL: GET /open-apis/board/v1/whiteboards/{token}/nodes
        api_url = f'{api_domain}/open-apis/board/v1/whiteboards/{board_token}/nodes'
        
        print(f'[_fetch_board_nodes] Fetching board nodes {board_token} from {api_url}...', file=os.sys.stderr)
        
        # Fetch board nodes
        response = await client.get(
            api_url,
            headers={
                'Authorization': f'Bearer {bearer_token}',
            },
            timeout=30.0,
        )
        
        if not response.is_success:
            print(f'[_fetch_board_nodes] Failed to fetch board {board_token}: {response.status_code} {response.text}', file=os.sys.stderr)
            return None
        
        data = response.json()
        if data.get('code') != 0:
            error_msg = data.get('msg', 'Unknown error')
            print(f'[_fetch_board_nodes] API error for board {board_token}: {error_msg}', file=os.sys.stderr)
            return None
        
        nodes_data = data.get('data', {})
        print(f'[_fetch_board_nodes] Successfully fetched {len(nodes_data.get("nodes", []))} nodes for board {board_token}', file=os.sys.stderr)
        return nodes_data
        
    except Exception as e:
        print(f'[_fetch_board_nodes] Error fetching board {board_token}: {e}', file=os.sys.stderr)
        return None


async def _download_board_image(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    board_token: str,
    static_dir: Path,
) -> Optional[str]:
    """
    Download a board as an image using the board API endpoint.
    
    Args:
        client: HTTP client for downloading
        api_domain: API domain (e.g., https://open.larksuite.com)
        bearer_token: Bearer token for authentication
        board_token: Board token/ID
        static_dir: Directory to save images to
    
    Returns:
        Filename (relative to static_dir) or None if download fails
    """
    try:
        # Build API URL: GET /open-apis/board/v1/whiteboards/{token}/download_as_image
        api_url = f'{api_domain}/open-apis/board/v1/whiteboards/{board_token}/download_as_image'
        
        print(f'[_download_board_image] Downloading board image {board_token} from {api_url}...', file=os.sys.stderr)
        
        # Download board image
        response = await client.get(
            api_url,
            headers={
                'Authorization': f'Bearer {bearer_token}',
            },
            timeout=60.0,  # Boards might take longer to render
        )
        
        if not response.is_success:
            print(f'[_download_board_image] Failed to download board {board_token}: {response.status_code} {response.text}', file=os.sys.stderr)
            return None
        
        image_data = response.content
        if not image_data:
            print(f'[_download_board_image] Empty response for board {board_token}', file=os.sys.stderr)
            return None
        
        # Detect MIME type from content or image data
        content_type = response.headers.get('content-type', '')
        if 'image/jpeg' in content_type or 'image/jpg' in content_type:
            mime_type = 'image/jpeg'
        elif 'image/png' in content_type:
            mime_type = 'image/png'
        elif 'image/webp' in content_type:
            mime_type = 'image/webp'
        elif 'image/gif' in content_type:
            mime_type = 'image/gif'
        else:
            # Try to detect from image data
            if image_data.startswith(b'\xff\xd8\xff'):
                mime_type = 'image/jpeg'
            elif image_data.startswith(b'\x89PNG'):
                mime_type = 'image/png'
            elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                mime_type = 'image/webp'
            elif image_data.startswith(b'GIF'):
                mime_type = 'image/gif'
            else:
                print(f'[_download_board_image] Unknown image format for board {board_token}, defaulting to png', file=os.sys.stderr)
                mime_type = 'image/png'
        
        # Generate filename using UUID (like regular images)
        file_extension = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
        }.get(mime_type, '.png')
        
        # Use UUID-based filename (same as regular images)
        filename = f'{uuid.uuid4().hex}{file_extension}'
        filepath = static_dir / filename
        
        # Ensure static directory exists
        static_dir.mkdir(parents=True, exist_ok=True)
        
        # Save board image to disk
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        print(f'[_download_board_image] Saved board image to {filepath} ({len(image_data)} bytes)', file=os.sys.stderr)
        return filename
        
    except Exception as e:
        print(f'[_download_board_image] Error downloading board {board_token}: {e}', file=os.sys.stderr)
        return None


def _parse_board_nodes(nodes_data: Dict[str, Any]) -> str:
    """
    Parse board nodes data into a readable text format.
    
    Based on the board data structure, nodes can be:
    - life_line: Represents actors/participants in sequence diagrams
    - activation: Represents activation boxes on lifelines
    - connector: Represents arrows/messages between lifelines
    - composite_shape: Other shapes like actors
    
    Args:
        nodes_data: Board nodes data from API
    
    Returns:
        Formatted text description of the board
    """
    try:
        nodes = nodes_data.get('nodes', [])
        if not nodes:
            return '[BOARD: Empty]'
        
        # Create a map of all nodes by ID for quick lookup
        all_nodes_map = {}
        for node in nodes:
            node_id = node.get('id', '')
            if node_id:
                all_nodes_map[node_id] = node
        
        # Organize nodes by type
        life_lines = {}  # id -> node
        connectors = []  # list of connector nodes
        
        for node in nodes:
            node_type = node.get('type', '')
            node_id = node.get('id', '')
            
            if node_type == 'life_line':
                life_lines[node_id] = node
            elif node_type == 'connector':
                connectors.append(node)
        
        # Build description
        parts = []
        
        # Extract life line labels
        life_line_labels = {}
        life_line_positions = {}  # id -> x position
        for node_id, node in life_lines.items():
            text_obj = node.get('text', {})
            label = text_obj.get('text', '') if isinstance(text_obj, dict) else ''
            if label:
                life_line_labels[node_id] = label
                life_line_positions[node_id] = node.get('x', 0)
        
        # Sort connectors by y position (top to bottom)
        connectors_sorted = sorted(connectors, key=lambda c: c.get('y', 0))
        
        # Helper function to find parent life line for a node
        def find_parent_life_line(node_id: str) -> Optional[str]:
            """Find which life line a node belongs to"""
            if not node_id:
                return None
            
            # Check if node_id itself is a life line
            if node_id in life_lines:
                return node_id
            
            # Check if node is a child of a life line
            for life_line_id, life_line in life_lines.items():
                children = life_line.get('children', [])
                if node_id in children:
                    return life_line_id
                # Check prefix match (e.g., "s5:1" might belong to "r5:5")
                node_prefix = node_id.split(':')[0] if ':' in node_id else node_id
                for child_id in children:
                    child_prefix = child_id.split(':')[0] if ':' in child_id else child_id
                    if node_prefix == child_prefix:
                        return life_line_id
            
            # Check if node has a parent_id that leads to a life line
            node = all_nodes_map.get(node_id)
            if node:
                parent_id = node.get('parent_id', '')
                if parent_id:
                    return find_parent_life_line(parent_id)
            
            return None
        
        # Build sequence description
        sequence_parts = []
        for connector in connectors_sorted:
            connector_obj = connector.get('connector', {})
            start_obj = connector_obj.get('start', {})
            end_obj = connector_obj.get('end', {})
            
            # Get start object ID
            start_attached = start_obj.get('attached_object', {})
            start_object_id = start_attached.get('id', '') or start_obj.get('start_object', {}).get('id', '')
            
            # Get end position
            end_position = end_obj.get('position', {})
            end_x = end_position.get('x', 0)
            
            # Find start life line
            start_life_line_id = find_parent_life_line(start_object_id)
            start_label = life_line_labels.get(start_life_line_id, 'Unknown') if start_life_line_id else 'Unknown'
            
            # Find end life line by x position (closest life line)
            end_life_line_id = None
            min_distance = float('inf')
            for life_line_id, life_line_x in life_line_positions.items():
                distance = abs(end_x - life_line_x)
                if distance < min_distance:
                    min_distance = distance
                    end_life_line_id = life_line_id
            
            end_label = life_line_labels.get(end_life_line_id, 'Unknown') if end_life_line_id else 'Unknown'
            
            # Get caption text
            captions = connector_obj.get('captions', {})
            caption_data = captions.get('data', [])
            caption_text = ''
            if caption_data and len(caption_data) > 0:
                caption_text = caption_data[0].get('text', '')
            
            # Get arrow direction
            end_arrow = end_obj.get('arrow_style', 'none')
            arrow_symbol = '→' if end_arrow != 'none' else '←'
            
            if caption_text:
                sequence_parts.append(f'- {start_label} {arrow_symbol} {end_label}: {caption_text}')
            else:
                sequence_parts.append(f'- {start_label} {arrow_symbol} {end_label}')
        
        if sequence_parts:
            parts.append('**Sequence Flow:**\n')
            parts.extend(sequence_parts)
            parts.append('')
        
        # List participants
        if life_line_labels:
            parts.append('**Participants:**\n')
            for label in sorted(life_line_labels.values()):
                parts.append(f'- {label}')
            parts.append('')
        
        return '\n'.join(parts) if parts else '[BOARD: Unable to parse]'
        
    except Exception as e:
        print(f'[_parse_board_nodes] Error parsing board nodes: {e}', file=os.sys.stderr)
        import traceback
        print(f'[_parse_board_nodes] Traceback: {traceback.format_exc()}', file=os.sys.stderr)
        return f'[BOARD: Parse error - {str(e)}]'


async def _fetch_image_urls(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    image_tokens: list,
) -> Dict[str, str]:
    """
    Fetch download URLs for images using batch API: GET /open-apis/drive/v1/medias/batch_get_tmp_download_url.
    The API only accepts a single token per request, so we loop through each token individually.
    Returns dict mapping token -> download URL.
    """
    if not image_tokens:
        return {}
    
    # Filter out empty tokens
    valid_tokens = [token for token in image_tokens if token]
    if not valid_tokens:
        return {}
    
    urls = {}
    api_url = f'{api_domain}/open-apis/drive/v1/medias/batch_get_tmp_download_url'
    
    # Loop through each token individually (API only accepts one token at a time)
    for token in valid_tokens:
        try:
            # Build query parameters: file_tokens=single_token
            params = {'file_tokens': token}
            
            response = await client.get(
                api_url,
                params=params,
                headers={
                    'Authorization': f'Bearer {bearer_token}',
                    'Content-Type': 'application/json',
                },
            )
            
            if not response.is_success:
                print(f'[fetch_image_urls] API failed for token {token[:20]}...: {response.status_code} {response.text}', file=os.sys.stderr)
                continue
            
            data = response.json()
            if data.get('code') != 0:
                print(f'[fetch_image_urls] API error for token {token[:20]}...: {data.get("msg") or "Unknown error"}', file=os.sys.stderr)
                continue
            
            # Parse response: data.tmp_download_urls is a list of objects with file_token and tmp_download_url
            tmp_download_urls = data.get('data', {}).get('tmp_download_urls', [])
            for item in tmp_download_urls:
                file_token = item.get('file_token')
                tmp_download_url = item.get('tmp_download_url')
                if file_token and tmp_download_url:
                    urls[file_token] = tmp_download_url
                    
        except Exception as e:
            print(f'[fetch_image_urls] Error fetching URL for token {token[:20]}...: {e}', file=os.sys.stderr)
            continue
    
    # Log summary
    found_count = len(urls)
    total_count = len(valid_tokens)
    if found_count < total_count:
        print(f'[fetch_image_urls] Warning: Only fetched {found_count}/{total_count} image URLs', file=os.sys.stderr)
    else:
        print(f'[fetch_image_urls] Successfully fetched {found_count} image URLs', file=os.sys.stderr)
    
    return urls


async def _fetch_sheet_metadata(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    spreadsheet_token: str,
    sheet_id: str,
) -> Dict[str, Any]:
    """
    Fetch sheet metadata using GET /open-apis/sheets/v3/spreadsheets/:spreadsheet_token/sheets/:sheet_id
    Returns dict with column_count and row_count.
    """
    api_url = f'{api_domain}/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/{sheet_id}'
    
    response = await client.get(
        api_url,
        headers={
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        },
    )
    
    if not response.is_success:
        raise Exception(f'Failed to fetch sheet metadata: {response.status_code} {response.text}')
    
    data = response.json()
    if data.get('code') != 0:
        raise Exception(f'API error: {data.get("msg") or "Unknown error"}')
    
    sheet_info = data.get('data', {}).get('sheet', {})
    grid_properties = sheet_info.get('grid_properties', {})
    
    return {
        'column_count': grid_properties.get('column_count', 0),
        'row_count': grid_properties.get('row_count', 0),
        'sheet_id': sheet_id,
        'title': sheet_info.get('title', ''),
    }


async def _fetch_sheet_values(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    spreadsheet_token: str,
    range_str: str,
) -> list:
    """
    Fetch sheet cell values using Larksuite Sheets API.
    Tries v2 API first (more stable and documented), falls back to v3 if v2 returns 404.
    
    v2: GET /open-apis/sheets/v2/spreadsheets/:spreadsheet_token/values/:range
    v3: GET /open-apis/sheets/v3/spreadsheets/:spreadsheet_token/values/:encoded_range
    
    Returns list of rows, where each row is a list of cell values.
    """
    # Try v2 API format first (more stable and documented)
    # v2: /sheets/v2/spreadsheets/{spreadsheet_token}/values/{range}
    api_url_v2 = f'{api_domain}/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{range_str}'
    
    params = {
        'valueRenderOption': 'ToString',
        'dateTimeRenderOption': 'FormattedString',
    }
    
    response = await client.get(
        api_url_v2,
        params=params,
        headers={
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
        },
    )
    
    # If v2 fails with 404, try v3 API format
    if not response.is_success and response.status_code == 404:
        # v3: /sheets/v3/spreadsheets/{spreadsheet_token}/values/{encoded_range}
        encoded_range = quote(range_str, safe='')
        api_url_v3 = f'{api_domain}/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/values/{encoded_range}'
        
        response = await client.get(
            api_url_v3,
            params=params,
            headers={
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json',
            },
        )
    
    if not response.is_success:
        error_text = response.text
        try:
            error_data = response.json()
            error_msg = error_data.get('msg') or error_data.get('error') or error_text
        except:
            error_msg = error_text
        raise Exception(f'Failed to fetch sheet values: {response.status_code} {error_msg}')
    
    data = response.json()
    
    # Handle both v2 and v3 response formats
    # v2 format: data.valueRange.values or data.values
    # v3 format: data.data.values
    if data.get('code') != 0:
        raise Exception(f'API error: {data.get("msg") or "Unknown error"}')
    
    # Try v2 format first
    if 'valueRange' in data.get('data', {}):
        values = data['data']['valueRange'].get('values', [])
    elif 'values' in data.get('data', {}):
        values = data['data']['values']
    elif 'values' in data:
        values = data['values']
    else:
        values = []
    
    return values


async def _fetch_sheet_content(
    client: httpx.AsyncClient,
    api_domain: str,
    bearer_token: str,
    sheet_token: str,
) -> str:
    """
    Fetch full content from a sheet token.
    Sheet token format: {spreadsheet_token}_{sheet_id}
    Returns formatted markdown table representation of the sheet.
    """
    try:
        # Parse sheet token: format is {spreadsheet_token}_{sheet_id}
        if '_' not in sheet_token:
            print(f'[fetch_sheet_content] Invalid sheet token format: {sheet_token}', file=os.sys.stderr)
            return f'[SHEET_TOKEN:{sheet_token}]'
        
        parts = sheet_token.rsplit('_', 1)
        if len(parts) != 2:
            print(f'[fetch_sheet_content] Invalid sheet token format: {sheet_token}', file=os.sys.stderr)
            return f'[SHEET_TOKEN:{sheet_token}]'
        
        spreadsheet_token, sheet_id = parts
        
        # Fetch sheet metadata to get dimensions
        print(f'[fetch_sheet_content] Fetching metadata for sheet {sheet_id}...', file=os.sys.stderr)
        metadata = await _fetch_sheet_metadata(
            client, api_domain, bearer_token, spreadsheet_token, sheet_id
        )
        
        column_count = metadata.get('column_count', 0)
        row_count = metadata.get('row_count', 0)
        
        if column_count == 0 or row_count == 0:
            print(f'[fetch_sheet_content] Sheet has no data (columns: {column_count}, rows: {row_count})', file=os.sys.stderr)
            return f'[SHEET: {metadata.get("title", sheet_id)} - Empty]'
        
        # Build range string: {sheet_id}!A1:{last_column}{last_row}
        last_column = _column_number_to_letters(column_count)
        range_str = f'{sheet_id}!A1:{last_column}{row_count}'
        
        # Fetch sheet values
        print(f'[fetch_sheet_content] Fetching values for range {range_str}...', file=os.sys.stderr)
        values = await _fetch_sheet_values(
            client, api_domain, bearer_token, spreadsheet_token, range_str
        )
        
        if not values:
            return f'[SHEET: {metadata.get("title", sheet_id)} - No data]'
        
        # Format as markdown table
        table_lines = []
        table_lines.append(f'**Sheet: {metadata.get("title", sheet_id)}**\n')
        
        for row_idx, row in enumerate(values):
            # Pad row to column_count if needed
            padded_row = row + [''] * (column_count - len(row))
            # Truncate to column_count if needed
            padded_row = padded_row[:column_count]
            
            # Escape pipe characters in cell values
            escaped_row = [str(cell).replace('|', '\\|') for cell in padded_row]
            table_lines.append('| ' + ' | '.join(escaped_row) + ' |')
            
            # Add header separator after first row
            if row_idx == 0:
                table_lines.append('|' + '|'.join([' --- '] * column_count) + '|')
        
        return '\n'.join(table_lines)
        
    except Exception as e:
        print(f'[fetch_sheet_content] Error fetching sheet content for token {sheet_token}: {e}', file=os.sys.stderr)
        return f'[SHEET_TOKEN:{sheet_token} - Error: {str(e)}]'


async def lark_docs(
    url: str,
    lang: int = 0,
    oauth_config: Optional[Dict[str, str]] = None,
    LARKS_BEARER_TOKEN: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tool: docs
    Get structured content from a Larks document URL using blocks API.
    Fetches blocks recursively and includes image URLs.
    """
    try:
        # Check authentication first (skip if bearer token is provided as parameter)
        auth_check = await ensure_authenticated(oauth_config, LARKS_BEARER_TOKEN)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': 'Authentication required. Please login first.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
            }

        # Extract document ID from URL
        document_id = utils.extract_document_id(url)
        
        if not document_id:
            return {
                'success': False,
                'error': 'Could not extract document ID from URL',
            }

        # Get bearer token (priority: parameter > OAuth user token > environment variable)
        bearer_token = utils.get_bearer_token(LARKS_BEARER_TOKEN)
        
        # Use direct HTTP request with the user access token
        config = auth.get_oauth_config()
        # Use API domain for API calls, not OAuth domain
        api_domain = config.api_domain
        
        async with httpx.AsyncClient() as client:
            # Fetch all blocks (main query already includes all blocks including children)
            print(f'[lark_docs] Fetching blocks for document {document_id}...', file=os.sys.stderr)
            all_blocks = await _fetch_blocks_recursive(
                client, api_domain, bearer_token, document_id
            )
            print(f'[lark_docs] Fetched {len(all_blocks)} blocks', file=os.sys.stderr)
            
            # Extract image tokens, sheet tokens, and board tokens
            image_tokens = []
            sheet_tokens = []
            board_tokens = []
            for block in all_blocks:
                if block.get('block_type') == 27 and 'image' in block:
                    token = block['image'].get('token')
                    if token:
                        image_tokens.append(token)
                elif block.get('block_type') == 30 and 'sheet' in block:
                    token = block['sheet'].get('token')
                    if token:
                        sheet_tokens.append(token)
                elif block.get('block_type') == 43 and 'board' in block:
                    token = block['board'].get('token')
                    if token:
                        board_tokens.append(token)
            
            # Fetch image URLs
            image_urls = {}
            if image_tokens:
                print(f'[lark_docs] Fetching {len(image_tokens)} image URLs...', file=os.sys.stderr)
                print(f'[lark_docs] Image tokens to fetch: {image_tokens[:3]}...', file=os.sys.stderr)
                image_urls = await _fetch_image_urls(
                    client, api_domain, bearer_token, image_tokens
                )
                print(f'[lark_docs] Fetched {len(image_urls)} image URLs', file=os.sys.stderr)
                if image_urls:
                    print(f'[lark_docs] Sample fetched tokens: {list(image_urls.keys())[:3]}', file=os.sys.stderr)
            
            # Download and save images to disk
            image_filename_map = {}  # token -> filename
            static_dir = Path(__file__).parent / 'static'
            if image_urls:
                print(f'[lark_docs] Downloading {len(image_urls)} images...', file=os.sys.stderr)
                for token, image_url in image_urls.items():
                    if image_url and image_url.startswith('http'):
                        filename = await _download_and_compress_image(client, image_url, static_dir)
                        if filename:
                            image_filename_map[token] = filename
                            print(f'[lark_docs] Processed image {token[:20]}... -> {filename}', file=os.sys.stderr)
                        else:
                            print(f'[lark_docs] Failed to download image {token[:20]}...', file=os.sys.stderr)
                print(f'[lark_docs] Successfully processed {len(image_filename_map)}/{len(image_urls)} images', file=os.sys.stderr)
            
            # Fetch sheet contents
            sheet_contents = {}
            if sheet_tokens:
                print(f'[lark_docs] Fetching {len(sheet_tokens)} sheet contents...', file=os.sys.stderr)
                for sheet_token in sheet_tokens:
                    sheet_content = await _fetch_sheet_content(
                        client, api_domain, bearer_token, sheet_token
                    )
                    sheet_contents[sheet_token] = sheet_content
                print(f'[lark_docs] Fetched {len(sheet_contents)} sheet contents', file=os.sys.stderr)
            
            # Fetch and parse board nodes, and download board images
            board_contents = {}  # token -> parsed content
            board_filename_map = {}  # token -> filename
            board_token_to_index = {}  # token -> index (for numbering)
            if board_tokens:
                print(f'[lark_docs] Fetching {len(board_tokens)} board nodes and images...', file=os.sys.stderr)
                # Create mapping from token to index (for consistent numbering)
                for idx, board_token in enumerate(board_tokens, start=1):
                    board_token_to_index[board_token] = idx
                
                board_counter = 0
                for board_token in board_tokens:
                    board_counter += 1
                    
                    # Fetch nodes for parsing
                    nodes_data = await _fetch_board_nodes(
                        client, api_domain, bearer_token, board_token
                    )
                    parsed_content = None
                    if nodes_data:
                        parsed_content = _parse_board_nodes(nodes_data)
                        board_contents[board_token] = parsed_content
                        print(f'[lark_docs] Parsed board {board_token[:20]}...', file=os.sys.stderr)
                    
                    # Download image
                    filename = await _download_board_image(
                        client, api_domain, bearer_token, board_token, static_dir
                    )
                    if filename:
                        # Use UUID-based filename directly (like regular images)
                        board_filename_map[board_token] = filename
                        print(f'[lark_docs] Processed board image {board_token[:20]}... -> {filename}', file=os.sys.stderr)
                    
                    if not parsed_content and not filename:
                        print(f'[lark_docs] Failed to fetch board {board_token[:20]}...', file=os.sys.stderr)
                
                print(f'[lark_docs] Successfully processed {len(board_contents)}/{len(board_tokens)} board contents and {len(board_filename_map)}/{len(board_tokens)} board images', file=os.sys.stderr)
            
            # Build content from blocks
            content_parts = []
            image_counter = 0
            board_counter = 0
            for block in all_blocks:
                block_type = block.get('block_type')
                
                # Handle images directly from block data (more reliable than parsing text)
                if block_type == 27 and 'image' in block:
                    token = block['image'].get('token')
                    if token:
                        image_counter += 1
                        # Check if we have saved image filename
                        if token in image_filename_map:
                            filename = image_filename_map[token]
                            # Use localhost static URL (port from env or default 48080)
                            static_port = os.getenv('MCP_PORT', '48080')
                            image_url = f'http://localhost:{static_port}/static/{filename}'
                            # Format image reference for better parsing: clear label and URL
                            content_parts.append(f'[Image{image_counter}]({image_url})')
                        else:
                            # Fall back to original URL if available
                            image_url = image_urls.get(token)
                            if image_url and image_url.startswith('http'):
                                content_parts.append(f'[Image{image_counter}]({image_url})')
                            else:
                                # Token not found or URL invalid, keep placeholder
                                if image_urls:
                                    print(f'[lark_docs] Warning: Image token {token} not found in image_urls. Available tokens: {list(image_urls.keys())[:5]}', file=os.sys.stderr)
                                else:
                                    print(f'[lark_docs] Warning: Image token {token} not found - no image URLs were fetched', file=os.sys.stderr)
                                content_parts.append(f'[Image{image_counter}](IMAGE_TOKEN:{token})')
                    continue
                
                # Handle boards directly from block data
                if block_type == 43 and 'board' in block:
                    token = block['board'].get('token')
                    if token:
                        # Get board number from token index (preserves order)
                        board_number = board_token_to_index.get(token, 0)
                        if board_number == 0:
                            # Token not in our list, increment counter
                            board_counter += 1
                            board_number = board_counter
                        
                        # Build board content with both parsed text and image
                        board_parts = []
                        board_parts.append(f'**Board {board_number}:**\n')
                        
                        # Add parsed content if available
                        if token in board_contents:
                            board_parts.append(board_contents[token])
                        
                        # Add image if available
                        if token in board_filename_map:
                            filename = board_filename_map[token]
                            static_port = os.getenv('MCP_PORT', '48080')
                            board_image_url = f'http://localhost:{static_port}/static/{filename}'
                            board_parts.append(f'\n![Board {board_number} Diagram]({board_image_url})')
                        elif token not in board_contents:
                            # Neither content nor image available
                            board_parts.append(f'[BOARD_TOKEN:{token} - Unable to fetch]')
                        
                        content_parts.append('\n'.join(board_parts))
                    else:
                        board_counter += 1
                        content_parts.append(f'**Board {board_counter}:**\n[BOARD - No token]')
                    continue
                
                # Handle sheets directly from block data
                if block_type == 30 and 'sheet' in block:
                    token = block['sheet'].get('token')
                    if token:
                        sheet_content = sheet_contents.get(token, f'[SHEET_TOKEN:{token}]')
                        content_parts.append(sheet_content)
                    else:
                        content_parts.append('[SHEET]')
                    continue
                
                # For all other block types, extract text normally
                text = _extract_text_from_block(block)
                if text:
                    content_parts.append(text)
            
            # Combine content with proper spacing for better readability
            # Use double newline to separate major sections, single newline within sections
            formatted_content = '\n\n'.join(content_parts)
            
            import json
            return {
                'success': True,
                'document_id': document_id,
                'url': url,
                'blocks': all_blocks,
                'content': formatted_content,
                'raw_content': {
                    'blocks': all_blocks,
                    'image_urls': image_urls,
                    'image_filename_map': image_filename_map,
                    'board_contents': board_contents,
                    'board_filename_map': board_filename_map,
                    'board_tokens': board_tokens,
                },
            }
    except httpx.HTTPStatusError as error:
        error_data = error.response.json() if error.response.headers.get('content-type', '').startswith('application/json') else {}
        
        # On any API error, clear tokens and prompt for re-login
        auth_check = await handle_token_expiration(oauth_config)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': f'API error: {error_data.get("msg") or error.response.reason_phrase}. Please login again.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
                'code': error_data.get('code') or error.response.status_code,
            }
        
        return {
            'success': False,
            'error': f'API error: {error_data.get("msg") or error.response.reason_phrase}',
            'code': error_data.get('code') or error.response.status_code,
        }
    except ValueError as error:
        # Handle "No access token" errors (not expired, just missing) - use ensureAuthenticated
        if 'No access token' in str(error):
            auth_check = await ensure_authenticated(oauth_config, LARKS_BEARER_TOKEN)
            if auth_check.get('needsLogin') and auth_check.get('loginResult'):
                login_result = auth_check['loginResult']
                return {
                    'success': False,
                    'needsLogin': True,
                    'error': str(error),
                    'authorization_url': login_result.get('authorization_url'),
                    'state': login_result.get('state'),
                    'message': login_result.get('message'),
                    'next_step': login_result.get('next_step'),
                }
            return {
                'success': False,
                'error': str(error),
            }
        
        # For any other API call errors, clear tokens and prompt for re-login
        auth_check = await handle_token_expiration(oauth_config)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': f'Request failed: {str(error)}. Please login again.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
            }
        
        return {
            'success': False,
            'error': f'Request failed: {str(error)}',
        }
    except Exception as error:
        # For any other API call errors, clear tokens and prompt for re-login
        auth_check = await handle_token_expiration(oauth_config)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': f'Request failed: {str(error)}. Please login again.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
            }
        
        return {
            'success': False,
            'error': f'Request failed: {str(error)}',
        }
    except ValueError as error:
        # Handle "No access token" errors (not expired, just missing) - use ensureAuthenticated
        if 'No access token' in str(error):
            auth_check = await ensure_authenticated(oauth_config, LARKS_BEARER_TOKEN)
            if auth_check.get('needsLogin') and auth_check.get('loginResult'):
                login_result = auth_check['loginResult']
                return {
                    'success': False,
                    'needsLogin': True,
                    'error': str(error),
                    'authorization_url': login_result.get('authorization_url'),
                    'state': login_result.get('state'),
                    'message': login_result.get('message'),
                    'next_step': login_result.get('next_step'),
                }
            return {
                'success': False,
                'error': str(error),
            }
        
        # For any other API call errors, clear tokens and prompt for re-login
        # This handles network errors, parsing errors, and other failures that might be auth-related
        auth_check = await handle_token_expiration(oauth_config)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': f'Request failed: {str(error)}. Please login again.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
            }
        
        return {
            'success': False,
            'error': f'Request failed: {str(error)}',
        }
    except Exception as error:
        # For any other API call errors, clear tokens and prompt for re-login
        # This handles network errors, parsing errors, and other failures that might be auth-related
        auth_check = await handle_token_expiration(oauth_config)
        if auth_check.get('needsLogin') and auth_check.get('loginResult'):
            login_result = auth_check['loginResult']
            return {
                'success': False,
                'needsLogin': True,
                'error': f'Request failed: {str(error)}. Please login again.',
                'authorization_url': login_result.get('authorization_url'),
                'state': login_result.get('state'),
                'message': login_result.get('message'),
                'next_step': login_result.get('next_step'),
            }
        
        return {
            'success': False,
            'error': f'Request failed: {str(error)}',
        }
