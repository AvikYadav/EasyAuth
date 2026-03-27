import bcrypt
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, flash
from datetime import datetime, timezone
from urllib.parse import quote
import secrets
import database
import jwt_token
import encryption
import logger

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)

# ── Database connection ──────────────────────────────────────────────────────

db = database.connect_to_database()

# Note: Security headers (CSP, HSTS, X-Frame-Options) are applied in the
# deployment environment (reverse proxy / CDN) rather than in app code.


# ── Helpers ──────────────────────────────────────────────────────────────────

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
                           stats=stats, logs=logs)


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


# ── Routes: Service Auth Gate (third-party apps) ─────────────────────────────

@app.route("/auth/<user>/<service>", methods=["GET", "POST"])
def auth(user, service):
    """
    Third-party auth gate — renders signup/login UI for service users.
    On success, redirects to the service's callback URL with a Fernet-encrypted token.
    """
    if request.method == "GET":
        return render_template("auth.html", user=user, service=service, mode="signup")

    # Extract form fields
    submitted_username = request.form.get("username", "").strip()
    submitted_password = request.form.get("password", "")
    mode               = request.form.get("mode")
    is_signup          = (mode == "signup")
    email              = request.form.get("email", "").strip().lower()
    ip                 = get_client_ip()

    def render_error(msg):
        return render_template("auth.html", user=user, service=service,
                               mode=mode, error=msg, username=submitted_username)

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