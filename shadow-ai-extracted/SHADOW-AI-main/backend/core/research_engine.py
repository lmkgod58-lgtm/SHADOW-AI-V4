import html
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup


class ResearchEngine:
    """Lightweight, general-purpose multi-source research engine.

    It deliberately avoids a local LLM. Research is gathered in parallel and
    returned as evidence for GPT/Claude to synthesize.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 ShadowAI/3.0 (+research)",
            "Accept-Language": "en-US,en;q=0.8",
        })

    def terminal_status(self) -> Dict[str, bool]:
        tools = {}
        for cmd in ["curl", "wget", "dig", "host", "whois", "python3"]:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, timeout=2)
                tools[cmd] = True
            except Exception:
                tools[cmd] = False
        return tools

    def research(self, query: str, max_sources: int = 8) -> Tuple[str, List[Dict[str, str]]]:
        jobs = {
            "DuckDuckGo": lambda: self._duckduckgo(query),
            "Wikipedia": lambda: self._wikipedia(query),
            "GitHub": lambda: self._github(query),
        }
        # Add specialized sources when the question clearly benefits from them.
        q = query.lower()
        if any(x in q for x in ["security", "vulnerability", "xss", "owasp", "cve", "cyber"]):
            jobs["OWASP"] = lambda: self._page("https://owasp.org/www-project-top-ten/")
            jobs["PortSwigger"] = lambda: self._page("https://portswigger.net/web-security")
        if any(x in q for x in ["python", "programming", "api", "javascript", "code"]):
            jobs["Python Docs"] = lambda: self._python_docs(query)

        results: List[Dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
            futures = {pool.submit(fn): name for name, fn in jobs.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    items = future.result() or []
                    for item in items:
                        if item.get("text"):
                            item["source"] = item.get("source") or name
                            results.append(item)
                except Exception as exc:
                    print(f"[Research/{name}] {type(exc).__name__}: {exc}")

        # Keep evidence compact for model context.
        seen = set()
        unique = []
        for item in results:
            key = (item.get("url", "") + item.get("text", ""))[:180]
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= max_sources:
                break

        evidence = []
        for i, item in enumerate(unique, 1):
            evidence.append(
                f"[{i}] {item.get('title', item.get('source', 'Source'))}\n"
                f"URL: {item.get('url', '')}\n"
                f"{item.get('text', '')[:1800]}"
            )
        return "\n\n".join(evidence), unique

    def domain_tools(self, query: str) -> List[Dict[str, str]]:
        domain = self._extract_domain(query)
        if not domain:
            return []
        output = []
        for label, cmd in [("DNS", ["dig", "+short", domain]), ("WHOIS", ["whois", domain])]:
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                text = (p.stdout or p.stderr).strip()
                if label == "WHOIS":
                    lines = [x for x in text.splitlines() if any(k in x.lower() for k in ["registrar", "name server", "creation", "expiration", "country"])]
                    text = "\n".join(lines[:20])
                if text:
                    output.append({"source": label, "title": f"{label} for {domain}", "url": domain, "text": text[:2500]})
            except Exception:
                pass
        return output

    def _duckduckgo(self, query: str) -> List[Dict[str, str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        r = self.session.get(url, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for result in soup.select(".result")[:5]:
            a = result.select_one(".result__a")
            snippet = result.select_one(".result__snippet")
            if a:
                href = a.get("href", "")
                out.append({
                    "source": "DuckDuckGo",
                    "title": html.unescape(a.get_text(" ", strip=True)),
                    "url": href,
                    "text": html.unescape(snippet.get_text(" ", strip=True) if snippet else "")
                })
        return out

    def _wikipedia(self, query: str) -> List[Dict[str, str]]:
        r = self.session.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 3
        }, timeout=10)
        r.raise_for_status()
        out = []
        for item in r.json().get("query", {}).get("search", []):
            out.append({
                "source": "Wikipedia",
                "title": item.get("title", "Wikipedia"),
                "url": "https://en.wikipedia.org/wiki/" + item.get("title", "").replace(" ", "_"),
                "text": BeautifulSoup(item.get("snippet", ""), "html.parser").get_text(" ", strip=True)
            })
        return out

    def _github(self, query: str) -> List[Dict[str, str]]:
        r = self.session.get("https://api.github.com/search/repositories", params={"q": query, "per_page": 3}, timeout=10)
        if r.status_code >= 400:
            return []
        out = []
        for item in r.json().get("items", []):
            out.append({
                "source": "GitHub",
                "title": item.get("full_name", "GitHub repository"),
                "url": item.get("html_url", ""),
                "text": item.get("description") or "No repository description provided."
            })
        return out

    def _python_docs(self, query: str) -> List[Dict[str, str]]:
        return self._duckduckgo(f"site:docs.python.org {query}")[:3]

    def _page(self, url: str) -> List[Dict[str, str]]:
        text = self._fetch_text(url)
        if not text:
            return []
        return [{"source": urlparse(url).netloc, "title": urlparse(url).netloc, "url": url, "text": text[:2200]}]

    def _fetch_text(self, url: str) -> str:
        try:
            r = self.session.get(url, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        except Exception:
            return ""

    @staticmethod
    def _extract_domain(text: str):
        match = re.search(r"(?:https?://)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9.-]+)", text)
        return match.group(1).strip(".,;:!?/") if match else None
