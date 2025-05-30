"""
HTTP client for making API calls.
Provides asynchronous HTTP requests with error handling and response processing.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def send_http_request(
    url: str,
    method: str = "POST",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Send an HTTP request with JSON payload.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, PUT, DELETE)
        payload: JSON payload to send
        headers: HTTP headers
        timeout: Request timeout in seconds

    Returns:
        Dict containing response information and status
    """
    if not url:
        return {"status": "error", "error": "No URL specified"}

    # Default headers if not provided
    if headers is None:
        headers = {}
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    # Normalize method to uppercase
    method = method.upper()

    try:
        logger.info(f"Sending {method} request to {url}")
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Different handling based on HTTP method
            if method == "GET":
                response = await client.get(url, headers=headers, params=payload)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=payload)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=payload)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers, json=payload)
            else:
                return {
                    "status": "error",
                    "error": f"Unsupported HTTP method: {method}",
                }

            # Try to parse the response as JSON
            response_content = response.text
            try:
                response_json = response.json()
            except (json.JSONDecodeError, ValueError):
                response_json = None

            # Check if the request was successful (status code 2xx)
            if response.is_success:
                logger.info(
                    f"HTTP request to {url} succeeded with status {response.status_code}"
                )
                return {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": (
                        response_json if response_json is not None else response_content
                    ),
                }
            else:
                logger.warning(
                    f"HTTP request failed with status {response.status_code}: {response_content}"
                )
                return {
                    "status": "error",
                    "error": f"HTTP request failed with status {response.status_code}",
                    "status_code": response.status_code,
                    "response_content": response_content,
                    "response": response_json,
                }

    except httpx.TimeoutException as e:
        logger.error(f"HTTP request to {url} timed out after {timeout}s: {str(e)}")
        return {
            "status": "error",
            "error": f"Request timed out after {timeout}s",
            "exception": str(e),
        }
    except httpx.HTTPError as e:
        logger.error(f"HTTP error for {url}: {str(e)}")
        return {
            "status": "error",
            "error": f"HTTP error: {str(e)}",
            "exception": str(e),
        }
    except Exception as e:
        logger.exception(f"Exception during HTTP request to {url}: {str(e)}")
        return {
            "status": "error",
            "error": f"Exception during request: {str(e)}",
            "exception": str(e),
        }
