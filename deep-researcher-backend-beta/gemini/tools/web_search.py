"""
Web Search Tools using Crawl4AI
Provides functions to scrape URLs and save them with metadata tracking.
"""

import asyncio
import hashlib
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse
from typing import List, Dict, Optional, Union
from ddgs import DDGS
import json


try:
    from extract_favicon import from_url

    EXTRACT_FAVICON_AVAILABLE = True
except ImportError:
    EXTRACT_FAVICON_AVAILABLE = False

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

COUNTRY_CODES = {
    "Afghanistan": "af",
    "Albania": "al",
    "Algeria": "dz",
    "American Samoa": "as",
    "Andorra": "ad",
    "Angola": "ao",
    "Anguilla": "ai",
    "Antarctica": "aq",
    "Antigua and Barbuda": "ag",
    "Argentina": "ar",
    "Armenia": "am",
    "Aruba": "aw",
    "Australia": "au",
    "Austria": "at",
    "Azerbaijan": "az",
    "Bahamas": "bs",
    "Bahrain": "bh",
    "Bangladesh": "bd",
    "Barbados": "bb",
    "Belarus": "by",
    "Belgium": "be",
    "Belize": "bz",
    "Benin": "bj",
    "Bermuda": "bm",
    "Bhutan": "bt",
    "Bolivia": "bo",
    "Bosnia and Herzegovina": "ba",
    "Botswana": "bw",
    "Bouvet Island": "bv",
    "Brazil": "br",
    "British Indian Ocean Territory": "io",
    "Brunei Darussalam": "bn",
    "Bulgaria": "bg",
    "Burkina Faso": "bf",
    "Burundi": "bi",
    "Cambodia": "kh",
    "Cameroon": "cm",
    "Canada": "ca",
    "Cape Verde": "cv",
    "Cayman Islands": "ky",
    "Central African Republic": "cf",
    "Chad": "td",
    "Chile": "cl",
    "China": "cn",
    "Christmas Island": "cx",
    "Cocos (Keeling) Islands": "cc",
    "Colombia": "co",
    "Comoros": "km",
    "Congo": "cg",
    "Congo, the Democratic Republic of the": "cd",
    "Cook Islands": "ck",
    "Costa Rica": "cr",
    "Cote D'ivoire": "ci",
    "Croatia": "hr",
    "Cuba": "cu",
    "Cyprus": "cy",
    "Czech Republic": "cz",
    "Denmark": "dk",
    "Djibouti": "dj",
    "Dominica": "dm",
    "Dominican Republic": "do",
    "Ecuador": "ec",
    "Egypt": "eg",
    "El Salvador": "sv",
    "Equatorial Guinea": "gq",
    "Eritrea": "er",
    "Estonia": "ee",
    "Ethiopia": "et",
    "Falkland Islands (Malvinas)": "fk",
    "Faroe Islands": "fo",
    "Fiji": "fj",
    "Finland": "fi",
    "France": "fr",
    "French Guiana": "gf",
    "French Polynesia": "pf",
    "French Southern Territories": "tf",
    "Gabon": "ga",
    "Gambia": "gm",
    "Georgia": "ge",
    "Germany": "de",
    "Ghana": "gh",
    "Gibraltar": "gi",
    "Greece": "gr",
    "Greenland": "gl",
    "Grenada": "gd",
    "Guadeloupe": "gp",
    "Guam": "gu",
    "Guatemala": "gt",
    "Guinea": "gn",
    "Guinea-Bissau": "gw",
    "Guyana": "gy",
    "Haiti": "ht",
    "Heard Island and Mcdonald Islands": "hm",
    "Holy See (Vatican City State)": "va",
    "Honduras": "hn",
    "Hong Kong": "hk",
    "Hungary": "hu",
    "Iceland": "is",
    "India": "in",
    "Indonesia": "id",
    "Iran, Islamic Republic of": "ir",
    "Iraq": "iq",
    "Ireland": "ie",
    "Israel": "il",
    "Italy": "it",
    "Jamaica": "jm",
    "Japan": "jp",
    "Jordan": "jo",
    "Kazakhstan": "kz",
    "Kenya": "ke",
    "Kiribati": "ki",
    "Korea, Democratic People's Republic of": "kp",
    "Korea, Republic of": "kr",
    "Kuwait": "kw",
    "Kyrgyzstan": "kg",
    "Lao People's Democratic Republic": "la",
    "Latvia": "lv",
    "Lebanon": "lb",
    "Lesotho": "ls",
    "Liberia": "lr",
    "Libyan Arab Jamahiriya": "ly",
    "Liechtenstein": "li",
    "Lithuania": "lt",
    "Luxembourg": "lu",
    "Macao": "mo",
    "Macedonia, the Former Yugosalv Republic of": "mk",
    "Madagascar": "mg",
    "Malawi": "mw",
    "Malaysia": "my",
    "Maldives": "mv",
    "Mali": "ml",
    "Malta": "mt",
    "Marshall Islands": "mh",
    "Martinique": "mq",
    "Mauritania": "mr",
    "Mauritius": "mu",
    "Mayotte": "yt",
    "Mexico": "mx",
    "Micronesia, Federated States of": "fm",
    "Moldova, Republic of": "md",
    "Monaco": "mc",
    "Mongolia": "mn",
    "Montserrat": "ms",
    "Morocco": "ma",
    "Mozambique": "mz",
    "Myanmar": "mm",
    "Namibia": "na",
    "Nauru": "nr",
    "Nepal": "np",
    "Netherlands": "nl",
    "Netherlands Antilles": "an",
    "New Caledonia": "nc",
    "New Zealand": "nz",
    "Nicaragua": "ni",
    "Niger": "ne",
    "Nigeria": "ng",
    "Niue": "nu",
    "Norfolk Island": "nf",
    "Northern Mariana Islands": "mp",
    "Norway": "no",
    "Oman": "om",
    "Pakistan": "pk",
    "Palau": "pw",
    "Palestinian Territory, Occupied": "ps",
    "Panama": "pa",
    "Papua New Guinea": "pg",
    "Paraguay": "py",
    "Peru": "pe",
    "Philippines": "ph",
    "Pitcairn": "pn",
    "Poland": "pl",
    "Portugal": "pt",
    "Puerto Rico": "pr",
    "Qatar": "qa",
    "Reunion": "re",
    "Romania": "ro",
    "Russian Federation": "ru",
    "Rwanda": "rw",
    "Saint Helena": "sh",
    "Saint Kitts and Nevis": "kn",
    "Saint Lucia": "lc",
    "Saint Pierre and Miquelon": "pm",
    "Saint Vincent and the Grenadines": "vc",
    "Samoa": "ws",
    "San Marino": "sm",
    "Sao Tome and Principe": "st",
    "Saudi Arabia": "sa",
    "Senegal": "sn",
    "Serbia and Montenegro": "cs",
    "Seychelles": "sc",
    "Sierra Leone": "sl",
    "Singapore": "sg",
    "Slovakia": "sk",
    "Slovenia": "si",
    "Solomon Islands": "sb",
    "Somalia": "so",
    "South Africa": "za",
    "South Georgia and the South Sandwich Islands": "gs",
    "Spain": "es",
    "Sri Lanka": "lk",
    "Sudan": "sd",
    "Suriname": "sr",
    "Svalbard and Jan Mayen": "sj",
    "Swaziland": "sz",
    "Sweden": "se",
    "Switzerland": "ch",
    "Syrian Arab Republic": "sy",
    "Taiwan, Province of China": "tw",
    "Tajikistan": "tj",
    "Tanzania, United Republic of": "tz",
    "Thailand": "th",
    "Timor-Leste": "tl",
    "Togo": "tg",
    "Tokelau": "tk",
    "Tonga": "to",
    "Trinidad and Tobago": "tt",
    "Tunisia": "tn",
    "Turkey": "tr",
    "Turkmenistan": "tm",
    "Turks and Caicos Islands": "tc",
    "Tuvalu": "tv",
    "Uganda": "ug",
    "Ukraine": "ua",
    "United Arab Emirates": "ae",
    "United Kingdom": "uk",
    "United States": "us",
    "United States Minor Outlying Islands": "um",
    "Uruguay": "uy",
    "Uzbekistan": "uz",
    "Vanuatu": "vu",
    "Venezuela": "ve",
    "Viet Nam": "vn",
    "Virgin Islands, British": "vg",
    "Virgin Islands, U.S.": "vi",
    "Wallis and Futuna": "wf",
    "Western Sahara": "eh",
    "Yemen": "ye",
    "Zambia": "zm",
    "Zimbabwe": "zw",
}

