import bcrypt
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, flash
from datetime import datetime, timezone
from urllib.parse import quote
import secrets
import database
import jwt_token
import encryption
import logger
from sanitize import sanitize_html, sanitize_css

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)

# ── Page Templates ───────────────────────────────────────────────────────────

PAGE_TEMPLATES = {
    # ── Template 1: Marketing Site Header + Minimal Footer ─────────────────
    "marketing-header": {
        "name": "Marketing Site Header",
        "description": "Fixed dark header with logo & nav, minimal footer.",
        "layout": "column",
        "above_html": (
            '<header class="tpl-mh-header">'
            '<span class="tpl-mh-brand">BRAND</span>'
            '<nav class="tpl-mh-nav">'
            '<a href="#">Features</a><a href="#">Pricing</a><a href="#">Docs</a>'
            '</nav></header>'
            '<div class="tpl-mh-spacer"></div>'
        ),
        "below_html": (
            '<footer class="tpl-mh-footer">'
            '<span class="tpl-mh-copy">&copy; 2026 Brand Inc.</span>'
            '<div class="tpl-mh-links">'
            '<a href="#">Privacy</a><a href="#">Terms</a>'
            '</div></footer>'
        ),
        "extra_css": (
            ".tpl-mh-header{width:100%;background:#111110;padding:0 40px;display:flex;"
            "align-items:center;justify-content:space-between;height:60px;"
            "position:fixed;top:0;left:0;right:0;z-index:100;}"
            ".tpl-mh-brand{color:#fff;font-size:14px;font-weight:500;letter-spacing:0.1em;}"
            ".tpl-mh-nav{display:flex;gap:24px;}"
            ".tpl-mh-nav a{color:rgba(255,255,255,0.7);font-size:13px;text-decoration:none;}"
            ".tpl-mh-spacer{height:60px;width:100%;display:block;}"
            ".tpl-mh-footer{width:100%;padding:24px 40px;border-top:1px solid #e2e1da;"
            "display:flex;align-items:center;justify-content:space-between;margin-top:40px;}"
            ".tpl-mh-copy{font-size:11px;color:#888884;}"
            ".tpl-mh-links{display:flex;gap:20px;}"
            ".tpl-mh-links a{font-size:12px;color:#888884;text-decoration:none;}"
        ),
        "style_data": {
            "pageBg": "#f7f6f2", "pageAlign": "center", "pageLayout": "column",
            "cardBg": "#ffffff", "cardBorder": "#e2e1da", "cardRadius": "12",
            "headingColor": "#111110", "labelColor": "#888884",
            "inputColor": "#111110", "inputBg": "#f7f6f2", "inputBorder": "#e2e1da",
            "btnBg": "#111110", "btnColor": "#ffffff", "btnRadius": "6",
        },
    },

    # ── Template 2: Left Branding Panel + Right-Anchored Card ───────────────
    "left-brand-panel": {
        "name": "Left Branding Panel",
        "description": "Row layout: dark brand panel on left, auth card on right.",
        "layout": "row",
        "above_html": (
            '<div class="tpl-lbp">'
            '<div class="tpl-lbp-logo">B</div>'
            '<h2 class="tpl-lbp-heading">Build something great.</h2>'
            '<p class="tpl-lbp-sub">The fastest way to add secure auth to your product.</p>'
            '<ul class="tpl-lbp-list">'
            '<li>JWT-based token auth</li>'
            '<li>Custom branding &amp; theming</li>'
            '<li>Real-time event logs</li>'
            '</ul></div>'
        ),
        "below_html": "",
        "extra_css": (
            ".tpl-lbp{display:flex;flex-direction:column;justify-content:center;"
            "padding:60px 48px;background:linear-gradient(160deg,#0f172a 0%,#1e3a5f 100%);"
            "min-height:100vh;flex:1;}"
            ".tpl-lbp-logo{width:48px;height:48px;background:#fff;border-radius:12px;"
            "display:flex;align-items:center;justify-content:center;"
            "margin-bottom:32px;font-size:22px;font-weight:700;color:#0f172a;}"
            ".tpl-lbp-heading{color:#fff;font-size:28px;font-weight:600;"
            "letter-spacing:-0.02em;margin-bottom:12px;}"
            ".tpl-lbp-sub{color:rgba(255,255,255,0.65);font-size:15px;line-height:1.6;"
            "margin-bottom:40px;max-width:340px;}"
            ".tpl-lbp-list{list-style:none;padding:0;margin:0;display:flex;"
            "flex-direction:column;gap:14px;}"
            ".tpl-lbp-list li{color:rgba(255,255,255,0.8);font-size:14px;"
            "padding-left:28px;position:relative;}"
            ".tpl-lbp-list li::before{content:'\\2713';position:absolute;left:0;"
            "width:20px;height:20px;background:rgba(255,255,255,0.15);"
            "border-radius:50%;display:flex;align-items:center;justify-content:center;"
            "font-size:11px;top:50%;transform:translateY(-50%);}"
        ),
        "style_data": {
            "pageBg": "#f8fafc", "pageAlign": "center", "pageLayout": "row",
            "cardBg": "#ffffff", "cardBorder": "#e2e8f0", "cardRadius": "0",
            "headingColor": "#0f172a", "labelColor": "#64748b",
            "inputColor": "#0f172a", "inputBg": "#f8fafc", "inputBorder": "#e2e8f0",
            "btnBg": "#0f172a", "btnColor": "#ffffff", "btnRadius": "8",
        },
    },

    # ── Template 3: Announcement Banner + Centered Card + Footer ───────────
    "announcement-banner": {
        "name": "Announcement Banner + Footer",
        "description": "Slim banner at top, centered card, three-column footer.",
        "layout": "column",
        "above_html": (
            '<div class="tpl-ab-bar">'
            '<span class="tpl-ab-text">&#127881; Now in public beta &mdash; '
            '<a href="#" class="tpl-ab-link">Sign up free &rarr;</a></span>'
            '</div>'
        ),
        "below_html": (
            '<footer class="tpl-ab-footer">'
            '<div><div class="tpl-ab-col-title">Product</div>'
            '<a href="#">Features</a><a href="#">Pricing</a><a href="#">Changelog</a></div>'
            '<div><div class="tpl-ab-col-title">Company</div>'
            '<a href="#">About</a><a href="#">Blog</a></div>'
            '<div><div class="tpl-ab-col-title">Legal</div>'
            '<a href="#">Privacy</a><a href="#">Terms</a></div>'
            '</footer>'
        ),
        "extra_css": (
            ".tpl-ab-bar{width:100%;background:#111110;padding:10px 20px;"
            "display:flex;align-items:center;justify-content:center;}"
            ".tpl-ab-text{color:#fff;font-size:13px;}"
            ".tpl-ab-link{color:#93c5fd;text-decoration:none;font-weight:500;}"
            ".tpl-ab-footer{width:100%;max-width:900px;margin-top:48px;"
            "padding:32px 24px 0;border-top:1px solid #e2e1da;"
            "display:grid;grid-template-columns:repeat(3,1fr);gap:24px;}"
            ".tpl-ab-col-title{font-size:11px;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#888884;margin-bottom:12px;}"
            ".tpl-ab-footer a{display:block;font-size:13px;color:#111110;"
            "text-decoration:none;margin-bottom:8px;}"
        ),
        "style_data": {
            "pageBg": "#ffffff", "pageAlign": "flex-start", "pageLayout": "column",
            "cardBg": "#ffffff", "cardBorder": "#e2e1da", "cardRadius": "16",
            "headingColor": "#111110", "labelColor": "#888884",
            "inputColor": "#111110", "inputBg": "#f7f6f2", "inputBorder": "#e2e1da",
            "btnBg": "#111110", "btnColor": "#ffffff", "btnRadius": "8",
        },
    },

    # ── Template 4: Top-Left Logo + Testimonial Strip ───────────────────────
    "testimonial-strip": {
        "name": "Top-Left Logo + Testimonials",
        "description": "Row layout: auth card on left, testimonial column on right.",
        "layout": "row",
        "above_html": "",
        "below_html": (
            '<div class="tpl-ts">'
            '<div class="tpl-ts-title">What people say</div>'
            '<div class="tpl-ts-card">'
            '<p class="tpl-ts-quote">&#8220;The simplest auth setup I&#8217;ve ever used. '
            'Our team was up in 20 minutes.&#8221;</p>'
            '<div class="tpl-ts-author">'
            '<div class="tpl-ts-av tpl-ts-av1"></div>'
            '<div><div class="tpl-ts-name">Sarah K.</div>'
            '<div class="tpl-ts-role">CTO at Acme Co.</div></div>'
            '</div></div>'
            '<div class="tpl-ts-card">'
            '<p class="tpl-ts-quote">&#8220;Finally an auth solution that doesn&#8217;t '
            'require a PhD to configure.&#8221;</p>'
            '<div class="tpl-ts-author">'
            '<div class="tpl-ts-av tpl-ts-av2"></div>'
            '<div><div class="tpl-ts-name">Marcus T.</div>'
            '<div class="tpl-ts-role">Founder at Launchpad</div></div>'
            '</div></div>'
            '</div>'
        ),
        "extra_css": (
            ".tpl-ts{display:flex;flex-direction:column;justify-content:center;"
            "padding:60px 48px;background:#fafaf9;border-left:1px solid #e2e1da;"
            "min-height:100vh;flex:1;gap:24px;}"
            ".tpl-ts-title{font-size:11px;text-transform:uppercase;"
            "letter-spacing:0.1em;color:#888884;}"
            ".tpl-ts-card{background:#fff;border:1px solid #e2e1da;"
            "border-radius:12px;padding:24px;}"
            ".tpl-ts-quote{font-size:14px;color:#111110;line-height:1.6;margin-bottom:16px;}"
            ".tpl-ts-author{display:flex;align-items:center;gap:10px;}"
            ".tpl-ts-av{width:32px;height:32px;border-radius:50%;flex-shrink:0;}"
            ".tpl-ts-av1{background:#111110;}.tpl-ts-av2{background:#374151;}"
            ".tpl-ts-name{font-size:13px;font-weight:500;color:#111110;}"
            ".tpl-ts-role{font-size:12px;color:#888884;}"
        ),
        "style_data": {
            "pageBg": "#fafaf9", "pageAlign": "center", "pageLayout": "row",
            "cardBg": "#ffffff", "cardBorder": "#e2e1da", "cardRadius": "0",
            "headingColor": "#111110", "labelColor": "#888884",
            "inputColor": "#111110", "inputBg": "#f7f6f2", "inputBorder": "#e2e1da",
            "btnBg": "#111110", "btnColor": "#ffffff", "btnRadius": "6",
        },
    },

    # ── Template 5: Stepped Onboarding Shell ───────────────────────────────
    "stepped-onboarding": {
        "name": "Stepped Onboarding",
        "description": "Progress bar and step indicator above the card.",
        "layout": "column",
        "above_html": (
            '<div class="tpl-so-top">'
            '<div class="tpl-so-labels">'
            '<span class="tpl-so-count">Step 1 of 3</span>'
            '<span class="tpl-so-step-name">Account Setup</span>'
            '</div>'
            '<div class="tpl-so-bar"><div class="tpl-so-fill"></div></div>'
            '</div>'
        ),
        "below_html": (
            '<div class="tpl-so-dots">'
            '<div class="tpl-so-dot tpl-so-dot-on"></div>'
            '<div class="tpl-so-dot"></div>'
            '<div class="tpl-so-dot"></div>'
            '</div>'
            '<p class="tpl-so-note">Already have an account? '
            '<a href="#" class="tpl-so-link">Log in</a></p>'
        ),
        "extra_css": (
            ".tpl-so-top{width:100%;max-width:500px;margin-bottom:24px;}"
            ".tpl-so-labels{display:flex;align-items:center;"
            "justify-content:space-between;margin-bottom:10px;}"
            ".tpl-so-count{font-size:11px;text-transform:uppercase;"
            "letter-spacing:0.08em;color:#888884;}"
            ".tpl-so-step-name{font-size:12px;color:#888884;}"
            ".tpl-so-bar{width:100%;height:4px;background:#e2e1da;"
            "border-radius:99px;overflow:hidden;}"
            ".tpl-so-fill{width:33%;height:100%;background:#111110;border-radius:99px;}"
            ".tpl-so-dots{width:100%;max-width:500px;margin-top:20px;"
            "display:flex;justify-content:center;gap:6px;}"
            ".tpl-so-dot{width:8px;height:8px;border-radius:50%;background:#e2e1da;}"
            ".tpl-so-dot-on{background:#111110;}"
            ".tpl-so-note{text-align:center;font-size:13px;color:#888884;margin-top:16px;}"
            ".tpl-so-link{color:#111110;font-weight:500;text-decoration:none;}"
        ),
        "style_data": {
            "pageBg": "#f7f6f2", "pageAlign": "center", "pageLayout": "column",
            "cardBg": "#ffffff", "cardBorder": "#e2e1da", "cardRadius": "12",
            "headingColor": "#111110", "labelColor": "#888884",
            "inputColor": "#111110", "inputBg": "#f7f6f2", "inputBorder": "#e2e1da",
            "btnBg": "#111110", "btnColor": "#ffffff", "btnRadius": "6",
        },
    },
}

