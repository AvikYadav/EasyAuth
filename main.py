import bcrypt
from flask import Flask, render_template, request, redirect, url_for,jsonify, make_response,flash
import secrets
import database
import jwt_token
import encryption
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(32)

# ── Database connection ────────────────────────────────────────────────────────


db = database.connect_to_database()

# --- SECURITY MIDDLEWARE ---
# @app.after_request
# def add_security_headers(response):
#     """Applies global security headers to every response."""
#     # Strict CSP: Only allow content from our own origin
#     csp = (
#         "default-src 'self'; "
#         "script-src 'self'; "
#         "object-src 'none'; "
#         "frame-ancestors 'none';"
#     )
#     response.headers['Content-Security-Policy'] = csp
#     response.headers['X-Content-Type-Options'] = 'nosniff'
#     response.headers['X-Frame-Options'] = 'DENY'
#     # Ensures the browser only uses HTTPS for the next year
#     response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
#     return response


# ── Routes ─────────────────────────────────────────────────────────────────────
# ── USER DASHBOARD ─────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template("signup.html")



@app.route("/signup", methods=["POST"])
def signup():
    #GET FORM FIELDS
    username = request.form.get("username", "").strip()
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm",  "")



    #BASIC ERROR HANDLING
    def render_error(msg):
        """Re-render the signup page with an error message and prefilled fields."""
        return render_template("signup.html", error=msg,
                               username=username, email=email), 400
    # Basic server-side checks
    if not all([username, email, password, confirm]):
        return render_error("All fields are required.")
    if password != confirm:
        return render_error("Passwords do not match.")
    if len(password) < 8:
        return render_error("Password must be at least 8 characters.")



    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    # Create the user's collection and profile document
    user = database.create_user_profile(db, username, {
        "email":         email.lower(),
        "password_hash": password_hash,
        "is_verified":   False,
    })

    if user is None:
        return render_error("Username already taken.")

    token = jwt_token.generate_token(username)

    response = redirect("/dashboard")

    # Secure Cookie Configuration
    response.set_cookie(
        "auth_token",
        token,
        httponly=True,  # Invisible to JavaScript
        secure=True,  # Only sent over HTTPS
        samesite='Strict',  # No CSRF: only sent if request starts from our domain
        max_age=3600,  # Expires in 1 hour
        path='/'  # Available across the whole site
    )
    return response

@app.route("/login", methods=["POST"])
def login():
    # 1. Extract and Validate Input
    submitted_username = request.form.get("username", "").strip()
    submitted_password = request.form.get("password", "")

    def render_error(msg):
        return render_template("signup.html", mode="login",
                               error=msg, username=submitted_username)

    if not submitted_username or not submitted_password:
        return render_error("Username and password are required.")

    # 2. Fetch User
    user_profile = database.get_user_profile(db, submitted_username)

    if user_profile is None:
        return render_error("No account found with that username.")

    # 3. Verify Password
    is_valid = verify_password(user_profile["data"]["password_hash"], submitted_password)

    if not is_valid:
        return render_error("Invalid credentials.")

    # 4. Generate Token and Return
    token = jwt_token.generate_token(submitted_username)

    response = redirect("/dashboard")

    # Secure Cookie Configuration
    response.set_cookie(
        "auth_token",
        token,
        httponly=True,  # Invisible to JavaScript
        secure=True,  # Only sent over HTTPS
        samesite='Strict',  # No CSRF: only sent if request starts from our domain
        max_age=3600,  # Expires in 1 hour
        path='/'  # Available across the whole site
    )

    return response


@app.route("/dashboard", methods=["GET","POST"])
def dashboard():

    def render_error(msg):
        """Re-render the signup page with an error message and prefilled fields."""
        return render_template("signup.html", error=msg,
                               ), 400

    token = request.cookies.get('auth_token')
    if token is None:
        return render_error("Login required")

    payload = jwt_token.verify_token(token)

    if payload is None:
        return render_error("Session expired")

    # get username from token/session however you're handling auth
    username = payload['sub']
    services = database.get_all_services(db, username)
    for svc in services:
        svc.pop("_id", None)
    return render_template("dashboard.html", username=username, services=services)


@app.route("/dashboard/create-service", methods=["POST"])
def create_service():
    token = request.cookies.get('auth_token')
    payload = jwt_token.verify_token(token)
    # get username from token/session however you're handling auth
    username = payload['sub']
    service_name = request.form.get("service_name", "").strip()
    callback_url = request.form.get("callback_url", "").strip()
    key = encryption.generate_key()
    database.create_service(db, username, service_name, {
        "api_key":key,
        "callback_url": callback_url,
    }, [])
    flash(key, "api_key")

    return redirect("/dashboard")

@app.route("/dashboard/delete-service/<service_name>", methods=["POST"])
def delete_service_route(service_name):
    token = request.cookies.get('auth_token')
    payload = jwt_token.verify_token(token)
    # get username from token/session however you're handling auth
    username = payload['sub']
    database.delete_service(db, username, service_name)
    return "", 200