# Database path
DB_PATH = Path("bucket/_downloads/crawls/crawls.sqlite3")
CRAWLS_DIR = Path("bucket/_downloads/crawls")


# Web Crawling

def init_database() -> None:
    """Initialize SQLite database with crawls table."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS crawls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT,
            favicon TEXT,
            status_code INTEGER,
            word_count INTEGER,
            crawl_duration REAL
        )
    """
    )

    conn.commit()
    conn.close()


def insert_crawl_record(
    url: str,
    title: str,
    file_path: str,
    favicon: str,
    status_code: int,
    word_count: int,
    crawl_duration: float,
) -> None:
    """Insert a crawl record into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO crawls (url, title, file_path, favicon, status_code, word_count, crawl_duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (url, title, file_path, favicon, status_code, word_count, crawl_duration),
    )

    conn.commit()
    conn.close()


def get_daily_folder() -> Path:
    """Get or create the daily folder path (YYYY-MM-DD-Day format)."""
    now = datetime.now()
    folder_name = now.strftime("%Y-%m-%d-%A")
    daily_path = CRAWLS_DIR / folder_name
    daily_path.mkdir(parents=True, exist_ok=True)
    return daily_path


def extract_favicon(result, url: str) -> str:
    """
    Extract favicon using extract_favicon library (if available), with fallback to metadata and standard URL.

    Args:
        result: CrawlResult from crawl4ai
        url: Original URL

    Returns:
        Favicon URL as string
    """
    if EXTRACT_FAVICON_AVAILABLE:
        try:
            favicons = from_url(url)

            if favicons:
                ico_favicon = None
                png_favicon = None

                for favicon in favicons:
                    if favicon.format == "ico" and not ico_favicon:
                        ico_favicon = favicon.url
                    elif favicon.format == "png" and not png_favicon:
                        png_favicon = favicon.url

                if ico_favicon:
                    return ico_favicon
                elif png_favicon:
                    return png_favicon
                else:
                    return favicons[0].url

        except Exception as e:
            print(f"extract_favicon library failed: {e}")

    if hasattr(result, "metadata") and result.metadata:
        favicon = result.metadata.get("favicon")
        if favicon:
            return favicon

        icon = result.metadata.get("icon")
        if icon:
            return icon

    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


def save_markdown(content: str, url: str, daily_folder: Path) -> str:
    """
    Save markdown content to file with unique MD5 hash-based filename.

    Args:
        content: Markdown content to save
        url: Source URL
        daily_folder: Folder to save in

    Returns:
        Relative file path as string
    """
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    filename = f"{url_hash}.md"

    file_path = daily_folder / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)


def format_citation(title: str, url: str, favicon: str, content: str) -> str:
    """
    Format content with citation at the top.

    Args:
        title: Page title
        url: Page URL
        favicon: Favicon URL
        content: Markdown content

    Returns:
        Formatted string with citation + content
    """
    citation = f"""---