# ── Database connection ──────────────────────────────────────────────────────

db = database.connect_to_database()

# Note: Security headers (CSP, HSTS, X-Frame-Options) are applied in the
# deployment environment (reverse proxy / CDN) rather than in app code.


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_css_from_style_data(s: dict) -> str:
    """Mirror of buildCss() in auth_editor.html — generates page CSS from style dict."""
    page_bg      = s.get("pageBg",       "#f7f6f2")
    page_align   = s.get("pageAlign",    "center")
    page_layout  = s.get("pageLayout",   "column")
    card_bg      = s.get("cardBg",       "#ffffff")
    card_border  = s.get("cardBorder",   "#e2e1da")
    card_radius  = s.get("cardRadius",   "12")
    heading      = s.get("headingColor", "#111110")
    label        = s.get("labelColor",   "#888884")
    input_color  = s.get("inputColor",   "#111110")
    input_bg     = s.get("inputBg",      "#f7f6f2")
    input_border = s.get("inputBorder",  "#e2e1da")
    btn_bg       = s.get("btnBg",        "#111110")
    btn_color    = s.get("btnColor",     "#ffffff")
    btn_radius   = s.get("btnRadius",    "6")

    if page_layout == "row":
        layout_css = (
            f".page-wrapper {{ flex-direction: row; align-items: stretch; }}\n"
            f".above-card {{ flex: 1; max-width: none; }}\n"
            f".below-card {{ flex: 1; max-width: none; }}\n"
            f".card {{ align-self: center; margin: 0 5%; flex-shrink: 0; }}\n"
        )
    else:
        layout_css = (
            f".page-wrapper {{ flex-direction: column; align-items: center; justify-content: {page_align}; }}\n"
            f".above-card, .below-card {{ width: 100%; max-width: 500px; }}\n"
        )

    return (
        f"html, body {{ background-color: {page_bg}; margin: 0; padding: 0; }}\n"
        f".page-wrapper {{ background-color: {page_bg}; }}\n"
        + layout_css
        + f".card {{ background-color: {card_bg}; border-color: {card_border}; border-radius: {card_radius}px; }}\n"
        f".card h1 {{ color: {heading}; }}\n"
        f".field label {{ color: {label}; }}\n"
        f".field input {{ color: {input_color}; background-color: {input_bg}; border-color: {input_border}; }}\n"
        f".card .btn {{ background-color: {btn_bg}; color: {btn_color}; border-radius: {btn_radius}px; }}\n"
        f".tabs {{ border-color: {card_border}; }}\n"
        f".tab.active {{ background-color: {btn_bg}; color: {btn_color}; }}\n"
        f".wordmark {{ color: {label}; }}\n"
        f".powered-by {{ color: {label}; }}\n"
    )


