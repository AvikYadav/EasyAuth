# EasyAuth — Full Developer Documentation

This document covers every file, every function, every data flow, and every design decision in the EasyAuth codebase. It is written for developers who want to understand the system deeply, contribute to it, or adapt it.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Structure](#2-repository-structure)
3. [How It All Works — Data Flow](#3-how-it-all-works--data-flow)
   - [Platform signup/login (owner)](#31-platform-signuplogin-owner)
   - [Service user signup/login (end user)](#32-service-user-signuplogin-end-user)
   - [Token usage in a third-party app](#33-token-usage-in-a-third-party-app)
   - [Auth page customization flow](#34-auth-page-customization-flow)
4. [Backend Files](#4-backend-files)
   - [main.py](#41-mainpy)
   - [database.py](#42-databasepy)
   - [jwt_token.py](#43-jwt_tokenpy)
   - [encryption.py](#44-encryptionpy)
   - [sanitize.py](#45-sanitizepy)
   - [logger.py](#46-loggerpy)
5. [MongoDB Schema](#5-mongodb-schema)
6. [API Reference](#6-api-reference)
7. [Templates](#7-templates)
8. [Static Files](#8-static-files)
9. [Auth Page Customization System](#9-auth-page-customization-system)
10. [Page Templates](#10-page-templates)
11. [CI/CD Pipeline](#11-cicd-pipeline)
12. [Contributing](#12-contributing)
13. [Known Gotchas & Design Decisions](#13-known-gotchas--design-decisions)

---

## 1. Project Overview

EasyAuth is a hosted authentication service. A developer (the "owner") registers on the platform, creates a "service" representing their app, and gets an API key. Their users are then sent to an EasyAuth-hosted login/signup page. On success, the user is redirected back to the developer's app with an encrypted token. The developer's backend decrypts the token with their API key and verifies it.

**What EasyAuth replaces in a third-party app:**
- Signup and login UI
- Password hashing and storage
- Session token generation
- Per-user data storage (arbitrary JSON)

**What EasyAuth does NOT provide:**
- Email verification (field exists in schema but flow isn't wired up)
- OAuth / social login
- Rate limiting at the route level (library is installed but not wired up)

**Tech stack:**
- Python 3.12, Flask 3.1
- MongoDB (via pymongo 4.16)
- PyJWT (HS256), Fernet (AES-128-CBC + HMAC-SHA256), bcrypt
- bleach (HTML sanitization), GrapeJS v0.21.13 (drag-drop page editor)
- Gunicorn (production), Azure App Service (deployment target)

---

## 2. Repository Structure

```
CustomAuth/
├── main.py                        # All Flask routes and app-level helpers
├── database.py                    # All MongoDB operations
├── jwt_token.py                   # JWT generation and verification
├── encryption.py                  # Fernet encrypt/decrypt for API tokens
├── sanitize.py                    # HTML and CSS sanitizers
├── logger.py                      # Event logging helper
├── requirements.txt               # Python dependencies
├── .env                           # Secrets (not committed)
│
├── templates/
│   ├── signup.html                # Platform owner signup/login page
│   ├── login.html                 # (unused — signup.html handles both modes)
│   ├── dashboard.html             # Service list dashboard
│   ├── service_detail.html        # Per-service overview, logs, settings
│   ├── auth.html                  # End-user auth gate (served to third-party app users)
│   └── auth_editor.html           # GrapeJS drag-drop page editor
│
├── static/
│   ├── style.css                  # Shared base styles (auth gate + platform signup)
│   ├── signup.js                  # Tab switching on platform signup page
│   ├── auth.js                    # Tab switching on auth gate
│   ├── dashboard.css              # Dashboard styles
│   ├── dashboard.js               # Dashboard interactions
│   ├── service_detail.css         # Service detail page styles (includes template grid)
│   └── service_detail.js          # Logs filter, template picker, delete handler
│
└── Docs/
    ├── DocumentationToSetup.md    # Local setup guide
    └── DOCUMENTATION.md           # This file
```

---

## 3. How It All Works — Data Flow

### 3.1 Platform Signup/Login (Owner)

This is the EasyAuth developer registering their own account.

```
Browser                        Flask (main.py)              MongoDB
  |                                  |                          |
  |-- GET /  ───────────────────► render signup.html            |
  |                                  |                          |
  |-- POST /signup ─────────────►    |                          |
  |   {username, email,              |                          |
  |    password, confirm}            |-- bcrypt hash password   |
  |                                  |-- create_user_profile() ►|
  |                                  |   (inserts profile doc    |
  |                                  |    into <username> coll.) |
  |                                  |-- generate_token(username)|
  |◄── redirect /dashboard ─────────|   (HS256 JWT, 5hr expiry) |
  |    Set-Cookie: auth_token=JWT    |                          |
```

The session cookie (`auth_token`) is `HttpOnly; Secure; SameSite=Strict`. It is a plain JWT (not encrypted) signed with `JWT_SECRET_KEY`. The secret is regenerated on every server start — see [Known Gotchas](#13-known-gotchas--design-decisions).

---

### 3.2 Service User Signup/Login (End User)

This is an end user of a third-party app going through EasyAuth.

```
End User Browser               Flask (main.py)                   MongoDB
     |                               |                               |
     |-- GET /auth/<owner>/<svc> ──► | load page_css, page_extra_css |
     |                               |-- service_get_service_document|
     |◄── render auth.html ──────────|   (reads service doc from     |
     |    (themed login/signup UI)   |    <owner> collection)        |
     |                               |                               |
     |-- POST /auth/<owner>/<svc> ──►|                               |
     |   {username, password,        |                               |
     |    email (signup), mode}      |                               |
     |                               |                               |
     |        [SIGNUP path]          |                               |
     |                               |-- bcrypt hash password        |
     |                               |-- generate_token(username)    |
     |                               |-- encrypt_message(token,      |
     |                               |     service.api_key)          |
     |                               |-- service_create_user_entry() |
     |                               |-- service_add_user_to_svc() ──►|
     |                               |-- log_event(SIGNUP_SUCCESS)   |
     |                               |-- log_event(TOKEN_ISSUED)     |
     |◄── redirect callback_url      |                               |
     |    ?token=<encrypted_jwt>     |                               |
     |                               |                               |
     |        [LOGIN path]           |                               |
     |                               |-- find user in users array    |
     |                               |-- bcrypt verify password      |
     |                               |-- generate_token(username)    |
     |                               |-- encrypt_message(token,      |
     |                               |     service.api_key)          |
     |                               |-- service_update_user_jwt() ──►|
     |                               |-- log_event(LOGIN_SUCCESS)    |
     |                               |-- log_event(TOKEN_ISSUED)     |
     |◄── redirect callback_url      |                               |
     |    ?token=<encrypted_jwt>     |                               |
```

The token in the redirect query string is:
1. A HS256-signed JWT containing `{ sub, jti, iat, exp }`
2. Fernet-encrypted with the service's API key (AES-128-CBC + HMAC-SHA256)
3. URL-encoded before being appended to the callback URL

The third-party app receives `?token=<url-encoded-fernet-ciphertext>`. To use it, the app must:
1. URL-decode the token
2. Decrypt it with their API key using `Fernet(api_key).decrypt(token)`
3. Decode the resulting JWT string with `jwt.decode(jwt_string, api_key_or_any_key...)`

> Note: The JWT itself is verified server-side by EasyAuth's `/verify/` and `/retrieve/` endpoints. Third-party backends do not need to verify the JWT signature themselves — they just pass the decrypted JWT string to those endpoints.

---

### 3.3 Token Usage in a Third-Party App

After the redirect, the developer's backend uses the token to talk to EasyAuth:

```
Third-Party Backend                Flask (main.py)              MongoDB
       |                                  |                         |
       |-- POST /retrieve/<owner>/<svc>   |                         |
       |   { "token": "<plain_jwt>" }     |                         |
       |                                  |-- jwt.decode(token)     |
       |                                  |-- find user in svc doc  |
       |                                  |-- log_event(DATA_READ)  |
       |◄── { username, user_data } ──────|                         |
       |                                  |                         |
       |-- POST /update/<owner>/<svc>     |                         |
       |   { "token": "...",              |                         |
       |     "user_data": {...} }         |                         |
       |                                  |-- jwt.decode(token)     |
       |                                  |-- service_update_user_  |
       |                                  |   data() ──────────────►|
       |                                  |-- log_event(DATA_WRITE) |
       |◄── { message: "updated" } ───────|                         |
       |                                  |                         |
       |-- POST /verify/<owner>/<svc>     |                         |
       |   { "token": "..." }             |                         |
       |                                  |-- jwt.decode(token)     |
       |                                  |-- confirm user exists   |
       |                                  |-- log_event(TOKEN_      |
       |                                  |   VERIFIED)             |
       |◄── { message, username } ────────|                         |
```

The `token` passed to these endpoints is the **decrypted** JWT string — not the encrypted ciphertext from the callback URL. The developer's backend is responsible for decrypting it first.

---

### 3.4 Auth Page Customization Flow

```
Owner Browser                  Flask (main.py)               MongoDB
     |                               |                            |
     |  [Choose Template]            |                            |
     |-- click template card         |                            |
     |-- click "Apply & Open Editor" |                            |
     |-- POST /dashboard/service/    |                            |
     |   <svc>/apply-template        |                            |
     |   { template_id: "..." }      |                            |
     |                               |-- PAGE_TEMPLATES[id]       |
     |                               |-- build_css_from_          |
     |                               |   style_data(tpl.style_data|
     |                               |-- sanitize_html(above/     |
     |                               |   below html)              |
     |                               |-- sanitize_css(page_css,   |
     |                               |   page_extra_css)          |
     |                               |-- update_service(          |
     |                               |   page_above_html,         |
     |                               |   page_below_html,         |
     |                               |   page_css,                |
     |                               |   page_extra_css,          |
     |                               |   page_style_data,         |
     |                               |   page_layout) ───────────►|
     |◄── { ok, redirect: /edit-page}|                            |
     |                               |                            |
     |  [Visual Editor]              |                            |
     |-- GET /dashboard/service/     |                            |
     |   <svc>/edit-page  ──────────►|                            |
     |◄── render auth_editor.html    |                            |
     |    (GrapeJS + style panel)    |                            |
     |                               |                            |
     |  [Save from editor]           |                            |
     |-- POST /dashboard/service/    |                            |
     |   <svc>/save-page             |                            |
     |   { above_html, below_html,   |                            |
     |     css, style_data }         |                            |
     |                               |-- sanitize_html()          |
     |                               |-- sanitize_css()           |
     |                               |-- update_service(          |
     |                               |   page_above_html,         |
     |                               |   page_below_html,         |
     |                               |   page_css,                |
     |                               |   page_style_data,         |
     |                               |   page_layout) ───────────►|
     |                               |   NOTE: page_extra_css is  |
     |                               |   NOT overwritten here     |
     |◄── { ok: true } ─────────────|                            |
     |                               |                            |
     |  [End user visits auth page]  |                            |
     |-- GET /auth/<owner>/<svc> ───►|                            |
     |                               |-- read page_css,           |
     |                               |   page_extra_css,          |
     |                               |   page_above_html,         |
     |                               |   page_below_html ────────►|
     |◄── render auth.html           |                            |
     |    <style>page_css</style>    |                            |
     |    <style>page_extra_css</style>                           |
     |    above_html ... card ...    |                            |
     |    below_html                 |                            |
```

`page_css` and `page_extra_css` are kept in separate DB fields deliberately:
- `page_css` is regenerated by `buildCss()` every time the user saves from the editor (colors, layout, typography — things the style panel controls).
- `page_extra_css` holds template-specific styling (header backgrounds, grid layouts, nav links) and is only written by `apply_template`. The editor never touches it, so template styles persist through editor sessions.

---

## 4. Backend Files

### 4.1 `main.py`

The entire Flask application. No blueprints — all routes live in one file.

#### App-level setup

```python
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)
db = database.connect_to_database()
```

`SECRET_KEY` is used by Flask for flash messages (displaying the API key once after service creation). It is regenerated on restart — flash messages do not persist across restarts, which is fine since they're transient.

#### `PAGE_TEMPLATES` dict

A module-level dict of 5 pre-built auth page layouts. Each entry has:

| Key | Type | Purpose |
|---|---|---|
| `name` | str | Display name shown in UI |
| `description` | str | Short description shown in UI |
| `layout` | `"column"` or `"row"` | Controls `flex-direction` on `.page-wrapper` |
| `above_html` | str | HTML inserted above the auth card |
| `below_html` | str | HTML inserted below the auth card |
| `extra_css` | str | CSS for template-specific classes (stored in `page_extra_css`) |
| `style_data` | dict | Style panel values (colors, radius, etc.) used to generate `page_css` |

All HTML uses CSS classes (never `style=""` attributes) because bleach/html5lib HTML-encodes single quotes inside `style=""` values, which breaks CSS property values like `font-family:'DM Mono'`.

**Template IDs:**
- `"marketing-header"` — Dark fixed header + minimal footer, column layout
- `"left-brand-panel"` — Gradient brand panel left, auth card right (row layout)
- `"announcement-banner"` — Slim promo bar top, 3-column footer, column layout
- `"testimonial-strip"` — Auth card left, testimonial cards right (row layout)
- `"stepped-onboarding"` — Progress bar + step dots around card, column layout

#### `build_css_from_style_data(s: dict) -> str`

Python mirror of the `buildCss()` function in `auth_editor.html`. Takes a style dict (same shape as `page_style_data` stored in the DB) and returns the full CSS string for `page_css`.

Handles both `pageLayout === "row"` (side-by-side) and `"column"` (stacked). Called by `apply_template` to generate `page_css` from a template's `style_data`.

The CSS it generates covers: `html, body`, `.page-wrapper`, `.above-card`, `.below-card`, `.card`, `.card h1`, `.field label`, `.field input`, `.card .btn`, `.tabs`, `.tab.active`, `.wordmark`, `.powered-by`.

#### Helper functions

**`hash_password(password)`** — bcrypt hash, cost factor 12. Returns a string (decoded from bytes).

**`verify_password(stored_hash, provided_password)`** — constant-time bcrypt comparison.

**`api_response(data, error, status_code)`** — uniform JSON wrapper.
- Success: `{ "status": "success", "data": {...} }`
- Error: `{ "status": "error", "message": "..." }`

**`get_client_ip()`** — reads `X-Forwarded-For` header, falls back to `request.remote_addr`.

**`require_auth()`** — reads `auth_token` cookie, verifies JWT. Returns `(payload, None)` on success, `(None, error_response)` on failure. Used as a guard at the top of every dashboard route.

#### Jinja filters

**`timeago`** — converts a `datetime` to a human-readable string (`"5m ago"`, `"2h ago"`, `"3d ago"`). Handles naive datetimes by assuming UTC.

**`fmt_time`** — formats a `datetime` to `"YYYY-MM-DD HH:MM:SS"`.

#### Routes

See [Section 6 — API Reference](#6-api-reference) for the full route table.

---

### 4.2 `database.py`

All MongoDB operations. Every function takes `db` (the pymongo database instance) as its first argument — the connection is established once in `main.py` and passed down.

#### Connection

```python
DB_NAME = "USER_DATA"

def connect_to_database():
    client = MongoClient(url)  # url from .env: mongo_url
    return client[DB_NAME]
```

#### Collection structure

Each platform user gets their own MongoDB collection, named after their username (lowercased). This provides hard isolation — there are no shared tables and no multi-tenant query filters.

Inside a user's collection, all documents have a `type` field that distinguishes them:

| `type` value | Description |
|---|---|
| `"profile"` | The owner's own account (one per collection) |
| `"service"` | One service document per service registered |
| `"service_logs"` | One log document per service (contains an array of events) |

#### Profile functions

**`create_user_profile(db, username, profile_data)`**
- Creates the user's collection
- Creates a partial unique index on `type == "profile"` to prevent duplicate profiles
- Inserts the profile document
- Returns the document or `None` on `DuplicateKeyError`

**`get_user_profile(db, username)`** — `find_one({"type": "profile"})`

**`update_user_profile(db, username, updated_data)`**
- Uses dot-notation keys (`data.email`, `data.is_verified`) to merge fields without overwriting others
- Returns `True`/`False`

**`delete_user_profile(db, username)`** — drops the entire collection (removes profile + all services + all logs)

#### Service functions

**`create_service(db, username, service_name, service_data, user_data)`**
- Creates a compound partial unique index on `(type, service_name)` for service documents
- `user_data` is the initial `users` array (always `[]` when called from `main.py`)
- Returns the document or `None` on `DuplicateKeyError`

**`get_service(db, username, service_name)`** — `find_one({"type": "service", "service_name": ...})`

**`get_all_services(db, username)`** — `find({"type": "service"})`

**`update_service(db, username, service_name, updated_data)`**
- Uses dot-notation `data.<key>` for each key in `updated_data`
- This is how auth page fields are stored: `data.page_css`, `data.page_extra_css`, `data.page_above_html`, etc.

**`delete_service(db, username, service_name)`** — `delete_one(...)`

**`get_all_user_profiles(db)`** — iterates all collections, fetches each `type == "profile"` document. Used for admin purposes.

#### Service user functions

These operate on users *within* a service document's `users` array.

**`service_get_service_document(db, user_collection_name, service_name)`**
- Different from `get_service` — this takes the raw collection name (the owner's username) as the first arg instead of going through `get_user_collection`. Used in the auth gate and data API where the owner username comes from the URL parameter.

**`service_create_user_entry(username, password, email, jwt)`**
- Returns a dict representing one user in the `users` array:
```python
{
    "username":    username,
    "password":    bcrypt_hash,
    "email":       email,
    "is_verified": False,
    "created_at":  iso_string,
    "jwt":         jwt_string,
    "user_data":   []
}
```

**`service_add_user_to_service(db, user_collection_name, service_name, new_user_entry)`**
- `$push` to the `users` array

**`service_update_user_jwt(db, user_collection_name, service_name, username, new_token)`**
- Uses `users.username` in the filter and `$` positional operator to update only the matched user's `jwt`, `last_login`, `updated_at`

**`service_update_user_data(db, user_collection_name, service_name, username, data_dict)`**
- Overwrites the entire `users.$.user_data` field with `data_dict`
- This replaces, not merges — the third-party app controls the shape

#### Logging functions

**`insert_log(db, owner, service_name, log_data)`**
- Upserts a single `type == "service_logs"` document per service
- Uses `$push` with `$each`, `$sort`, `$slice: -1000` to append and cap the array at 1000 entries

**`get_logs(db, owner, service_name, event, status, user_id, limit, skip)`**
- Reads the full `logs` array from the single log document
- Filters in Python (fine since the array is capped at 1000)
- Returns newest-first (reverses the ascending-sorted array before slicing)

**`get_service_stats(db, owner, service_name)`**
- Reads the service document for `total_users` count
- Reads the log document for the last-1-hour window
- Returns: `total_users`, `active_users_1h`, `tokens_issued_1h`, `tokens_verified_1h`, `last_activity`

---

### 4.3 `jwt_token.py`

Handles platform session tokens (for dashboard access) and service user tokens (issued after auth gate sign-in/login).

```python
JWT_SECRET_KEY  = secrets.token_hex(35)   # regenerated on every server start
JWT_ALGORITHM   = "HS256"
JWT_EXPIRY_HOURS = 5
```

**`generate_token(username)`**
- Payload: `{ sub, jti, iat, exp }`
- `jti` is a UUID4 — makes every token unique even for the same user
- Returns a signed JWT string

**`verify_token(token)`**
- Decodes and verifies the signature and expiry
- Returns the payload dict on success, `None` on `ExpiredSignatureError` or `InvalidTokenError`

> **Important**: The JWT secret is ephemeral. Every server restart invalidates all active sessions and all issued service user tokens. For production, load the secret from an env variable. See [Known Gotchas](#13-known-gotchas--design-decisions).

---

### 4.4 `encryption.py`

Handles encryption of the JWT before it is sent to the third-party app's callback URL.

**`generate_key()`**
- `Fernet.generate_key()` — returns a URL-safe base64-encoded 32-byte key
- Called once when a service is created; the key is stored in the service document as `api_key`

**`encrypt_message(message, key)`**
- Fernet encrypt: AES-128-CBC + HMAC-SHA256 authentication
- `message` is the JWT string; `key` is the service's API key string
- Returns an encrypted string (base64-encoded ciphertext)

**`decrypt_message(encrypted_message, key)`**
- Fernet decrypt: verifies HMAC before decrypting
- A tampered ciphertext raises `cryptography.fernet.InvalidToken` — it does not silently return garbage

**`write_to_log(content)`**
- Appends to `log.txt` — a leftover debug helper. Not called in production code. Safe to ignore.

---

### 4.5 `sanitize.py`

Two sanitizers that sit between user-submitted content and the database.

#### HTML sanitizer

```python
ALLOWED_TAGS = [
    'div', 'section', 'article', 'main', 'aside', 'header', 'footer', 'nav',
    'h1'-'h6', 'p', 'span', 'a', 'strong', 'em', 'u', 's',
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
```

**`sanitize_html(raw)`** — wraps `bleach.clean()` with the allowlist above. Strips disallowed tags entirely (does not escape them).

**Critical limitation**: bleach uses an html5lib parser which HTML-encodes single quotes inside attribute values. `style="font-family:'DM Mono'"` becomes `style="font-family:&#x27;DM Mono&#x27;"`, which is invalid CSS and breaks the entire declaration. This is why all template HTML uses CSS classes instead of `style=""` attributes.

#### CSS sanitizer

**`sanitize_css(raw)`** — regex blacklist approach. Strips:
- `javascript:` (JS protocol in `url()`)
- `expression(...)` (IE legacy eval)
- `url(javascript:...)` (JS in url())
- `@import` (external resource loading)
- `behavior:` (IE HTC behavior)

Everything else is passed through unchanged. This is intentionally permissive — any valid CSS layout/design property works. The sanitizer only blocks injection vectors, not design capabilities.

---

### 4.6 `logger.py`

Thin wrapper around `database.insert_log`.

#### Event type constants

```python
SIGNUP_SUCCESS    = "signup_success"
SIGNUP_FAIL       = "signup_fail"
LOGIN_SUCCESS     = "login_success"
LOGIN_FAIL        = "login_fail"
TOKEN_ISSUED      = "token_issued"
TOKEN_VERIFIED    = "token_verified"
TOKEN_VERIFY_FAIL = "token_verify_fail"
DATA_READ         = "data_read"
DATA_WRITE        = "data_write"
ERROR             = "error"
```

**`log_event(db, owner, service_name, event, status, user_id, ip, error_message, metadata)`**

Builds this dict and passes it to `database.insert_log`:

```python
{
    "timestamp":     datetime (UTC),
    "event":         str,       # one of the constants above
    "status":        str,       # "success" or "failure"
    "user_id":       str|None,  # service user's username
    "ip":            str|None,  # client IP
    "error_message": str|None,  # human-readable error (on failures)
    "metadata":      dict,      # extra context
}
```

---

## 5. MongoDB Schema

### Platform user collection (`<username>`)

One collection per platform owner. Collection name = username (lowercase, stripped).

#### Profile document

```json
{
    "_id":        ObjectId,
    "type":       "profile",
    "user_id":    "uuid4-string",
    "username":   "john_doe",
    "data": {
        "email":         "john@example.com",
        "password_hash": "$2b$12$...",
        "is_verified":   false
    },
    "created_at": ISODate,
    "updated_at": ISODate
}
```

Unique partial index on `type == "profile"` prevents duplicate profile documents.

#### Service document

```json
{
    "_id":          ObjectId,
    "type":         "service",
    "service_id":   "uuid4-string",
    "service_name": "my_app",
    "data": {
        "api_key":        "fernet-key-string",
        "callback_url":   "https://myapp.com/callback",

        "page_above_html": "<header class=\"tpl-mh-header\">...</header>",
        "page_below_html": "<footer class=\"tpl-mh-footer\">...</footer>",
        "page_css":        "html, body { background-color: #f7f6f2; } ...",
        "page_extra_css":  ".tpl-mh-header { background: #111110; ... }",
        "page_style_data": "{\"pageBg\":\"#f7f6f2\",\"pageLayout\":\"column\",...}",
        "page_layout":     "column"
    },
    "users": [
        {
            "username":    "alice",
            "password":    "$2b$12$...",
            "email":       "alice@example.com",
            "is_verified": false,
            "created_at":  "2026-04-11T10:00:00Z",
            "jwt":         "eyJ...",
            "last_login":  "2026-04-11T10:05:00Z",
            "updated_at":  ISODate,
            "user_data":   {}
        }
    ],
    "created_at": ISODate,
    "updated_at": ISODate
}
```

Unique compound partial index on `(type, service_name)` prevents duplicate service names per user.

Auth page fields (`page_*`) are optional — absent until the owner visits the editor or applies a template.

`page_style_data` is stored as a JSON string (not a subdocument) because it is passed directly to the editor's JS and parsed there.

`user_data` starts as `[]` but `service_update_user_data` overwrites it with whatever dict the third-party app sends.

#### Service log document

```json
{
    "_id":          ObjectId,
    "type":         "service_logs",
    "service_name": "my_app",
    "logs": [
        {
            "timestamp":     ISODate,
            "event":         "login_success",
            "status":        "success",
            "user_id":       "alice",
            "ip":            "203.0.113.42",
            "error_message": null,
            "metadata":      {}
        }
    ],
    "created_at": ISODate,
    "updated_at": ISODate
}
```

One document per service. The `logs` array is capped at 1000 entries (oldest evicted) via `$push + $slice`.

---

## 6. API Reference

### Platform auth routes

| Method | URL | Description |
|---|---|---|
| GET | `/` | Render platform signup/login page |
| POST | `/signup` | Create platform account |
| POST | `/login` | Authenticate platform owner |
| GET | `/logout` | Clear session cookie, redirect to `/` |

### Dashboard routes (require `auth_token` cookie)

| Method | URL | Description |
|---|---|---|
| GET | `/dashboard` | List all services with stats |
| POST | `/dashboard/create-service` | Create a new service (generates API key) |
| POST | `/dashboard/delete-service/<service_name>` | Delete a service |
| POST | `/dashboard/edit-service` | Update a service's callback URL |
| GET | `/dashboard/service/<service_name>` | Service detail page |
| GET | `/dashboard/service/<service_name>/logs` | JSON: filtered logs (AJAX) |
| GET | `/dashboard/service/<service_name>/edit-page` | GrapeJS editor |
| POST | `/dashboard/service/<service_name>/save-page` | Save editor output |
| POST | `/dashboard/service/<service_name>/apply-template` | Apply a pre-built template |

#### `POST /dashboard/service/<service_name>/save-page`

Request body (JSON):
```json
{
    "above_html":  "<div>...</div>",
    "below_html":  "<footer>...</footer>",
    "css":         ".page-wrapper { ... }",
    "style_data":  "{\"pageBg\":\"#fff\",\"pageLayout\":\"column\",...}"
}
```

Response: `{ "ok": true }`

Note: `page_extra_css` is never sent by the editor and never overwritten by this route.

#### `POST /dashboard/service/<service_name>/apply-template`

Request body (JSON):
```json
{ "template_id": "marketing-header" }
```

Valid `template_id` values: `"marketing-header"`, `"left-brand-panel"`, `"announcement-banner"`, `"testimonial-strip"`, `"stepped-onboarding"`.

Response: `{ "ok": true, "redirect": "/dashboard/service/<name>/edit-page" }`

#### `GET /dashboard/service/<service_name>/logs`

Query params (all optional):
- `event` — filter by event type string
- `status` — `"success"` or `"failure"`
- `user_id` — filter by service username
- `limit` — max results (default 100, max 500)
- `skip` — offset for pagination

Response:
```json
{
    "status": "success",
    "data": {
        "logs": [ { "timestamp": "...", "event": "...", ... } ]
    }
}
```

### Auth gate routes (for third-party app users)

| Method | URL | Description |
|---|---|---|
| GET | `/auth/<owner>/<service>` | Render themed signup/login page |
| POST | `/auth/<owner>/<service>` | Process signup or login, redirect with token |

### Data API routes (JSON, for third-party backends)

All three accept `Content-Type: application/json` and return `{ "status": "success"/"error", "data"/"message": ... }`.

#### `POST /retrieve/<owner>/<service>`

Request:
```json
{ "token": "<plain_jwt_string>" }
```

Response (success):
```json
{
    "status": "success",
    "data": {
        "username":  "alice",
        "user_data": { "plan": "free", "onboarded": true }
    }
}
```

#### `POST /update/<owner>/<service>`

Request:
```json
{
    "token":     "<plain_jwt_string>",
    "user_data": { "plan": "pro", "onboarded": true }
}
```

Response (success):
```json
{ "status": "success", "data": { "message": "User data updated." } }
```

#### `POST /verify/<owner>/<service>`

Request:
```json
{ "token": "<plain_jwt_string>" }
```

Response (success):
```json
{
    "status": "success",
    "data": { "message": "Token is valid.", "username": "alice" }
}
```

---

## 7. Templates

### `signup.html`

Platform owner signup and login page. Both modes share the same template — mode is toggled by JS. Sends to `POST /signup` or `POST /login` based on the active tab.

Variables: `error` (optional), `username` (optional, repopulates field on error), `mode` (optional, defaults to signup).

### `auth.html`

The auth gate rendered for third-party app end users. Receives page customization variables from the `auth()` route.

Variables:
- `user` — service owner's username
- `service` — service name
- `mode` — `"signup"` or `"login"`
- `page_css` — CSS from style panel (colors, layout)
- `page_extra_css` — CSS from template (header/footer/panel styles)
- `page_above_html` — HTML above the card
- `page_below_html` — HTML below the card
- `error` / `message` — optional feedback banners
- `username`, `email` — optional repopulation on error

Both `page_css` and `page_extra_css` are rendered as separate `<style>` tags with `| safe`. They are sanitized before storage, not at render time.

### `auth_editor.html`

The GrapeJS drag-drop page editor. Self-contained (~700 lines) — includes GrapeJS CDN, custom style panel, and all editor logic inline.

Key JS globals:
- `DEFAULTS` — default style panel values
- `FIELD_MAP` — maps style panel input IDs to `style_data` keys
- `buildCss(s)` — generates `page_css` from a style dict (mirrors `build_css_from_style_data` in Python)
- `BASE_CSS` — base CSS injected into GrapeJS canvas for editor preview fidelity

On load, the editor populates from `page_style_data` (Jinja-injected JSON string). On save, it POSTs `above_html`, `below_html`, the output of `buildCss()`, and the style dict to `/save-page`.

GrapeJS is used only as a drag-drop block container. Its CSS generation is completely bypassed — `buildCss()` generates all CSS from the style panel values.

### `dashboard.html`

Lists all services as cards. Shows stats (total users, active users, last activity). Has a create-service modal.

### `service_detail.html`

Three-tab layout: Overview, Logs, Settings.

- **Overview**: stats cards (total users, active 1h, tokens issued 1h, tokens verified 1h, last activity)
- **Logs**: filterable event log (AJAX via `service_detail.js`)
- **Settings**: template picker grid, "Edit Auth Page" link, callback URL editor, danger zone (delete service)

Receives `templates=PAGE_TEMPLATES` from the route, iterates it to render the template grid.

---

## 8. Static Files

### `style.css`

Shared base styles used by both `signup.html` (platform) and `auth.html` (auth gate). Defines CSS custom properties (`--bg`, `--surface`, `--ink`, `--muted`, `--border`, `--accent`), card styles, form styles, tabs, error/success banners, and the `.page-wrapper` / `.above-card` / `.below-card` layout containers.

`body` has `display:flex; align-items:center; justify-content:center; min-height:100vh` for the platform signup page card centering. The auth gate uses `.page-wrapper` (which is `display:flex; flex-direction:column; min-height:100vh`) for its layout — `body` flex styles are compatible because `.page-wrapper` is the sole body child.

### `signup.js`

Attaches click listeners to the sign-up/log-in tabs on the platform signup page. Updates form heading, button label, email field visibility, and hidden mode input. No inline event handlers (CSP compliant).

### `auth.js`

Same tab-switching logic as `signup.js`, for the auth gate page.

### `dashboard.css` / `dashboard.js`

Dashboard-specific styles and interactions. `dashboard.js` handles the create-service modal and the flash-message API key display.

### `service_detail.css`

Service detail page styles. Includes:
- Three-tab layout
- Stats cards
- Log entry expand/collapse
- Template picker grid (5-column, responsive)
- Template thumbnail preview styles (`.tpl-thumb--<id>` variants)

### `service_detail.js`

Three areas of responsibility:

**1. Tab switching** — `.detail-tab` click handler shows/hides `.tab-panel` divs.

**2. Logs** — expand/collapse on `.log-entry` click. AJAX filter via `GET /logs?...`. `renderLogs()` renders the log list using a safe HTML-escape helper (`esc()`) to prevent XSS in log content.

**3. Template picker** — IIFE that:
- Listens for clicks on `.template-card` elements
- Shows the actions bar with the selected template name
- On "Apply & Open Editor" click: confirms, POSTs to `/apply-template`, redirects on success
- `pageshow` event listener resets button state if page is restored from bfcache (browser back navigation)

**4. Delete service** — listens for `.btn-delete-service` clicks, confirms, POSTs to `/delete-service/...`, redirects to dashboard.

---

## 9. Auth Page Customization System

The auth gate page (`/auth/<owner>/<service>`) is fully customizable. Here is the complete picture of how it works:

### HTML structure of the auth page

```html
<body>
  <div class="page-wrapper">
    <div class="above-card"><!-- page_above_html --></div>
    <div class="card"><!-- auth form --></div>
    <div class="below-card"><!-- page_below_html --></div>
  </div>
</body>
```

### CSS layers (applied in order, later rules win)

1. `/static/style.css` — base styles (body, card defaults, form elements)
2. `<style>{{ page_css }}</style>` — style panel output (colors, layout, typography)
3. `<style>{{ page_extra_css }}</style>` — template-specific styles (header/panel/footer)

### What the style panel controls (`page_css`)

The panel exposes: `pageBg`, `pageAlign`, `pageLayout`, `cardBg`, `cardBorder`, `cardRadius`, `headingColor`, `labelColor`, `inputColor`, `inputBg`, `inputBorder`, `btnBg`, `btnColor`, `btnRadius`.

These are stored as JSON in `page_style_data` and rebuilt into CSS by `buildCss()` (JS) or `build_css_from_style_data()` (Python) every time the page is saved.

### Layout modes

**Column layout** (`pageLayout: "column"`):
```css
.page-wrapper { flex-direction: column; align-items: center; justify-content: <pageAlign>; }
.above-card, .below-card { width: 100%; max-width: 500px; }
```

**Row layout** (`pageLayout: "row"`):
```css
.page-wrapper { flex-direction: row; align-items: stretch; }
.above-card { flex: 1; max-width: none; }
.below-card { flex: 1; max-width: none; }
.card { align-self: center; margin: 0 5%; flex-shrink: 0; }
```

Row layout is used by Templates 2 (left brand panel) and 4 (testimonial strip). `above-card` becomes the left column; `below-card` becomes the right column.

### GrapeJS editor

GrapeJS v0.21.13 is used as a drag-drop block container for `above-card` and `below-card`. The style manager is re-enabled for user-dragged blocks (but does not affect the auth card itself).

GrapeJS's own CSS generation is not used — `editor.getCss()` would produce output scoped to random GrapeJS-internal IDs, not to the `.page-wrapper` / `.card` selectors needed for the live auth page. Instead:
- `buildCss()` generates all `page_css` from the style panel
- Only `editor.getHtml()` is used from GrapeJS (for `above_html` and `below_html`)

### Why `page_extra_css` is a separate field

When a user applies a template, `page_extra_css` holds the template's visual styling (dark header backgrounds, column layouts, testimonial card borders, etc.). When the user then opens the editor and tweaks colors or saves, `save-page` only updates `page_css`, `page_above_html`, `page_below_html`, and `page_style_data`. It never touches `page_extra_css`. This means template styles survive editor sessions without needing to be re-applied.

---

## 10. Page Templates

All five templates are defined in `PAGE_TEMPLATES` in `main.py`. To add a new template:

1. Add a new entry to `PAGE_TEMPLATES` with a unique string key.
2. Write `above_html` and `below_html` using only CSS classes (no `style=""` attributes).
3. Write all element styles in `extra_css` using unique class names (prefix with `tpl-<shortname>-` to avoid collisions).
4. Fill in `style_data` with the color palette the template expects.
5. Set `layout` to `"column"` or `"row"`.
6. Add thumbnail preview styles for `.tpl-thumb--<your-key>` in `service_detail.css`.
7. Add any special inner markup for the thumbnail in `service_detail.html`'s `{% for tid, tpl in templates.items() %}` block.

No route changes are needed — `apply_template` reads from `PAGE_TEMPLATES` dynamically.

---

## 11. CI/CD Pipeline

File: `.github/workflows/master_customauthservice.yml`

Trigger: push to `master` branch (or manual `workflow_dispatch`).

**Build job** (ubuntu-latest):
1. Checkout repo
2. Set up Python 3.12
3. Create venv `antenv`, install `requirements.txt`
4. Upload artifact (excluding `antenv/`)

**Deploy job** (ubuntu-latest, needs build):
1. Download artifact
2. Deploy to Azure App Service (`CustomAuthService`, Production slot) using `azure/webapps-deploy@v3`

The Azure App Service runs Oryx on the uploaded artifact, installs dependencies from `requirements.txt`, and serves the app with Gunicorn.

The deployment publish profile is stored as a GitHub secret: `AZUREAPPSERVICE_PUBLISHPROFILE_19467FB31C8D456589AC3D0191502AAF`.

---

## 12. Contributing

### Local setup

```bash
git clone https://github.com/AvikYadav/CustomAuth
cd CustomAuth
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in the project root:
```
mongo_url=mongodb+srv://<username>:<password>@cluster.xxxxx.mongodb.net/
```

Run:
```bash
python main.py
```

Visit `http://127.0.0.1:5000`.

### Branch strategy

- `master` — production branch, triggers Azure deploy on push
- `UiUpgrade` — active development branch
- PRs should target `master`

### Adding a route

1. Add the route function in `main.py`, grouped with its logical section (dashboard, auth gate, data API, etc.)
2. If it requires authentication, call `require_auth()` first
3. If it writes HTML from user input, run it through `sanitize_html()`
4. If it writes CSS from user input, run it through `sanitize_css()`
5. Return JSON from API routes using `api_response()`

### Adding a database operation

Add functions to `database.py`. Follow the existing pattern:
- First arg is always `db`
- Use `get_user_collection(db, username)` to get the collection
- Use MongoDB `$set` with dot-notation to update nested fields without overwriting siblings
- Return `None` or `False` on not-found; return the document or `True` on success

### Frontend conventions

- No inline event handlers. All JS attaches via `addEventListener`. This is required for the CSP (`script-src 'self'`).
- No inline `<script>` tags in templates. All JS lives in `/static/`.
- Use `esc()` (defined in `service_detail.js`) when rendering user-supplied content into the DOM via JS — this prevents XSS in dynamically rendered log entries and other AJAX content.

---

## 13. Known Gotchas & Design Decisions

### JWT secret resets on every restart

`jwt_token.py` generates `JWT_SECRET_KEY = secrets.token_hex(35)` at import time. Every server restart invalidates all active sessions and all service user tokens stored in the DB. For production, load from env:

```python
# jwt_token.py
import os
JWT_SECRET_KEY = os.getenv("JWT_SECRET") or secrets.token_hex(35)
```

```
# .env
JWT_SECRET=your-stable-secret-here
```

### bleach HTML-encodes single quotes in `style=""` attributes

`bleach.clean()` uses html5lib, which parses and re-serializes HTML. During re-serialization, single quotes inside attribute values are HTML-encoded. This means `style="font-family:'DM Mono'"` becomes `style="font-family:&#x27;DM Mono&#x27;"`, which browsers treat as literal text — not a font name — causing CSS to silently fail.

**Workaround in place**: All template HTML uses CSS classes. Template styling goes in `extra_css`, which is stored in `page_extra_css` and passes through `sanitize_css()` (regex-only, no HTML parsing). Class attributes on elements survive bleach without modification.

**If you add template HTML**: Never use `style=""` attributes. Always write a CSS class and put the rule in `extra_css`.

### `update_service` only updates keys you provide

`database.update_service(db, username, service_name, { "page_css": ... })` uses `$set` with dot-notation keys. It only touches `data.page_css`. Every other field in `data` is left exactly as it was. This is how `page_extra_css` survives `save-page` calls — the save route simply doesn't include it in its `update_service` call.

### GrapeJS CSS is bypassed entirely

GrapeJS v0.21.13's `editor.getCss()` scopes generated CSS to internal random IDs (like `#iqfg`). These IDs only exist inside the GrapeJS canvas and don't match any element on the real auth page. To avoid this, all CSS for the auth page is generated by the custom `buildCss()` function using correct class selectors (`.page-wrapper`, `.card`, etc.). GrapeJS is only used to provide `above_html` and `below_html` via `editor.getHtml()`.

### `secure=True` on cookies blocks local dev

Session cookies are set with `secure=True`. In local development over `http://`, the browser will silently drop the cookie and you will be redirected to the signup page on every request. To develop locally, temporarily set `secure=False` in the two `set_cookie` calls in `main.py` (`/signup` and `/login` routes). Do not commit this change.

### Service users vs platform users

There are two completely separate user populations:

- **Platform users (owners)**: registered at `easyauth.dev`, have their own collection, can create services. Authenticated via the `auth_token` JWT cookie.
- **Service users (end users)**: registered through `/auth/<owner>/<service>`, stored in the `users` array inside a service document. Authenticated by their own JWT, which is Fernet-encrypted before delivery. They never interact with the platform dashboard.

The auth gate (`/auth/`) and data API (`/retrieve/`, `/update/`, `/verify/`) are for service users. The dashboard routes (`/dashboard/`) are for platform owners. Never mix the two.

### `page_style_data` is stored as a JSON string

The `page_style_data` field is stored as `json.dumps(dict)` — a string, not a BSON subdocument. This is because the editor reads it back as a string and calls `JSON.parse()` in JS. Consistency was preferred over elegance. When reading it in Python, use `json.loads(style_data)`.

### Flask `SECRET_KEY` is ephemeral

`app.config['SECRET_KEY'] = secrets.token_hex(32)` is regenerated on every restart. The only thing this key protects is Flask's flash messages (used to display the API key once after service creation). Since flash messages are transient and tied to the current session, losing them on restart is acceptable. For production, store a stable key in `.env` anyway.
