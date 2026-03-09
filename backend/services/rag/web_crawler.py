"""
Web Crawler for RAG.

Crawls websites and extracts text content for indexing.
"""

from typing import Optional
import httpx
from bs4 import BeautifulSoup
import structlog
from urllib.parse import urljoin, urlparse

logger = structlog.get_logger()


class WebCrawler:
    """Simple web crawler for extracting content from URLs."""

    def __init__(self, max_pages: int = 50, max_depth: int = 3):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "LiveAvatarBot/1.0 (RAG Indexer)",
            },
        )

    async def crawl_url(self, url: str) -> dict:
        """
        Crawl a single URL and extract its text content.

        Returns:
            dict with 'text', 'title', 'url', 'links' keys
        """
        logger.info("Crawling URL", url=url)

        response = await self._client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Extract title
        title = soup.title.string if soup.title else urlparse(url).netloc

        # Extract main content
        main_content = soup.find("main") or soup.find("article") or soup.find("body")
        text = main_content.get_text(separator="\n", strip=True) if main_content else ""

        # Extract internal links for further crawling
        links = []
        base_domain = urlparse(url).netloc
        for a_tag in soup.find_all("a", href=True):
            href = urljoin(url, a_tag["href"])
            if urlparse(href).netloc == base_domain:
                links.append(href)

        return {
            "text": text,
            "title": title,
            "url": url,
            "links": list(set(links)),
        }

    async def crawl_site(
        self,
        start_url: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> list[dict]:
        """
        Crawl a website starting from a URL, following internal links.

        Args:
            start_url: Starting URL
            max_pages: Maximum pages to crawl
            max_depth: Maximum link depth

        Returns:
            List of page dicts with 'text', 'title', 'url'
        """
        max_pages = max_pages or self.max_pages
        max_depth = max_depth or self.max_depth

        visited = set()
        results = []
        queue = [(start_url, 0)]

        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)

            if url in visited or depth > max_depth:
                continue

            visited.add(url)

            try:
                page = await self.crawl_url(url)
                if page["text"].strip():
                    results.append(page)

                # Add discovered links to queue
                for link in page["links"]:
                    if link not in visited:
                        queue.append((link, depth + 1))

            except Exception as e:
                logger.warning("Failed to crawl URL", url=url, error=str(e))
                continue

        logger.info("Site crawl complete",
                     start_url=start_url, pages_crawled=len(results))
        return results

    async def close(self):
        await self._client.aclose()
