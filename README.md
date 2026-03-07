# ⚡ EasyAuth

**Add auth to any app in under a minute. No compromises on security.**

Stop rebuilding login flows. EasyAuth gives you a fully hosted, production-grade authentication system — sign up, log in, session management, encrypted tokens, per-user data storage — in the time it takes to make coffee.

```
 Create Account  ──────►  Create Service  ──────►  Enjoy
  easyauth.dev             grab API key            ship faster
```

---

## Seriously. Under a minute.

```
1. Register at easyauth.dev
2. Create a service → get your API key
3. Point your app to /auth/<you>/<your-service>
```

That's it. EasyAuth handles the rest.

---

## See It Live

```
 Signed up as `dummy`  ──────►  Created service `new_app`  ──────►  Live auth page ✓
```

**[http://easy-auth.dev/auth/dummy/new_app](http://easy-auth.dev/auth/dummy/new_app)**

That URL is all we had to set up. Everything on that page — the form, the validation, the password hashing, the token — is handled by EasyAuth.

---

## How It Looks From Your App

Redirect your users here:
```
https://easyauth.dev/auth/your_username/your_service
```

EasyAuth handles the entire sign-up / login UI. On success, your user lands back at your callback URL with a token:
```
https://yourapp.com/callback?token=<encrypted_token>
```

Decrypt it with your API key, and you're in.

---

## Integrate With Your App

EasyAuth works with any stack that can make an HTTP request. For popular frameworks, we have official SDKs that make integration even simpler.

### Flask — one line and EasyAuth is in your app

Add `@login_required` to any route. That's it. Your existing code doesn't change.

```python
@app.route("/dashboard")
@login_required          # ← one line. full auth. done.
def dashboard(token):
    ...
```

📦 [AvikYadav/EasyAuth_Flask-Connector](https://github.com/AvikYadav/EasyAuth_Flask-Connector)

> More SDKs coming — Django, React, and others are on the roadmap.

---

## What You Get Out of the Box

- ✅ Sign up & login UI — hosted, styled, ready to go
- ✅ Encrypted token delivery to your callback URL
- ✅ Per-user data storage — read and write arbitrary JSON per user per service
- ✅ Token verification endpoint — confirm any token is valid in one call
- ✅ Full isolation — your service's users are completely separate from every other service
- ✅ Works with any stack — if it can make an HTTP request, it works

---

## Security — No Compromises

EasyAuth is built for developers who care about doing things right. Here's exactly what's under the hood:

### Passwords — bcrypt, cost factor 12
Every password is hashed with bcrypt before it touches the database. Plaintext never leaves memory. Verification uses constant-time comparison — timing attacks don't work here.

### Sessions — signed JWTs, 1-hour expiry
Platform sessions use HS256-signed JWTs delivered as `HttpOnly; Secure; SameSite=Strict` cookies. JavaScript can't read them. They can't be sent cross-site. They expire.

### Token Delivery — Fernet encryption (AES-128-CBC + HMAC-SHA256)
When a user authenticates through your service, the JWT is **encrypted with your unique API key** before being sent to your callback URL. Only your app can decrypt it. If the token is intercepted in transit, it's unreadable ciphertext. Fernet also authenticates the ciphertext — a tampered token fails to decrypt, not silently.

### Data Isolation — structurally separated at the database level
Every platform user gets their own MongoDB collection. There are no shared tables, no multi-tenant query filters that could be bypassed. Your users' data lives in your namespace and only your namespace.

### XSS — strict Content Security Policy
`script-src 'self'` is enforced across every page. Zero inline event handlers exist in any template — all JS runs from external files attached via `addEventListener`. An injected script has nowhere to execute.

### CSRF — blocked at the browser
`SameSite=Strict` on the session cookie means cross-origin requests never carry credentials. No CSRF tokens needed because the browser won't send the cookie at all.

---

## For the Sceptical Dev

> Here's the checklist:

| Concern | What EasyAuth does |
|---|---|
| Password storage | bcrypt, cost 12, constant-time verify |
| Session tokens | HS256 JWT, 5hr expiry, unique `jti` per token |
| Cookie security | HttpOnly + Secure + SameSite=Strict |
| Token in transit | Fernet-encrypted before leaving the server |
| XSS | Strict CSP, zero inline handlers |
| CSRF | SameSite=Strict makes CSRF tokens redundant |
| Data isolation | Per-user MongoDB collections, not rows in a shared table |
| Duplicate accounts | Unique partial index at DB level, race-condition safe |

No auth logic runs client-side. No credentials are logged. No tokens are stored in plaintext. If you want to audit the source, it's all right here.

---

## API Reference

### Auth Gate
```
GET  /auth/<owner>/<service>   → renders login/signup UI
POST /auth/<owner>/<service>   → authenticates user, redirects to callback with token
```

### Data API
```
POST /retrieve/<owner>/<service>   { "token": "..." }  → returns user's stored data
POST /update/<owner>/<service>     { "token": "...", "user_data": {...} }  → writes user data
POST /verify/<owner>/<service>     { "token": "..." }  → confirms token is valid
```

---

## Self-Hosting

Prefer to run it yourself? Clone and go:

```bash
git clone https://github.com/you/easyauth
pip install flask pymongo python-dotenv pyjwt bcrypt cryptography
echo "mongo_url=your_mongo_connection_string" > .env
python main.py
```

Add your MongoDB connection string and you're running a fully self-hosted auth server.

---

## Stack

Python · Flask · MongoDB · PyJWT · Fernet · bcrypt

---

*EasyAuth — because auth should be a five-minute task, not a five-day one.*
