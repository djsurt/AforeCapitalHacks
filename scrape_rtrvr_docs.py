"""
rtrvr.ai Documentation Scraper
Fetches all doc pages and outputs a single text file ready to feed to an AI model.

Usage:
    pip install requests beautifulsoup4
    python scrape_rtrvr_docs.py

Output:
    rtrvr_docs.txt  - All docs concatenated, ready to paste into an AI prompt
    rtrvr_docs.json - Structured version with page titles, URLs, and content
"""

import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://www.rtrvr.ai"

# All doc pages from the sidebar navigation
DOC_PAGES = [
    "/docs",
    "/docs/quick-start",
    "/docs/web-agent",
    "/docs/sheets-workflows",
    "/docs/recordings",
    "/docs/tool-calling",
    "/docs/knowledge-base",
    "/docs/cli",
    "/docs/api",
    "/docs/agent",
    "/docs/scrape",
    "/docs/mcp",
    "/docs/shortcuts",
    "/docs/triggers-webhooks",
    "/docs/schedules",
    "/docs/cookie-sync",
    "/docs/permissions-privacy",
    "/docs/integrations",
    "/docs/webhooks",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DocScraper/1.0)"
}


def fetch_page(path):
    url = BASE_URL + path
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  ⚠️  Failed to fetch {url}: {e}")
        return None


def extract_content(html, path):
    soup = BeautifulSoup(html, "html.parser")

    # Get page title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else path

    # Remove nav, header, footer, sidebar clutter
    for tag in soup.select("nav, header, footer, aside, script, style, [aria-hidden='true']"):
        tag.decompose()

    # Try to find the main content area
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(class_=lambda c: c and "content" in c.lower())
        or soup.body
    )

    if not main:
        return title, ""

    # Extract clean text
    lines = []
    for element in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "pre", "code", "td", "th"]):
        text = element.get_text(separator=" ", strip=True)
        if not text:
            continue

        tag = element.name
        if tag == "h1":
            lines.append(f"\n# {text}")
        elif tag == "h2":
            lines.append(f"\n## {text}")
        elif tag == "h3":
            lines.append(f"\n### {text}")
        elif tag == "h4":
            lines.append(f"\n#### {text}")
        elif tag == "pre":
            lines.append(f"\n```\n{text}\n```")
        elif tag in ("td", "th"):
            lines.append(f"| {text} |")
        else:
            lines.append(text)

    content = "\n".join(lines)
    return title, content


def main():
    print("🔍 Scraping rtrvr.ai documentation...\n")
    pages = []

    for path in DOC_PAGES:
        url = BASE_URL + path
        print(f"  Fetching {url}")
        html = fetch_page(path)
        if not html:
            continue

        title, content = extract_content(html, path)
        pages.append({
            "title": title,
            "url": url,
            "path": path,
            "content": content,
        })
        time.sleep(0.5)  # polite crawl delay

    if not pages:
        print("\n❌ No pages were fetched. Check your internet connection.")
        return

    # --- Output 1: Single flat text file for pasting into AI prompts ---
    txt_path = "rtrvr_docs.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("# rtrvr.ai Documentation\n")
        f.write(f"# Scraped {len(pages)} pages from {BASE_URL}/docs\n\n")
        f.write("=" * 80 + "\n\n")
        for page in pages:
            f.write(f"SOURCE: {page['url']}\n")
            f.write(f"TITLE: {page['title']}\n")
            f.write("-" * 40 + "\n")
            f.write(page["content"].strip())
            f.write("\n\n" + "=" * 80 + "\n\n")

    # --- Output 2: Structured JSON for programmatic use ---
    json_path = "rtrvr_docs.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Scraped {len(pages)} pages.\n")
    print(f"  📄 {txt_path}  — paste directly into any AI chat (Claude, ChatGPT, etc.)")
    print(f"  🗂️  {json_path} — structured data for programmatic use\n")

    # Show token estimate
    total_chars = sum(len(p["content"]) for p in pages)
    approx_tokens = total_chars // 4
    print(f"  📊 Total content: ~{approx_tokens:,} tokens (approx)")
    print("     Claude context window: 200k tokens — this fits comfortably.\n")

    # Usage tip
    print("💡 To use with Claude (or any AI):")
    print("   1. Open rtrvr_docs.txt")
    print("   2. Paste it into your system prompt or first user message")
    print("   3. Then ask your questions or describe what you want to build\n")


if __name__ == "__main__":
    main()