def hash_password(password):
    """Hash a plaintext password with bcrypt (cost factor 12)."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(stored_hash, provided_password):
    """Constant-time comparison of a bcrypt hash against a plaintext password."""
    return bcrypt.checkpw(
        provided_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    )


def api_response(data=None, error=None, status_code=200):
    """
    Uniform JSON response wrapper for all API endpoints.
    Success: {"status": "success", "data": {...}}
    Error:   {"status": "error", "message": "..."}
    """
    if error:
        return jsonify({"status": "error", "message": error}), status_code
    return jsonify({"status": "success", "data": data}), status_code


def get_client_ip():
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def require_auth():
    """
    Validate the auth_token cookie and return the JWT payload.
    Returns (payload, None) on success, (None, error_response) on failure.
    """
    token = request.cookies.get("auth_token")
    if not token:
        return None, (render_template("signup.html", error="Login required"), 400)
    payload = jwt_token.verify_token(token)
    if not payload:
        return None, (render_template("signup.html", error="Session expired"), 400)
    return payload, None


# ── Jinja template filters ──────────────────────────────────────────────────

@app.template_filter("timeago")
def timeago_filter(dt):
    """Convert a datetime to a human-readable relative string (e.g. '5m ago')."""
    if dt is None:
        return "never"
    if isinstance(dt, str):
        return dt
    # MongoDB returns naive datetimes in UTC — make them aware before comparing
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes / 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours / 24)
    return f"{days}d ago"


@app.template_filter("fmt_time")
def format_time_filter(dt):
    """Format a datetime for display. Handles both datetime objects and strings."""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ── Routes: Platform Auth ────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Landing page — renders the signup/login form."""
    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup():
    """Register a new platform account with username, email, and password."""
    username = request.form.get("username", "").strip()
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm",  "")

    def render_error(msg):
        return render_template("signup.html", error=msg,
                               username=username, email=email), 400

    if not all([username, email, password, confirm]):
        return render_error("All fields are required.")
    if password != confirm:
        return render_error("Passwords do not match.")
    if len(password) < 8:
        return render_error("Password must be at least 8 characters.")

    password_hash = hash_password(password)
    user = database.create_user_profile(db, username, {
        "email":         email.lower(),
        "password_hash": password_hash,
        "is_verified":   False,
    })

    if user is None:
        return render_error("Username already taken.")

    # Issue session token and set secure cookie
    token = jwt_token.generate_token(username)
    response = redirect("/dashboard")
    response.set_cookie(
        "auth_token", token,
        httponly=True,      # invisible to JavaScript
        secure=True,        # only sent over HTTPS
        samesite="Strict",  # blocks cross-site requests (CSRF prevention)
        max_age=3600,
        path="/"
    )
    return response


