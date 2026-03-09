"""
External API Connector for RAG.

Allows connecting external REST APIs as knowledge sources.
Useful for CRM data, ticket systems, product catalogs, etc.
"""

from typing import Optional
import httpx
import json
import structlog

logger = structlog.get_logger()


class APIConnector:
    """Connects external APIs as RAG data sources."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def fetch_data(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        auth_token: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch data from an external API and convert to text chunks.

        Args:
            url: API endpoint URL
            method: HTTP method (GET, POST)
            headers: Custom headers
            params: Query parameters
            body: Request body (for POST)
            auth_token: Bearer token for authentication

        Returns:
            List of dicts with 'text' and 'metadata' ready for RAG
        """
        request_headers = headers or {}
        if auth_token:
            request_headers["Authorization"] = f"Bearer {auth_token}"

        logger.info("Fetching API data", url=url, method=method)

        if method.upper() == "GET":
            response = await self._client.get(url, headers=request_headers, params=params)
        elif method.upper() == "POST":
            response = await self._client.post(url, headers=request_headers, json=body)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        data = response.json()

        # Convert API response to text chunks
        chunks = self._json_to_chunks(data, source_url=url)

        logger.info("API data fetched", url=url, chunks=len(chunks))
        return chunks

    def _json_to_chunks(self, data: any, source_url: str) -> list[dict]:
        """
        Convert JSON API response into text chunks for RAG.
        Handles both lists and single objects.
        """
        chunks = []

        if isinstance(data, list):
            for i, item in enumerate(data):
                text = self._flatten_to_text(item)
                if text.strip():
                    chunks.append({
                        "text": text,
                        "metadata": {
                            "source": source_url,
                            "doc_type": "api",
                            "item_index": i,
                        },
                    })
        elif isinstance(data, dict):
            # Check if there's a common "results" or "data" key
            items = data.get("results") or data.get("data") or data.get("items") or [data]
            if isinstance(items, list):
                return self._json_to_chunks(items, source_url)
            else:
                text = self._flatten_to_text(data)
                if text.strip():
                    chunks.append({
                        "text": text,
                        "metadata": {"source": source_url, "doc_type": "api"},
                    })

        return chunks

    @staticmethod
    def _flatten_to_text(obj: any, prefix: str = "") -> str:
        """Recursively flatten a JSON object into readable text."""
        if isinstance(obj, dict):
            lines = []
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    nested = APIConnector._flatten_to_text(value, prefix=f"{key}.")
                    lines.append(nested)
                else:
                    lines.append(f"{prefix}{key}: {value}")
            return "\n".join(lines)
        elif isinstance(obj, list):
            return "\n".join(APIConnector._flatten_to_text(item) for item in obj)
        else:
            return str(obj)

    async def close(self):
        await self._client.aclose()
