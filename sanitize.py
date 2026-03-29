import re
import bleach

# ── HTML sanitization ────────────────────────────────────────────────────────

ALLOWED_TAGS = [
    'div', 'section', 'article', 'main', 'aside', 'header', 'footer', 'nav',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'strong', 'em', 'u', 's',
    'ul', 'ol', 'li', 'br', 'hr',
    'img', 'figure', 'figcaption',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'button', 'form', 'input', 'textarea', 'label', 'select', 'option',
]

ALLOWED_ATTRS = {
    '*':   ['class', 'id', 'style'],
    'a':   ['href', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
}


def sanitize_html(raw: str) -> str:
    return bleach.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


# ── CSS sanitization ────────────────────────────────────────────────────────

CSS_BLACKLIST = [
    r'javascript\s*:',
    r'expression\s*\(',
    r'url\s*\(\s*["\']?\s*javascript',
    r'@import',
    r'behavior\s*:',
]


def sanitize_css(raw: str) -> str:
    for pattern in CSS_BLACKLIST:
        raw = re.sub(pattern, '', raw, flags=re.IGNORECASE)
    return raw