@app.route("/login", methods=["POST"])
def login():
    """Authenticate an existing platform user with username and password."""
    submitted_username = request.form.get("username", "").strip()
    submitted_password = request.form.get("password", "")

    def render_error(msg):
        return render_template("signup.html", mode="login",
                               error=msg, username=submitted_username)

    if not submitted_username or not submitted_password:
        return render_error("Username and password are required.")

    user_profile = database.get_user_profile(db, submitted_username)
    if user_profile is None:
        return render_error("No account found with that username.")

    if not verify_password(user_profile["data"]["password_hash"], submitted_password):
        return render_error("Invalid credentials.")

    token = jwt_token.generate_token(submitted_username)
    response = redirect("/dashboard")
    response.set_cookie(
        "auth_token", token,
        httponly=True,
        secure=True,
        samesite="Strict",
        max_age=3600,
        path="/"
    )
    return response


@app.route("/logout")
def logout():
    """Clear the session cookie and redirect to landing page."""
    response = redirect("/")
    response.set_cookie("auth_token", "", expires=0, path="/")
    return response


# ── Routes: Dashboard ────────────────────────────────────────────────────────

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Main dashboard — lists all services with summary metrics."""
    payload, err = require_auth()
    if err:
        return err

    username = payload["sub"]
    services = database.get_all_services(db, username)

    # Attach summary stats to each service card
    for svc in services:
        svc.pop("_id", None)
        svc["stats"] = database.get_service_stats(db, username, svc["service_name"])

    return render_template("dashboard.html", username=username, services=services)


@app.route("/dashboard/create-service", methods=["POST"])
def create_service():
    """Register a new service — generates a Fernet API key shown once."""
    payload, err = require_auth()
    if err:
        return err

    username     = payload["sub"]
    service_name = request.form.get("service_name", "").strip()
    callback_url = request.form.get("callback_url", "").strip()
    key = encryption.generate_key()

    database.create_service(db, username, service_name, {
        "api_key":      key,
        "callback_url": callback_url,
    }, [])

    flash(key, "api_key")
    return redirect("/dashboard")


@app.route("/dashboard/delete-service/<service_name>", methods=["POST"])
def delete_service_route(service_name):
    """Delete a service and all its associated user data."""
    payload, err = require_auth()
    if err:
        return err

    username = payload["sub"]
    database.delete_service(db, username, service_name)
    return "", 200


@app.route("/dashboard/edit-service", methods=["POST"])
def edit_service():
    """Update a service's callback URL."""
    payload, err = require_auth()
    if err:
        return err

    username     = payload["sub"]
    service_name = request.form.get("service_name", "").strip()
    callback_url = request.form.get("callback_url", "").strip()
    database.update_service(db, username, service_name, {"callback_url": callback_url})
    return redirect("/dashboard")


