import ipaddress
import json
import re
import socket
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class ProductImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self._in_json_ld = False
        self._json_ld_chunks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
            content = attrs.get("content")
            if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src", "image"} and content:
                self.images.append(content)
        if tag == "link":
            rel = (attrs.get("rel") or "").lower()
            href = attrs.get("href")
            if "image_src" in rel and href:
                self.images.append(href)
        if tag in {"img", "source"}:
            for key in ("src", "data-src", "data-original", "data-lazy", "data-image"):
                value = attrs.get(key)
                if value:
                    self.images.append(value)
            srcset = attrs.get("srcset") or attrs.get("data-srcset")
            if srcset:
                self.images.extend(parse_srcset(srcset))
        if tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_chunks = []

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_chunks.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self._extract_json_images("".join(self._json_ld_chunks))

    def _extract_json_images(self, raw):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        self._walk_json(data)

    def _walk_json(self, value):
        if isinstance(value, dict):
            image = value.get("image")
            if isinstance(image, str):
                self.images.append(image)
            elif isinstance(image, list):
                self.images.extend(item for item in image if isinstance(item, str))
            elif isinstance(image, dict) and isinstance(image.get("url"), str):
                self.images.append(image["url"])
            for child in value.values():
                self._walk_json(child)
        elif isinstance(value, list):
            for child in value:
                self._walk_json(child)


def parse_srcset(srcset):
    urls = []
    for candidate in srcset.split(","):
        url = candidate.strip().split(" ")[0]
        if url:
            urls.append(url)
    return urls


def normalize_scraped_url(raw_url):
    url = unescape(raw_url.strip().strip("\"'"))
    url = url.replace("\\/", "/")
    try:
        url = bytes(url, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        pass
    return url


def extract_image_urls_from_text(html):
    patterns = [
        r'https?:\\?/\\?/[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?',
        r'//[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, html, flags=re.IGNORECASE))
    return urls


def image_score(image_url):
    parsed = urlparse(image_url)
    value = image_url.lower()
    score = 0
    if parsed.netloc:
        score += 2
    if any(token in value for token in ("product", "goods", "main", "large", "zoom", "images3_pi", "ltwebstatic")):
        score += 6
    if any(token in value for token in ("logo", "sprite", "icon", "avatar", "placeholder", "loading", "banner")):
        score -= 8
    if any(size in value for size in ("405x552", "600x", "800x", "1200x")):
        score += 2
    return score


def is_safe_public_url(raw_url):
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False
    return True


def find_product_image_url(product_url):
    request = Request(
        product_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SistemaImport/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""
        html = response.read(1_500_000).decode("utf-8", errors="ignore")

    parser = ProductImageParser()
    parser.feed(html)
    candidates = parser.images + extract_image_urls_from_text(html)
    normalized = []
    seen = set()
    for image_url in candidates:
        image_url = normalize_scraped_url(image_url)
        absolute_url = urljoin(product_url, image_url)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        if urlparse(absolute_url).scheme in {"http", "https"}:
            normalized.append(absolute_url)
    normalized.sort(key=image_score, reverse=True)
    if normalized:
        return normalized[0]
    return ""