Title: {title}
URL: {url}
Favicon: {favicon}
---

{content}
"""
    return citation


def scrape_url(url: str) -> str:
    """
    Scrape a single URL and save it with metadata tracking.

    Args:
        url: URL to scrape

    Returns:
        Formatted string with citation and scraped content
    """
    return asyncio.run(_scrape_url_async(url))


async def _scrape_url_async(url: str) -> str:
    """Async implementation of scrape_url."""
    init_database()

    daily_folder = get_daily_folder()

    start_time = time.time()

    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        remove_overlay_elements=True,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=config)

        if not result.success:
            error_msg = f"Failed to crawl {url}: {result.error_message}"
            print(error_msg)
            return f"Error: {error_msg}"

        # Extract metadata
        title = (
            result.metadata.get("title", "Untitled") if result.metadata else "Untitled"
        )
        favicon = extract_favicon(result, url)
        status_code = result.status_code

        # Get markdown content
        markdown_content = (
            result.markdown.raw_markdown
            if hasattr(result.markdown, "raw_markdown")
            else str(result.markdown)
        )

        # Calculate metadata
        word_count = len(markdown_content.split())
        crawl_duration = time.time() - start_time

        # Save markdown file
        file_path = save_markdown(markdown_content, url, daily_folder)

        # Insert into database
        insert_crawl_record(
            url=url,
            title=title,
            file_path=file_path,
            favicon=favicon,
            status_code=status_code,
            word_count=word_count,
            crawl_duration=crawl_duration,
        )

        # Format and return result
        formatted_result = format_citation(title, url, favicon, markdown_content)

        return formatted_result


def scrape_urls(urls: List[str]) -> Dict[str, str]:
    """
    Scrape multiple URLs in parallel and save them with metadata tracking.

    Args:
        urls: List of URLs to scrape

    Returns:
        Dictionary mapping URL to formatted content with citations
    """
    return asyncio.run(_scrape_urls_async(urls))


async def _scrape_urls_async(urls: List[str]) -> Dict[str, str]:
    """Async implementation of scrape_urls."""
    init_database()

    daily_folder = get_daily_folder()

    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        remove_overlay_elements=True,
    )

    results_dict = {}

    async with AsyncWebCrawler() as crawler:
        start_times = {url: time.time() for url in urls}
        results = await crawler.arun_many(urls=urls, config=config)

        for result in results:
            url = result.url
            start_time = start_times.get(url, time.time())

            if not result.success:
                error_msg = f"Failed to crawl {url}: {result.error_message}"
                print(error_msg)
                results_dict[url] = f"Error: {error_msg}"
                continue

            title = (
                result.metadata.get("title", "Untitled")
                if result.metadata
                else "Untitled"
            )
            favicon = extract_favicon(result, url)
            status_code = result.status_code

            markdown_content = (
                result.markdown.raw_markdown
                if hasattr(result.markdown, "raw_markdown")
                else str(result.markdown)
            )

            word_count = len(markdown_content.split())
            crawl_duration = time.time() - start_time

            file_path = save_markdown(markdown_content, url, daily_folder)

            insert_crawl_record(
                url=url,
                title=title,
                file_path=file_path,
                favicon=favicon,
                status_code=status_code,
                word_count=word_count,
                crawl_duration=crawl_duration,
            )

            formatted_result = format_citation(title, url, favicon, markdown_content)
            results_dict[url] = formatted_result

    return results_dict


# Web Searching


def web_search(
    query: str,
    region: str = "us-en",
    safesearch: str = "on",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    page: int = 1,
    backend: str = "auto",
) -> List[Dict[str, str]]:
    """Web search using DDGS.

    Args:
        query: Search query. Supports operators like filetype:pdf, site:example.com, etc.
        region: Region code (e.g., us-en, uk-en, ru-ru). Defaults to us-en.
        safesearch: SafeSearch setting (on, moderate, off). Defaults to moderate.
        timelimit: Time limit (d=day, w=week, m=month, y=year). Defaults to None.
        max_results: Maximum number of results. Defaults to 10.
        page: Page number. Defaults to 1.
        backend: Search backends (auto, google, bing, etc). Defaults to auto.

    Returns:
        List of dictionaries containing search results with title, body, url fields.
    """
    return DDGS().text(
        query=query,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
        max_results=max_results,
        page=page,
        backend=backend
    )


def news_search(
    query: str,
    region: str = "us-en",
    safesearch: str = "moderate",
    timelimit: Optional[str] = None,
    max_results: Optional[int] = 10,
    page: int = 1,
    backend: str = "auto",
) -> List[Dict[str, str]]:
    """News search using DDGS.

    Args:
        query: News search query.
        region: Region code (e.g., us-en, uk-en, ru-ru). Defaults to us-en.
        safesearch: SafeSearch setting (on, moderate, off). Defaults to moderate.
        timelimit: Time limit (d=day, w=week, m=month, y=year). Defaults to None.
        max_results: Maximum number of results. Defaults to 10.
        page: Page number. Defaults to 1.
        backend: Search backends (auto, bing, duckduckgo, yahoo). Defaults to auto.

    Returns:
        List of dictionaries containing news results with title, body, url, date, source fields.
    """
    return DDGS().news(
        query=query,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
        max_results=max_results,
        page=page,
        backend=backend
    )


def image_search(
    query: str,
    region: str = "us-en",
    safesearch: str = "moderate",
    max_results: Optional[int] = 10,
    page: int = 1,
    backend: str = "duckduckgo",  # DuckDuckGo is the only supported backend for images
) -> List[Dict[str, str]]:
    """Image search using DDGS.

    Args:
        query: Image search query.
        region: Region code (e.g., us-en, uk-en, ru-ru). Defaults to us-en.
        safesearch: SafeSearch setting (on, moderate, off). Defaults to moderate.
        max_results: Maximum number of results. Defaults to 10.
        page: Page number. Defaults to 1.
        backend: Only supports 'duckduckgo' for image search.

    Returns:
        List of dictionaries containing image results with title, url, thumbnail, source fields.
    """
    return DDGS().images(
        query=query,
        region=region,
        safesearch=safesearch,
        max_results=max_results,
        page=page,
        backend=backend
    )


# if __name__ == "__main__":
    # Example web search
    # web_results = web_search(
    #     'python programming filetype:pdf',
    #     region='us-en',
    #     safesearch='off',
    #     timelimit='y',
    #     max_results=5
    # )
    # print("Web Search Results:")
    # print(json.dumps(web_results, indent=2))

# Example news search
# news_results = news_search(
#     'artificial intelligence',
#     region='us-en',
#     timelimit='w',
#     max_results=5
# )
# print("\nNews Search Results:")
# print(json.dumps(news_results, indent=2))

    # # Example image search
    # image_results = image_search(
    #     'nature photography',
    #     region='us-en',
    #     max_results=5
    # )
    # print("\nImage Search Results:")
    # print(json.dumps(image_results, indent=2))


    # # Test single URL
    # # print("Testing scrape_url()...")
    # # result = scrape_url("https://www.aycreation.com")
    # # print(f"Scraped {len(result)} characters")
    # # print(result[:500])  # Print first 500 chars

    # # print("\n" + "=" * 50 + "\n")

    # # # Test multiple URLs
    # # print("Testing scrape_urls()...")
    # # urls = ["https://admin.thehealthequip.com", "https://www.pixelthreader.in"]
    # # results = scrape_urls(urls)
    # # for url, content in results.items():
    # #     print(f"\n{url}: {len(content)} characters")
    # #     print(content[:300])  # Print first 300 chars