import uuid
from datetime import datetime, timezone
import dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import os
# ──────────────────────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────────────────────
dotenv.load_dotenv()

# Access them using os.getenv()
# It's safer than os.environ because it returns None instead of crashing if the key is missing
url = os.getenv("mongo_url")
DB_NAME="USER_DATA"

# ──────────────────────────────────────────────────────────────────────────────
# CONNECTION
# ──────────────────────────────────────────────────────────────────────────────

def connect_to_database():
    """
    Establish a connection to MongoDB and return the database instance.

    Args:
        mongo_uri : MongoDB connection string (e.g. "mongodb://localhost:27017/")
        db_name   : Name of the database to use

    Returns:
        db : pymongo database instance
    """
    client = MongoClient(url)
    db = client[DB_NAME]
    return db


# ──────────────────────────────────────────────────────────────────────────────
# STRUCTURE
#
# Each user gets their own collection named after their username.
#
# Collection name  : <username>   (e.g. "john_doe")
#
# Documents inside :
#
#   Profile document  (one per user) ─────────────────────────────────────────
#   {
#       "type"       : "profile",
#       "user_id"    : "<uuid>",
#       "username"   : "john_doe",
#       "data"       : {          ← any JSON you pass in from code
#           "email"        : "...",
#           "password_hash": "...",
#           "is_verified"  : false,
#           ...
#       },
#       "created_at" : <datetime>,
#       "updated_at" : <datetime>
#   }
#
#   Service document  (one per service, many per user) ────────────────────────
#   {
#       "type"         : "service",
#       "service_id"   : "<uuid>",
#       "service_name" : "my_app",
#       "data"         : {        ← any JSON you pass in from code
#           "api_key"     : "...",
#           "callback_url": "...",
#           ...
#       },
#       "created_at"   : <datetime>,
#       "updated_at"   : <datetime>
#   }
# ──────────────────────────────────────────────────────────────────────────────

def get_user_collection(db, username: str):
    """
    Return the MongoDB collection that belongs to the given user.
    Collection is named exactly after the username.

    Args:
        db       : pymongo database instance
        username : The user's username (used as collection name)

    Returns:
        collection : pymongo collection instance for this user
    """
    return db[username.lower().strip()]


# ──────────────────────────────────────────────────────────────────────────────
# PROFILE  (user identity document)
# ──────────────────────────────────────────────────────────────────────────────

