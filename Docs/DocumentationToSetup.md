# EasyAuth — Local Setup Guide

Get EasyAuth running on your own machine in a few minutes.

---

## Prerequisites

Make sure you have these installed before starting:

- **Python 3.10+** — [python.org/downloads](https://python.org/downloads)
- **MongoDB or any DB** — either a local install or a free cloud cluster via [MongoDB Atlas](https://www.mongodb.com/atlas)
- **Git**

Verify your Python version:
```bash
python --version
```

---

## Installation

Clone the repo and install dependencies:

```bash
git clone https://github.com/you/easyauth
cd easyauth
pip install -r requirements.txt
```

That's all EasyAuth needs. No framework bloat.

---

## Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Add your MongoDB connection string:

```
mongo_url=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/
```

If you're running MongoDB locally, it's just:

```
mongo_url=mongodb://localhost:27017/
```

> **Never commit `.env` to Git.** It's already in `.gitignore` — keep it that way.

---

## Running Locally

Start the server:

```bash
python main.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open your browser and go to `http://127.0.0.1:5000` — you'll land on the sign-up page.

Create an account, head to your dashboard, and register your first service. Your local auth URL for any service will be:

```
http://127.0.0.1:5000/auth/<your_username>/<your_service_name>
```

---

## Testing

**Test the auth flow manually**

1. Go to `http://127.0.0.1:5000`, create an account
2. From the dashboard, create a service — copy the API key when it appears (shown once)
3. Visit `http://127.0.0.1:5000/auth/<your_username>/<your_service_name>` and sign up as a test user
4. You'll be redirected to your callback URL with an encrypted token in the query string

**Test the data API**

```python
from easy_auth import LoginConnector

auth = LoginConnector(
    base_url="http://127.0.0.1:5000",
    username="your_username",
    service_name="your_service_name",
    api_key="your_api_key"
)

# Write data
auth.send_user_data(token, {"plan": "free", "onboarded": True})

# Read it back
print(auth.get_user_data(token))

# Verify the token is valid
print(auth.verify_token(token))  # True / False
```

---

## Troubleshooting

**`pymongo.errors.ServerSelectionTimeoutError`**
Your connection string is wrong or your IP isn't whitelisted in Atlas. Double-check both.

**`ModuleNotFoundError`**
A package didn't install. Re-run `pip install -r requirements.txt` from inside the project folder.

**Cookie not being set after login**
The session cookie is marked `Secure` — it only transmits over HTTPS. For local dev, temporarily set `secure=False` in the `set_cookie` calls inside `main.py`.

**Port 5000 already in use**
Change the port in the last line of `main.py`:
```python
app.run(debug=True, port=8080)
```

---

## Project Structure

```
easyauth/
├── main.py            # All routes and app logic
├── database.py        # MongoDB helpers
├── jwt_token.py       # JWT generation and verification
├── encryption.py      # Fernet encrypt / decrypt
├── templates/
│   ├── signup.html    # Platform sign-up / login page
│   ├── auth.html      # Third-party app auth gate
│   └── dashboard.html
├── static/
│   ├── style.css
│   ├── signup.js
│   └── auth.js
└── .env               # Your secrets — never commit this
```

---

## Bringing Your Own Database

EasyAuth's entire database layer lives in a single file — `database.py`. If you want to use a different database (PostgreSQL, SQLite, DynamoDB, anything), just replace that file with your own implementation.

As long as your file exposes the following functions with the same signatures, the rest of the app will work without touching a single line of `main.py`:

```python
# ── Connection ────────────────────────────────────────────────
connect_to_database()
# Returns a database instance — whatever your DB client uses

# ── Platform user profile ─────────────────────────────────────
create_user_profile(db, username, profile_data)
# Creates a new user. Returns the created document, or None if username already exists.

get_user_profile(db, username)
# Returns the user's profile document, or None if not found.

update_user_profile(db, username, updated_data)
# Merges updated_data into the user's profile. Returns True on success, False if not found.

delete_user_profile(db, username)
# Deletes the user and all their data. Returns True on success, False if not found.

# ── Services ──────────────────────────────────────────────────
create_service(db, username, service_name, service_data, users_list)
# Creates a new service for the user. Returns the document, or None if name already taken.

get_service(db, username, service_name)
# Returns the service document, or None if not found.

get_all_services(db, username)
# Returns a list of all service documents for the user. Empty list if none.

update_service(db, username, service_name, updated_data)
# Updates fields inside the service's data. Returns True on success, False if not found.

delete_service(db, username, service_name)
# Deletes the service document. Returns True on success, False if not found.

# ── Service user management ───────────────────────────────────
service_get_service_document(db, user_collection_name, service_name)
# Returns the full service document including its users array.

service_create_user_entry(username, password_hash, email, jwt)
# Builds and returns a new user entry dict to be inserted into the users array.

service_add_user_to_service(db, user_collection_name, service_name, new_user_entry)
# Appends a new user entry to the service's users array.

service_update_user_jwt(db, user_collection_name, service_name, username, new_token)
# Updates the stored JWT for a specific user in the service's users array.

service_update_user_data(db, user_collection_name, service_name, username, data_dict)
# Writes arbitrary JSON data into the user's user_data field inside the service.
```

Keep the return types consistent — `main.py` checks for `None` on lookups and `True/False` on writes. Everything else is up to your implementation.

---

## Going to Production

When you're ready to deploy:

- Set `debug=False` in `main.py`
- **Fix the JWT secret key** — `jwt_token.py` currently generates a new random secret on every server start (`secrets.token_hex(35)`). This means every restart invalidates all active sessions. Replace it with a stable secret stored in your `.env`:
  ```
  # .env
  JWT_SECRET=your-long-random-secret-here
  ```
  ```python
  # jwt_token.py
  JWT_SECRET_KEY = os.getenv("JWT_SECRET")
  ```
- Use a stable secret key for `app.config['SECRET_KEY']` — not one regenerated on every restart
- **Fix the CSP for Google Fonts** — the default CSP blocks external fonts. Update the header in `main.py` to allow them:
  ```python
  csp = (
      "default-src 'self'; "
      "script-src 'self'; "
      "style-src 'self' https://fonts.googleapis.com; "
      "font-src 'self' https://fonts.gstatic.com; "
      "object-src 'none'; "
      "frame-ancestors 'none';"
  )
  ```
- **Run with Gunicorn** instead of Flask's dev server — it's already in `requirements.txt`:
  ```bash
  gunicorn -w 4 -b 0.0.0.0:8000 main:app
  ```
- Serve over HTTPS — the `Secure` cookie flag and HSTS header both depend on it
- Revert `secure=True` on all cookies if you changed it for local dev