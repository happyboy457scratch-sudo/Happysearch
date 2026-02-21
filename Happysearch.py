
-"""Happysearch: tiny search engine web app."""
+"""Happysearch: Pokemon GO event tracker inspired by LeekDuck."""
 
 from __future__ import annotations
 
 import argparse
 import json
+import re
 import time
 from dataclasses import dataclass
+from datetime import datetime, timezone
+from email.utils import parsedate_to_datetime
 from http import HTTPStatus
 from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from typing import Dict, List
-from urllib.parse import parse_qs, quote, urlencode, urlparse
 from urllib.request import Request, urlopen
+from xml.etree import ElementTree
 
 WEB_DIR = Path(__file__).resolve().parent
 
 
 @dataclass
-class SearchResult:
+class EventPost:
     title: str
-    snippet: str
     url: str
+    summary: str
+    source: str
+    published_at: str
+    category: str
+
+
+class PokemonGoEvents:
+    """Fetches Pokemon GO news feeds and converts them into event-style breakdowns."""
+
+    FEEDS = (
+        ("Pokemon GO Live", "https://pokemongolive.com/news/rss"),
+        ("Pokemon GO Live (EN)", "https://pokemongolive.com/en/news/rss"),
+        ("Pokemon GO Blog", "https://pokemongohub.net/feed/"),
+    )
+
+    EVENT_KEYWORDS = {
+        "Raid": "Raid",
+        "Spotlight": "Spotlight Hour",
+        "Community Day": "Community Day",
+        "Max Monday": "Max Monday",
+        "Research": "Research",
+        "GO Battle": "GO Battle League",
+        "Season": "Season",
+        "Showcase": "Showcase",
+        "Incense": "Incense",
+        "Egg": "Egg",
+    }
+
+    def __init__(self, timeout_seconds: float = 8.0) -> None:
+        self.timeout_seconds = timeout_seconds
 
+    def _clean_html(self, text: str) -> str:
+        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()
 
-class Happysearch:
-    def __init__(self, timeout_seconds: float = 6.0) -> None:
-        self.timeout_seconds = timeout_seconds
+    def _category_for_title(self, title: str) -> str:
+        for keyword, category in self.EVENT_KEYWORDS.items():
+            if keyword.lower() in title.lower():
+                return category
+        return "News"
 
-    def _get_json(self, url: str) -> Dict:
+    def _read_feed(self, source_name: str, url: str) -> List[EventPost]:
         request = Request(
             url,
             headers={
-                "User-Agent": "Happysearch/1.0 (+https://localhost)",
-                "Accept": "application/json",
+                "User-Agent": "Happysearch-PokemonGO/1.0",
+                "Accept": "application/rss+xml, application/xml, text/xml",
             },
         )
-        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - controlled URL
-            return json.loads(response.read().decode("utf-8"))
-
-    def _wikipedia_results(self, query: str, limit: int = 7) -> List[SearchResult]:
-        params = urlencode(
-            {
-                "action": "query",
-                "list": "search",
-                "srsearch": query,
-                "srlimit": str(limit),
-                "utf8": "",
-                "format": "json",
-            }
-        )
-        payload = self._get_json(f"https://en.wikipedia.org/w/api.php?{params}")
-
-        items: List[SearchResult] = []
-        for row in payload.get("query", {}).get("search", []):
-            title = row.get("title", "Untitled")
-            snippet = row.get("snippet", "")
-            snippet = snippet.replace("<span class=\"searchmatch\">", "").replace("</span>", "")
-            url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
-            items.append(SearchResult(title=title, snippet=snippet, url=url))
-        return items
-
-    def search(self, query: str) -> Dict:
-        started = time.perf_counter()
+        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - trusted feed list
+            raw_xml = response.read()
+
+        root = ElementTree.fromstring(raw_xml)
+        posts: List[EventPost] = []
+
+        for item in root.findall(".//item")[:25]:
+            title = (item.findtext("title") or "Untitled Event").strip()
+            link = (item.findtext("link") or "").strip()
+            summary = self._clean_html(item.findtext("description") or "")
+            summary = summary[:230] + "…" if len(summary) > 230 else summary
+            published = (item.findtext("pubDate") or "").strip()
+            published_at = self._normalize_date(published)
+            category = self._category_for_title(title)
+
+            posts.append(
+                EventPost(
+                    title=title,
+                    url=link,
+                    summary=summary or "Open to see full event details.",
+                    source=source_name,
+                    published_at=published_at,
+                    category=category,
+                )
+            )
+        return posts
+
+    def _normalize_date(self, value: str) -> str:
+        if not value:
+            return "Unknown"
         try:
-            results = self._wikipedia_results(query)
+            dt = parsedate_to_datetime(value)
+            if dt.tzinfo is None:
+                dt = dt.replace(tzinfo=timezone.utc)
+            return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
         except Exception:
-            results = [
-                SearchResult(
-                    title=f"Search Wikipedia for: {query}",
-                    snippet="Live search source unavailable here, so use this direct Wikipedia query link.",
-                    url=f"https://en.wikipedia.org/w/index.php?search={quote(query)}",
+            return value
+
+    def fallback_posts(self) -> List[EventPost]:
+        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
+        return [
+            EventPost(
+                title="Daily feed refresh pending",
+                url="https://pokemongolive.com/",
+                summary=(
+                    "Could not reach live Pokemon GO feeds right now. The tracker will retry automatically "
+                    "on every page load so fresh event posts appear as soon as sources are reachable."
                 ),
-                SearchResult(
-                    title=f"Search DuckDuckGo for: {query}",
-                    snippet="Open web results directly in DuckDuckGo.",
-                    url=f"https://duckduckgo.com/?q={quote(query)}",
-                ),
-            ]
+                source="System",
+                published_at=f"{today} 00:00 UTC",
+                category="Status",
+            )
+        ]
+
+    def events(self) -> Dict:
+        started = time.perf_counter()
+        collected: List[EventPost] = []
+        errors: List[str] = []
 
+        for source, feed_url in self.FEEDS:
+            try:
+                collected.extend(self._read_feed(source, feed_url))
+            except Exception as error:  # network failures should not break the page
+                errors.append(f"{source}: {error}")
+
+        if not collected:
+            collected = self.fallback_posts()
+
+        unique: Dict[str, EventPost] = {}
+        for post in collected:
+            key = f"{post.title}|{post.url}"
+            unique[key] = post
+
+        def sort_key(post: EventPost) -> str:
+            return post.published_at
+
+        ordered = sorted(unique.values(), key=sort_key, reverse=True)
         elapsed_ms = int((time.perf_counter() - started) * 1000)
 
         return {
-            "query": query,
-            "engine": "Happysearch",
+            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
+            "refresh_note": "Auto-refreshes every day and can be manually refreshed anytime.",
             "elapsed_ms": elapsed_ms,
-            "results": [result.__dict__ for result in results],
+            "errors": errors,
+            "events": [event.__dict__ for event in ordered],
         }
 
 
 class HappysearchHandler(BaseHTTPRequestHandler):
-    engine = Happysearch()
+    tracker = PokemonGoEvents()
 
     def _send_json(self, payload: Dict, status: int = HTTPStatus.OK) -> None:
         body = json.dumps(payload).encode("utf-8")
         self.send_response(status)
         self.send_header("Content-Type", "application/json; charset=utf-8")
         self.send_header("Content-Length", str(len(body)))
         self.end_headers()
         self.wfile.write(body)
 
     def _serve_file(self, relative_path: str) -> None:
         safe_path = (WEB_DIR / relative_path).resolve()
         if WEB_DIR not in safe_path.parents and safe_path != WEB_DIR:
             self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
             return
         if not safe_path.exists() or safe_path.is_dir():
             self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
             return
 
         content_type = "text/plain; charset=utf-8"
         if safe_path.suffix == ".html":
             content_type = "text/html; charset=utf-8"
         elif safe_path.suffix == ".css":
             content_type = "text/css; charset=utf-8"
         elif safe_path.suffix == ".js":
             content_type = "application/javascript; charset=utf-8"
 
         body = safe_path.read_bytes()
         self.send_response(HTTPStatus.OK)
         self.send_header("Content-Type", content_type)
         self.send_header("Content-Length", str(len(body)))
         self.end_headers()
         self.wfile.write(body)
 
     def do_GET(self) -> None:
-        parsed = urlparse(self.path)
-
-        if parsed.path in {"/", "/index.html"}:
+        if self.path in {"/", "/index.html"}:
             self._serve_file("index.html")
             return
 
-        if parsed.path == "/api/search":
-            raw_query = parse_qs(parsed.query).get("q", [""])[0]
-            query = raw_query.strip()
-            if not query:
-                self._send_json({"error": "Query parameter 'q' is required."}, HTTPStatus.BAD_REQUEST)
-                return
-
-            payload = self.engine.search(query)
-            self._send_json(payload)
+        if self.path.startswith("/api/events"):
+            self._send_json(self.tracker.events())
             return
 
         self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
 
 
 def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
     parser = argparse.ArgumentParser(description="Run the Happysearch web server.")
     parser.add_argument("--host", default="127.0.0.1", help="Web server host")
     parser.add_argument("--port", type=int, default=8000, help="Web server port")
     return parser.parse_args(argv)
 
 
 def main() -> None:
     args = parse_args()
     server = ThreadingHTTPServer((args.host, args.port), HappysearchHandler)
     print(f"Happysearch running at http://{args.host}:{args.port}")
     server.serve_forever()
 
 
 if __name__ == "__main__":
     main()