# ── Routes: Service Detail ───────────────────────────────────────────────────

@app.route("/dashboard/service/<service_name>")
def service_detail(service_name):
    """Service detail page — overview stats, logs viewer, and settings."""
    payload, err = require_auth()
    if err:
        return err

    username = payload["sub"]
    service  = database.get_service(db, username, service_name)
    if not service:
        return redirect("/dashboard")

    service.pop("_id", None)
    stats = database.get_service_stats(db, username, service_name)
    logs  = database.get_logs(db, username, service_name, limit=50)

    return render_template("service_detail.html",
                           username=username, service=service,
                           stats=stats, logs=logs,
                           templates=PAGE_TEMPLATES)


@app.route("/dashboard/service/<service_name>/logs")
def service_logs_api(service_name):
    """JSON endpoint — returns filtered logs for AJAX requests in the logs tab."""
    payload, err = require_auth()
    if err:
        return api_response(error="Authentication required.", status_code=401)

    username = payload["sub"]

    # Read optional filter params from query string
    event   = request.args.get("event")
    status  = request.args.get("status")
    user_id = request.args.get("user_id")
    limit   = min(int(request.args.get("limit", 100)), 500)
    skip    = int(request.args.get("skip", 0))

    logs = database.get_logs(db, username, service_name,
                             event=event, status=status,
                             user_id=user_id, limit=limit, skip=skip)
    return api_response(data={"logs": logs})