@app.route("/dashboard/edit-service", methods=["POST"])
def edit_service():
    token = request.cookies.get('auth_token')
    payload = jwt_token.verify_token(token)
    # get username from token/session however you're handling auth
    username = payload['sub']
    service_name = request.form.get("service_name", "").strip()
    callback_url = request.form.get("callback_url", "").strip()

    database.update_service(db, username, service_name, {"callback_url": callback_url})

    return redirect("/dashboard")

@app.route("/logout")
def logout():
    response = redirect("/")

    # 2. Tell the browser to kill the cookie
    # You MUST match the 'path' and 'domain' used when you created it
    response.set_cookie('auth_token', '', expires=0, path='/')

    return response









# ── MAIN AUTH ─────────────────────────────────────────────────────────────────────
@app.route("/auth/<user>/<service>", methods=["GET", "POST"])
def auth(user, service):
    if request.method == "GET":
        return render_template("auth.html", user=user, service=service, mode="signup")

        # 1. Extract and Validate Input
    submitted_username = request.form.get("username", "").strip()
    submitted_password = request.form.get("password", "")
    mode = request.form.get("mode")
    is_signup = (mode == "signup")
    email = request.form.get("email", "").strip().lower()




    def render_error(msg):
        """Re-render the signup page with an error message and prefilled fields."""
        return render_template("auth.html", user=user, service=service, mode=mode,
                               error=msg, username=submitted_username)


    if not submitted_username or not submitted_password:
        return render_error("username and password required!")

    # 2. Fetch Data
    service_doc = database.service_get_service_document(db,user, service)
    if not service_doc:
        return render_error(f"Service '{service}' not found.")


    # 3. Process Logic
    users_list = service_doc.get("users", [])
    service_data = service_doc.get("data", [])
    existing_user = next((u for u in users_list if u["username"] == submitted_username), None)


    if existing_user is None and is_signup:
        # --- Handle Signup ---
        token = jwt_token.generate_token(submitted_username)
        token_enc = encryption.encrypt_message(token,service_data['api_key'])
        new_entry = database.service_create_user_entry(submitted_username, hash_password(submitted_password),email,token)
        database.service_add_user_to_service(db,user, service, new_entry)
        return redirect(f"{service_data['callback_url']}?token={token_enc}")

    elif existing_user is None and (not is_signup):
        return render_error("No user with that username found.")

    elif existing_user and is_signup:
        return render_error("user with that username already exists.")

    else:
        # --- Handle Login ---
        is_valid = verify_password(existing_user["password"], submitted_password)
        if is_valid:
            new_token = jwt_token.generate_token(submitted_username)
            token_enc = encryption.encrypt_message(new_token,service_data['api_key'])

            database.service_update_user_jwt(db,user, service,submitted_username, new_token)


            return redirect(f"{service_data['callback_url']}?token={token_enc}")
        else:
            return render_error("Invalid credentials.")

@app.route("/retrieve/<user>/<service>", methods=["POST"])
def retrieve_user_data(user, service):
    data  = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token required."}), 401

    payload = jwt_token.verify_token(token)

    if payload is None:
        return jsonify({"error": "Token expired or invalid."}), 401

    username = payload["sub"]

    # fetch user data from DB


    # 2. Fetch Data
    service_doc = database.service_get_service_document(db,user, service)
    if not service_doc:
        return jsonify({"error": f"error:Service '{service}' not found."})


    # 3. Process Logic
    users_list = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)


    if user_database is None:
        return jsonify({"error": "Invalid Token"}), 404

    return jsonify(user_database['user_data']), 200


@app.route("/update/<user>/<service>", methods=["POST"])
def update_user_data(user, service):
    data = request.get_json()
    token = data.get("token")
    user_data = data.get("user_data")

    if not token:
        return jsonify({"error": "Token required."}), 401

    payload = jwt_token.verify_token(token)

    if payload is None:
        return jsonify({"error": "Token expired or invalid."}), 401

    username = payload["sub"]

    # fetch user data from DB

    # 2. Fetch Data
    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return jsonify({"error": f"error:Service '{service}' not found."})

    # 3. Process Logic
    users_list = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)

    if user_database is None:
        return jsonify({"error": "Invalid Token"}), 404

    database.service_update_user_data(db,user, service, username,user_data)

    return jsonify({"status":"SUCCESS"}), 200



@app.route("/verify/<user>/<service>", methods=["POST"])
def verify_user_data(user, service):
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token required."}), 401

    payload = jwt_token.verify_token(token)

    if payload is None:
        return jsonify({"error": "Token expired or invalid."}), 401

    username = payload["sub"]

    # fetch user data from DB

    # 2. Fetch Data
    service_doc = database.service_get_service_document(db, user, service)
    if not service_doc:
        return jsonify({"error": f"error:Service '{service}' not found."})

    # 3. Process Logic
    users_list = service_doc.get("users", [])
    user_database = next((u for u in users_list if u["username"] == username), None)

    if user_database is None:
        return jsonify({"error": "User not found in service"}), 404

    return jsonify({"status":"SUCCESS"}), 200


#-----------------local functions -------------------
def hash_password(password):
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(stored_hash, provided_password):
    return bcrypt.checkpw(
        provided_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    )

# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)