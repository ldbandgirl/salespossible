"""
HTTP request tool — generic async HTTP for API integrations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

HTTP_REQUEST_SCHEMA: dict[str, Any] = {
    "name": "http_request",
    "description": (
        "Make an HTTP request to any URL. Useful for calling REST APIs, "
        "fetching data from web pages, or posting to webhooks."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "description": "HTTP method",
            },
            "url": {
                "type": "string",
                "description": "The full URL to request",
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers as key-value pairs",
            },
            "body": {
                "type": "object",
                "description": "JSON body for POST/PUT/PATCH requests",
            },
            "params": {
                "type": "object",
                "description": "Query string parameters",
            },
        },
        "required": ["method", "url"],
    },
}


async def http_request(inputs: dict[str, Any]) -> str:
    """Execute an HTTP request and return the response."""
    import httpx

    method = inputs["method"].upper()
    url = inputs["url"]
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    params = inputs.get("params")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=params,
            )

        # Attempt JSON, fall back to text
        try:
            data = response.json()
            content = json.dumps(data, indent=2)[:4000]
        except Exception:
            content = response.text[:4000]

        return (
            f"HTTP {method} {url}\n"
            f"Status: {response.status_code}\n"
            f"Response:\n{content}"
        )

    except Exception as e:
        logger.error("HTTP request error: %s", e)
        return f"HTTP request failed: {e}"