# ── Routes: Auth Page Builder ────────────────────────────────────────────────

@app.route("/dashboard/service/<service_name>/edit-page")
def edit_auth_page(service_name):
    """GrapeJS editor for customizing the auth page appearance."""
    payload, err = require_auth()
    if err:
        return err

    username = payload["sub"]
    service = database.get_service(db, username, service_name)
    if not service:
        return redirect("/dashboard")

    service_data = service.get("data", {})
    return render_template("auth_editor.html",
                           username=username,
                           service_name=service_name,
                           page_above_html=service_data.get("page_above_html", ""),
                           page_below_html=service_data.get("page_below_html", ""),
                           page_css=service_data.get("page_css", ""),
                           page_style_data=service_data.get("page_style_data", ""))


@app.route("/dashboard/service/<service_name>/save-page", methods=["POST"])
def save_auth_page(service_name):
    """Save customized auth page HTML and CSS."""
    payload, err = require_auth()
    if err:
        return jsonify({"ok": False, "error": "Auth required"}), 401

    username = payload["sub"]
    service = database.get_service(db, username, service_name)
    if not service:
        return jsonify({"ok": False, "error": "Service not found"}), 404

    data = request.get_json()
    above_html = sanitize_html(data.get("above_html", ""))
    below_html = sanitize_html(data.get("below_html", ""))
    page_css = sanitize_css(data.get("css", ""))
    style_data = data.get("style_data", "")

    database.update_service(db, username, service_name, {
        "page_above_html": above_html,
        "page_below_html": below_html,
        "page_css":        page_css,
        "page_style_data": style_data,
        "page_layout":     (json.loads(style_data).get("pageLayout", "column") if style_data else "column"),
    })

    return jsonify({"ok": True})