def create_user_profile(db, username: str, profile_data: dict) -> dict | None:
    """
    Create a new user collection and insert their profile document.
    The profile document is identified by type = "profile".
    One profile document per collection is enforced via a unique index.

    Args:
        db           : pymongo database instance
        username     : Username — also becomes the collection name
        profile_data : Any JSON-serializable dict with the user's data
                       e.g. { "email": "...", "password_hash": "...", "is_verified": False }

    Returns:
        profile_document : The inserted document on success
        None             : If a profile for this username already exists
    """
    collection = get_user_collection(db, username)

    # Unique index scoped only to profile documents
    collection.create_index(
        "type",
        unique=True,
        partialFilterExpression={"type": "profile"},
    )

    profile_document = {
        "type":       "profile",
        "user_id":    str(uuid.uuid4()),
        "username":   username.lower().strip(),
        "data":       profile_data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    try:
        collection.insert_one(profile_document)
        return profile_document
    except DuplicateKeyError:
        return None


def get_user_profile(db, username: str) -> dict | None:
    """
    Fetch the profile document from the user's collection.

    Args:
        db       : pymongo database instance
        username : Username identifying the collection

    Returns:
        profile_document : The profile document if found, else None
    """
    collection = get_user_collection(db, username)
    return collection.find_one({"type": "profile"})


def update_user_profile(db, username: str, updated_data: dict) -> bool:
    """
    Merge new values into the user's profile `data` field.
    Only the keys provided in updated_data are changed — others are preserved.

    Args:
        db           : pymongo database instance
        username     : Username identifying the collection
        updated_data : Dict of fields to update inside `data`
                       e.g. { "is_verified": True }

    Returns:
        True  : If the profile was updated
        False : If no profile was found for this username
    """
    collection = get_user_collection(db, username)

    # Target only specific keys inside `data` — leaves all other keys untouched
    partial_update = {f"data.{key}": value for key, value in updated_data.items()}
    partial_update["updated_at"] = datetime.now(timezone.utc)

    result = collection.update_one(
        {"type": "profile"},
        {"$set": partial_update},
    )
    return result.modified_count > 0


def delete_user_profile(db, username: str) -> bool:
    """
    Drop the entire collection for this user.
    This removes the profile document AND all service documents.

    Args:
        db       : pymongo database instance
        username : Username identifying the collection to drop

    Returns:
        True  : If the collection existed and was dropped
        False : If no collection was found for this username
    """
    clean_username = username.lower().strip()

    if clean_username not in db.list_collection_names():
        return False

    db.drop_collection(clean_username)
    return True


# ──────────────────────────────────────────────────────────────────────────────
# SERVICES  (one document per service, stored inside the user's collection)
# ──────────────────────────────────────────────────────────────────────────────

def create_service(db, username: str, service_name: str, service_data: dict,user_data:list) -> dict | None:
    """
    Insert a new service document into the user's collection.

    Args:
        db           : pymongo database instance
        username     : Username identifying the collection
        service_name : Human-readable name for the service (unique per user)
        service_data : Any JSON-serializable dict with the service's data
                       e.g. { "api_key": "...", "callback_url": "..." }

    Returns:
        service_document : The inserted document on success
        None             : If a service with this name already exists for the user
    """
    collection = get_user_collection(db, username)

    # Unique index scoped only to service documents — prevents duplicate service names
    collection.create_index(
        [("type", 1), ("service_name", 1)],
        unique=True,
        partialFilterExpression={"type": "service"},
    )

    service_document = {
        "type":         "service",
        "service_id":   str(uuid.uuid4()),
        "service_name": service_name.lower().strip(),
        "data":         service_data,
        "users": user_data,
        "created_at":   datetime.now(timezone.utc),
        "updated_at":   datetime.now(timezone.utc),
    }

    try:
        collection.insert_one(service_document)
        return service_document
    except DuplicateKeyError:
        return None


def get_service(db, username: str, service_name: str) -> dict | None:
    """
    Fetch a single service document from the user's collection by service name.

    Args:
        db           : pymongo database instance
        username     : Username identifying the collection
        service_name : Name of the service to retrieve

    Returns:
        service_document : The service document if found, else None
    """
    collection = get_user_collection(db, username)
    return collection.find_one({
        "type":         "service",
        "service_name": service_name.lower().strip(),
    })


def get_all_services(db, username: str) -> list[dict]:
    """
    Fetch all service documents from the user's collection.

    Args:
        db       : pymongo database instance
        username : Username identifying the collection

    Returns:
        services : List of all service documents (empty list if none found)
    """
    collection = get_user_collection(db, username)
    return list(collection.find({"type": "service"}))


def update_service(db, username: str, service_name: str, updated_data: dict) -> bool:
    """
    Merge new values into a service document's `data` field.
    Only the keys provided in updated_data are changed — others are preserved.

    Args:
        db           : pymongo database instance
        username     : Username identifying the collection
        service_name : Name of the service to update
        updated_data : Dict of fields to update inside `data`
                       e.g. { "callback_url": "https://newurl.com" }

    Returns:
        True  : If the service was updated
        False : If no matching service was found
    """
    collection = get_user_collection(db, username)

    # Target only specific keys inside `data` — leaves all other keys untouched
    partial_update = {f"data.{key}": value for key, value in updated_data.items()}
    partial_update["updated_at"] = datetime.now(timezone.utc)

    result = collection.update_one(
        {"type": "service", "service_name": service_name.lower().strip()},
        {"$set": partial_update},
    )
    return result.modified_count > 0


def delete_service(db, username: str, service_name: str) -> bool:
    """
    Remove a single service document from the user's collection.

    Args:
        db           : pymongo database instance
        username     : Username identifying the collection
        service_name : Name of the service to delete

    Returns:
        True  : If the service was deleted
        False : If no matching service was found
    """
    collection = get_user_collection(db, username)
    result = collection.delete_one({
        "type":         "service",
        "service_name": service_name.lower().strip(),
    })
    return result.deleted_count > 0

def get_all_user_profiles(db) -> list[dict]:
    """
    Retrieve the profile document from every user collection in the database.

    Skips system collections (USERS, admin, config) that don't belong to users.

    Args:
        db : pymongo database instance

    Returns:
        profiles : List of all profile documents found across all user collections
    """
    # Collections that are not user collections — skip these
    system_collections = {"USERS", "admin", "config"}

    profiles = []

    for collection_name in db.list_collection_names():
        if collection_name in system_collections:
            continue

        profile = db[collection_name].find_one({"type": "profile"})

        if profile:
            profiles.append(profile)

    return profiles

#SERIVE FUNCTIONS
def service_get_service_document(db,user_collection_name, service_name):
    """Fetches the service document from the specific user's collection."""
    return db[user_collection_name].find_one({
        "type": "service",
        "service_name": service_name,
    })

def service_add_user_to_service(db,user_collection_name, service_name, new_user_entry):
    """Appends a new user to the users array in the service document."""
    return db[user_collection_name].update_one(
        {"type": "service", "service_name": service_name},
        {
            "$push": {"users": new_user_entry},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )

def service_update_user_jwt(db, user_collection_name, service_name, username, new_token):
    """
    Updates the JWT token for a specific user within a service document.
    Uses the positional operator '$' to target the correct user in the array.
    """
    # 1. Filter: Find the service and the specific user in the nested list
    filter_query = {
        "type": "service",
        "service_name": service_name,
        "users.username": username
    }

    # 2. Update: Use the '$' operator to refer to the index found in the filter
    update_operation = {
        "$set": {
            "users.$.jwt": new_token,
            "users.$.last_login": datetime.now(timezone.utc).isoformat(),
            "users.$.updated_at": datetime.now(timezone.utc)
        }
    }

    return db[user_collection_name].update_one(filter_query, update_operation)


def service_update_user_data(db, user_collection_name, service_name, username, data_dict):
    """
    Updates or creates specific fields inside the 'user_data' object for a user.
    'data_dict' should be a dictionary like {"theme": "dark", "notifications": True}
    """
    # 1. Filter to find the exact user entry in the nested array
    filter_query = {
        "type": "service",
        "service_name": service_name,
        "users.username": username
    }

    # 2. Build the $set dictionary dynamically
    # This turns {"bio": "Hello"} into {"users.$.user_data.bio": "Hello"}
    update_fields = {
        f"users.$.user_data": data_dict
    }

    # Add metadata
    update_fields["users.$.updated_at"] = datetime.now(timezone.utc)

    # 3. Execute the update
    return db[user_collection_name].update_one(filter_query, {"$set": update_fields})

def service_create_user_entry(username, password,email,jwt):
    return {
        "username": username,
        "password": password,
        "email": email,
        "is_verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "jwt":jwt,
        "user_data":[]
    }


# ──────────────────────────────────────────────────────────────────────────────
# LOGGING  (per-service event logs stored in the owner's collection)
# ──────────────────────────────────────────────────────────────────────────────

def insert_log(db, owner: str, service_name: str, log_data: dict):
    """
    Insert a log event into the owner's collection.
    Log documents use type="log" and are indexed by (service_name, timestamp).

    Args:
        db           : pymongo database instance
        owner        : Service owner's username (collection name)
        service_name : Name of the service this event belongs to
        log_data     : Dict with timestamp, event, status, user_id, ip, etc.
    """
    collection = get_user_collection(db, owner)

    # Idempotent index for efficient log queries (sorted by newest first)
    collection.create_index(
        [("type", 1), ("service_name", 1), ("timestamp", -1)],
        partialFilterExpression={"type": "log"},
    )

    log_data["type"] = "log"
    log_data["service_name"] = service_name
    collection.insert_one(log_data)


def get_logs(db, owner: str, service_name: str,
             event=None, status=None, user_id=None,
             limit: int = 100, skip: int = 0) -> list[dict]:
    """
    Query log events for a service with optional filters.

    Args:
        db           : pymongo database instance
        owner        : Service owner's username
        service_name : Name of the service to query logs for
        event        : Filter by event type (e.g. "login_success")
        status       : Filter by status ("success" / "failure")
        user_id      : Filter by service user's username
        limit        : Max number of logs to return (default 100)
        skip         : Number of logs to skip for pagination

    Returns:
        logs : List of log documents, newest first (without _id)
    """
    collection = get_user_collection(db, owner)
    query = {"type": "log", "service_name": service_name}

    if event:
        query["event"] = event
    if status:
        query["status"] = status
    if user_id:
        query["user_id"] = user_id

    return list(
        collection.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )


def get_service_stats(db, owner: str, service_name: str) -> dict:
    """
    Compute analytics for a service: total users, active users (1h),
    tokens issued (1h), tokens verified (1h), and last activity time.

    Args:
        db           : pymongo database instance
        owner        : Service owner's username
        service_name : Name of the service

    Returns:
        dict with keys: total_users, active_users_1h, tokens_issued_1h,
                        tokens_verified_1h, last_activity
    """
    from datetime import timedelta

    collection = get_user_collection(db, owner)

    # Total users from the service document's users array
    service_doc = collection.find_one({
        "type": "service", "service_name": service_name
    })
    total_users = len(service_doc.get("users", [])) if service_doc else 0

    # Rolling window: last 1 hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    # Active users — unique user_ids with any successful event in the window
    pipeline = [
        {"$match": {
            "type": "log",
            "service_name": service_name,
            "status": "success",
            "timestamp": {"$gte": one_hour_ago},
            "user_id": {"$ne": None},
        }},
        {"$group": {"_id": "$user_id"}},
        {"$count": "count"},
    ]
    result = list(collection.aggregate(pipeline))
    active_users = result[0]["count"] if result else 0

    # Tokens issued in last hour
    tokens_issued = collection.count_documents({
        "type": "log",
        "service_name": service_name,
        "event": "token_issued",
        "timestamp": {"$gte": one_hour_ago},
    })

    # Tokens verified in last hour
    tokens_verified = collection.count_documents({
        "type": "log",
        "service_name": service_name,
        "event": {"$in": ["token_verified", "token_verify_fail"]},
        "timestamp": {"$gte": one_hour_ago},
    })

    # Last activity — most recent log entry
    last_log = collection.find_one(
        {"type": "log", "service_name": service_name},
        sort=[("timestamp", -1)],
    )
    last_activity = last_log["timestamp"] if last_log else None

    return {
        "total_users":       total_users,
        "active_users_1h":   active_users,
        "tokens_issued_1h":  tokens_issued,
        "tokens_verified_1h": tokens_verified,
        "last_activity":     last_activity,
    }


# ──────────────────────────────────────────────────────────────────────────────
# MANUAL TEST  —  run:  python database.py
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main213___":


    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    def check(label: str, condition: bool) -> None:
        print(f"  {PASS if condition else FAIL}  {label}")

    # ── Connect ────────────────────────────────────────────────────────────────
    print("\n── CONNECTION ────────────────────────────────────────────")
    db = connect_to_database()
    check("connect_to_database returns a db instance", db is not None)

    # Drop test collection from any previous run
    db.drop_collection("john_doe")

    # ── Profile ────────────────────────────────────────────────────────────────
    print("\n── USER PROFILE ──────────────────────────────────────────")

    profile = create_user_profile(db, "john_doe", {
        "email":         "john@example.com",
        "password_hash": "hashed_pw_123",
        "is_verified":   False,
    })
    check("create_user_profile returns a document",         profile is not None)
    check("create_user_profile sets type to 'profile'",     profile["type"] == "profile")
    check("create_user_profile stores provided data",       profile["data"]["email"] == "john@example.com")
    check("create_user_profile sets is_verified to False",  profile["data"]["is_verified"] == False)

    duplicate = create_user_profile(db, "john_doe", {"email": "other@example.com"})
    check("create_user_profile returns None on duplicate",  duplicate is None)

    fetched = get_user_profile(db, "john_doe")
    check("get_user_profile finds existing profile",        fetched is not None)
    check("get_user_profile returns correct username",      fetched["username"] == "john_doe")

    missing = get_user_profile(db, "ghost_user")
    check("get_user_profile returns None for unknown user", missing is None)

    updated = update_user_profile(db, "john_doe", {"is_verified": True})
    check("update_user_profile returns True on success",    updated == True)
    refreshed = get_user_profile(db, "john_doe")
    check("update_user_profile updates the field",          refreshed["data"]["is_verified"] == True)
    check("update_user_profile preserves other fields",     refreshed["data"]["email"] == "john@example.com")

    bad_update = update_user_profile(db, "ghost_user", {"is_verified": True})
    check("update_user_profile returns False for unknown user", bad_update == False)

    # ── Services ───────────────────────────────────────────────────────────────
    print("\n── SERVICES ──────────────────────────────────────────────")

    service = create_service(db, "john_doe", "my_app",
                             {
                                        "api_key":      "key-abc-123",
                                        "callback_url": "https://myapp.com/callback",},
                             [{
                                 "username": "john",
                                 "password":"hashed-password",
                                 "email":"you@example.com",
                                 "is_verified": False,
                             }]
                             )
    check("create_service returns a document",              service is not None)
    check("create_service sets type to 'service'",          service["type"] == "service")
    check("create_service stores provided data",            service["data"]["api_key"] == "key-abc-123")

    duplicate_service = create_service(db, "john_doe", "my_app", {"api_key": "other"},[{
                                 "username": "john",
                                 "password":"hashed-password",
                                 "email":"you@example.com",
                                 "is_verified": False,
                             }])
    check("create_service returns None on duplicate name",  duplicate_service is None)

    create_service(db, "john_doe", "second_app", {"api_key": "key-xyz-999"},[{
                                 "username": "john",
                                 "password":"hashed-password",
                                 "email":"you@example.com",
                                 "is_verified": False,
                             }])

    fetched_service = get_service(db, "john_doe", "my_app")
    check("get_service finds existing service",             fetched_service is not None)
    check("get_service returns correct service_name",       fetched_service["service_name"] == "my_app")

    missing_service = get_service(db, "john_doe", "nonexistent_app")
    check("get_service returns None for unknown service",   missing_service is None)

    all_services = get_all_services(db, "john_doe")
    check("get_all_services returns all services",          len(all_services) == 2)

    no_services = get_all_services(db, "ghost_user")
    check("get_all_services returns empty list for unknown user", no_services == [])

    svc_updated = update_service(db, "john_doe", "my_app", {"callback_url": "https://newurl.com"})
    check("update_service returns True on success",         svc_updated == True)
    refreshed_svc = get_service(db, "john_doe", "my_app")
    check("update_service updates the field",               refreshed_svc["data"]["callback_url"] == "https://newurl.com")
    check("update_service preserves other fields",          refreshed_svc["data"]["api_key"] == "key-abc-123")

    bad_svc_update = update_service(db, "john_doe", "ghost_app", {"callback_url": "x"})
    check("update_service returns False for unknown service", bad_svc_update == False)

    svc_deleted = delete_service(db, "john_doe", "second_app")
    check("delete_service returns True on success",         svc_deleted == True)
    check("delete_service removes the document",            get_service(db, "john_doe", "second_app") is None)

    bad_svc_delete = delete_service(db, "john_doe", "ghost_app")
    check("delete_service returns False for unknown service", bad_svc_delete == False)

    # # ── Delete User ────────────────────────────────────────────────────────────
    # print("\n── DELETE USER ───────────────────────────────────────────")
    #
    # user_deleted = delete_user_profile(db, "john_doe")
    # check("delete_user_profile returns True on success",    user_deleted == True)
    # check("delete_user_profile drops the entire collection",
    #       "john_doe" not in db.list_collection_names())
    #
    # not_found = delete_user_profile(db, "ghost_user")
    # check("delete_user_profile returns False for unknown user", not_found == False)

    print("\n── DONE ──────────────────────────────────────────────────\n")