@app.route("/dashboard/service/<service_name>/apply-template", methods=["POST"])
def apply_template(service_name):
    """Apply a pre-defined page template to the service."""
    payload, err = require_auth()
    if err:
        return jsonify({"ok": False, "error": "Auth required"}), 401

    username = payload["sub"]
    service = database.get_service(db, username, service_name)
    if not service:
        return jsonify({"ok": False, "error": "Service not found"}), 404

    data = request.get_json(silent=True) or {}
    template_id = data.get("template_id", "")
    if template_id not in PAGE_TEMPLATES:
        return jsonify({"ok": False, "error": "Unknown template"}), 400

    tpl = PAGE_TEMPLATES[template_id]
    css = build_css_from_style_data(tpl["style_data"])

    database.update_service(db, username, service_name, {
        "page_above_html": sanitize_html(tpl["above_html"]),
        "page_below_html": sanitize_html(tpl["below_html"]),
        "page_css":        sanitize_css(css),
        "page_extra_css":  sanitize_css(tpl.get("extra_css", "")),
        "page_style_data": json.dumps(tpl["style_data"]),
        "page_layout":     tpl["layout"],
    })

    return jsonify({"ok": True, "redirect": f"/dashboard/service/{service_name}/edit-page"})


# ── Routes: Service Auth Gate (third-party apps) ─────────────────────────────

@app.route("/auth/<user>/<service>", methods=["GET", "POST"])
def auth(user, service):
    """
    Third-party auth gate — renders signup/login UI for service users.
    On success, redirects to the service's callback URL with a Fernet-encrypted token.
    """
    # Fetch custom page builder data for this service
    service_doc = database.service_get_service_document(db, user, service)
    svc_data = service_doc.get("data", {}) if service_doc else {}
    page_vars = {
        "page_above_html": svc_data.get("page_above_html", ""),
        "page_below_html": svc_data.get("page_below_html", ""),
        "page_css":        svc_data.get("page_css", ""),
        "page_extra_css":  svc_data.get("page_extra_css", ""),
    }

    if request.method == "GET":
        return render_template("auth.html", user=user, service=service,
                               mode="signup", **page_vars)

    # Extract form fields
    submitted_username = request.form.get("username", "").strip()
    submitted_password = request.form.get("password", "")
    mode               = request.form.get("mode")
    is_signup          = (mode == "signup")
    email              = request.form.get("email", "").strip().lower()
    ip                 = get_client_ip()

    def render_error(msg):
        return render_template("auth.html", user=user, service=service,
                               mode=mode, error=msg, username=submitted_username,
                               **page_vars)

    if not submitted_username or not submitted_password:
        return render_error("Username and password are required.")

    # Fetch the service document from the owner's collection
    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return render_error(f"Service '{service}' not found.")

    users_list   = service_doc.get("users", [])
    service_data = service_doc.get("data", {})
    existing_user = next((u for u in users_list if u["username"] == submitted_username), None)

    # ── Signup: create new service user ──────────────────────────────────────
    if existing_user is None and is_signup:
        token     = jwt_token.generate_token(submitted_username)
        token_enc = encryption.encrypt_message(token, service_data["api_key"])
        new_entry = database.service_create_user_entry(
            submitted_username, hash_password(submitted_password), email, token
        )
        database.service_add_user_to_service(db, user, service, new_entry)

        # Log signup + token issued
        logger.log_event(db, user, service, logger.SIGNUP_SUCCESS, "success",
                         user_id=submitted_username, ip=ip)
        logger.log_event(db, user, service, logger.TOKEN_ISSUED, "success",
                         user_id=submitted_username, ip=ip)

        return redirect(f"{service_data['callback_url']}?token={quote(token_enc, safe='')}")

    # ── Login: user not found ────────────────────────────────────────────────
    if existing_user is None and not is_signup:
        logger.log_event(db, user, service, logger.LOGIN_FAIL, "failure",
                         user_id=submitted_username, ip=ip,
                         error_message="User not found")
        return render_error("No user with that username found.")

    # ── Signup: username already taken ───────────────────────────────────────
    if existing_user and is_signup:
        logger.log_event(db, user, service, logger.SIGNUP_FAIL, "failure",
                         user_id=submitted_username, ip=ip,
                         error_message="Username already exists")
        return render_error("A user with that username already exists.")

    # ── Login: verify credentials ────────────────────────────────────────────
    if not verify_password(existing_user["password"], submitted_password):
        logger.log_event(db, user, service, logger.LOGIN_FAIL, "failure",
                         user_id=submitted_username, ip=ip,
                         error_message="Invalid credentials")
        return render_error("Invalid credentials.")

    new_token = jwt_token.generate_token(submitted_username)
    token_enc = encryption.encrypt_message(new_token, service_data["api_key"])
    database.service_update_user_jwt(db, user, service, submitted_username, new_token)

    # Log login + token issued
    logger.log_event(db, user, service, logger.LOGIN_SUCCESS, "success",
                     user_id=submitted_username, ip=ip)
    logger.log_event(db, user, service, logger.TOKEN_ISSUED, "success",
                     user_id=submitted_username, ip=ip)
    return redirect(f"{service_data['callback_url']}?token={quote(token_enc, safe='')}")


# ── Routes: Data API (JSON, for third-party backends) ────────────────────────

@app.route("/retrieve/<user>/<service>", methods=["POST"])
def retrieve_user_data(user, service):
    """Retrieve stored data for an authenticated service user."""
    data  = request.get_json(silent=True) or {}
    token = data.get("token")
    ip    = get_client_ip()

    if not token:
        return api_response(error="Token required.", status_code=401)

    payload = jwt_token.verify_token(token)
    if payload is None:
        logger.log_event(db, user, service, logger.TOKEN_VERIFY_FAIL, "failure",
                         ip=ip, error_message="Expired or invalid token")
        return api_response(error="Token expired or invalid.", status_code=401)

    username = payload["sub"]

    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return api_response(error=f"Service '{service}' not found.", status_code=404)

    users_list    = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)

    if user_database is None:
        return api_response(error="User not found in service.", status_code=404)

    # Log successful data read
    logger.log_event(db, user, service, logger.DATA_READ, "success",
                     user_id=username, ip=ip)

    return api_response(data={"username": username, "user_data": user_database["user_data"]})


@app.route("/update/<user>/<service>", methods=["POST"])
def update_user_data(user, service):
    """Write arbitrary JSON data for an authenticated service user."""
    data      = request.get_json(silent=True) or {}
    token     = data.get("token")
    user_data = data.get("user_data")
    ip        = get_client_ip()

    if not token:
        return api_response(error="Token required.", status_code=401)

    payload = jwt_token.verify_token(token)
    if payload is None:
        logger.log_event(db, user, service, logger.TOKEN_VERIFY_FAIL, "failure",
                         ip=ip, error_message="Expired or invalid token")
        return api_response(error="Token expired or invalid.", status_code=401)

    username = payload["sub"]

    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return api_response(error=f"Service '{service}' not found.", status_code=404)

    users_list    = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)

    if user_database is None:
        return api_response(error="User not found in service.", status_code=404)

    database.service_update_user_data(db, user, service, username, user_data)

    # Log successful data write
    logger.log_event(db, user, service, logger.DATA_WRITE, "success",
                     user_id=username, ip=ip)

    return api_response(data={"message": "User data updated."})


@app.route("/verify/<user>/<service>", methods=["POST"])
def verify_user_data(user, service):
    """Confirm whether a token is valid for a service user."""
    data  = request.get_json(silent=True) or {}
    token = data.get("token")
    ip    = get_client_ip()

    if not token:
        return api_response(error="Token required.", status_code=401)

    payload = jwt_token.verify_token(token)
    if payload is None:
        logger.log_event(db, user, service, logger.TOKEN_VERIFY_FAIL, "failure",
                         ip=ip, error_message="Expired or invalid token")
        return api_response(error="Token expired or invalid.", status_code=401)

    username = payload["sub"]

    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return api_response(error=f"Service '{service}' not found.", status_code=404)

    users_list    = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)

    if user_database is None:
        return api_response(error="User not found in service.", status_code=404)

    # Log successful token verification
    logger.log_event(db, user, service, logger.TOKEN_VERIFIED, "success",
                     user_id=username, ip=ip)

    return api_response(data={"message": "Token is valid.", "username": username})


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5050)





# fix logs in DB 
# connector discrepencies
# add customisation options