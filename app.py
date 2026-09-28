from flask import Flask, jsonify, request
import sqlite3
import secrets
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

app.config["DATABASE"] = os.getenv("DATABASE_PATH", "user.db")

def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS user(
                  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_fname TEXT NOT NULL,
                  user_lname TEXT NOT NULL,
                  location TEXT NOT NULL
              )""")
        db.execute("""CREATE TABLE IF NOT EXISTS auth_user(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  token_hash TEXT
              )""")
        db.commit()
        db.close()


PUBLIC_ROUTES = {"register", "login"}  # Flask endpoint names (function names) that skip auth


def hash_token(token: str) -> str:
    """One-way hash for storing/looking up tokens (tokens are high-entropy, so plain SHA-256 is fine)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    """Generates a new random, URL-safe token."""
    return secrets.token_urlsafe(32)


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ROUTES:
        return  # public route, no auth check

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "authentication required"}), 401

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return jsonify({"error": "authentication required"}), 401

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM auth_user WHERE token_hash = ?", (hash_token(token),)
    ).fetchone()
    conn.close()

    if user is None:
        return jsonify({"error": "invalid or expired token"}), 401
    # auth passed -> Flask proceeds to the actual route


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'username and password required'}), 400

    conn = get_db()
    existing_user = conn.execute(
        "SELECT * FROM auth_user WHERE username = ?", (data['username'],)
    ).fetchone()
    if existing_user:
        conn.close()
        return jsonify({'error': 'User already exists'}), 400

    hashed_password = generate_password_hash(data['password'])
    token = generate_token()
    token_hash = hash_token(token)

    conn.execute(
        "INSERT INTO auth_user (username, password_hash, token_hash) VALUES (?, ?, ?)",
        (data["username"], hashed_password, token_hash)
    )
    conn.commit()
    conn.close()
    return jsonify({
        'message': 'User created successfully',
        'token': token  # shown only once — client must store this
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Re-authenticate with username/password and get a fresh token (invalidates the old one)."""
    data = request.get_json(silent=True)
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'username and password required'}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM auth_user WHERE username = ?", (data['username'],)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], data['password']):
        conn.close()
        return jsonify({'error': 'invalid username or password'}), 401

    token = generate_token()
    token_hash = hash_token(token)
    conn.execute(
        "UPDATE auth_user SET token_hash = ? WHERE id = ?", (token_hash, user["id"])
    )
    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Login successful',
        'token': token
    }), 200


@app.route('/api/adduser', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_fname = data.get("user_fname")
    user_lname = data.get("user_lname")
    location = data.get("location")

    if not user_fname or not user_lname or not location:
        return jsonify({"error": "user_fname and user_lname are required"}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO user (user_fname, user_lname, location) VALUES (?, ?, ?)",
        (user_fname, user_lname, location)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Data inserted successfully"}), 201


@app.route('/api/user/delete/<int:user_id>', methods=['DELETE'])
def delete_user(user_id: int):
    conn = get_db()
    data_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    if data_row is None:
        conn.close()
        return jsonify({"error": "user not found"}), 404
    conn.execute("DELETE FROM user WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "User deleted successfully"}), 200


@app.route('/api/user/update/<int:user_id>', methods=['PUT'])
def update_user(user_id: int):
    conn = get_db()
    data = request.get_json(silent=True)
    if not data:
        conn.close()
        return jsonify({"error": "No data provided"}), 400

    # map incoming JSON keys to actual DB column names
    column_map = {
        "user_fname": "user_fname",
        "user_lname": "user_lname",
        "location": "location"
    }

    # keep only known, non-empty fields
    fields = {k: v for k, v in data.items() if k in column_map and v not in (None, "")}

    if not fields:
        conn.close()
        return jsonify({"error": "At least one of user_fname, user_lname, location is required"}), 400

    user_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    if user_row is None:
        conn.close()
        return jsonify({"error": "user not found"}), 404

    set_clauses = [f"{column_map[k]} = ?" for k in fields]
    values = list(fields.values())
    values.append(user_id)

    query = f"UPDATE user SET {', '.join(set_clauses)} WHERE user_id = ?"
    conn.execute(query, values)
    conn.commit()
    conn.close()

    return jsonify({"message": "User updated successfully"}), 200


@app.route('/api/user/patch/<int:user_id>', methods=['PATCH'])
def patch_user(user_id: int):
    """
    Partial update: send only the field(s) you want to change.
    Accepted JSON keys: user_fname, user_lname, location.
    Example:
        PATCH /api/user/patch/1
        { "user_fname": "Navya" }

        PATCH /api/user/patch/2
        { "user_fname": "Aarav", "location": "Gujarat" }
    """
    conn = get_db()
    data = request.get_json(silent=True)
    if not data:
        conn.close()
        return jsonify({"error": "No data provided"}), 400

    # map incoming JSON keys to actual DB column names
    column_map = {
        "user_fname": "user_fname",
        "user_lname": "user_lname",
        "location": "location"
    }

    # keep only known, non-empty fields
    fields = {k: v for k, v in data.items() if k in column_map and v not in (None, "")}

    if not fields:
        conn.close()
        return jsonify({"error": "At least one of user_fname, user_lname, location is required"}), 400

    user_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    if user_row is None:
        conn.close()
        return jsonify({"error": "user not found"}), 404

    set_clauses = [f"{column_map[k]} = ?" for k in fields]
    values = list(fields.values())
    values.append(user_id)

    query = f"UPDATE user SET {', '.join(set_clauses)} WHERE user_id = ?"
    conn.execute(query, values)
    conn.commit()

    updated_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()

    return jsonify({
        "message": "User patched successfully",
        "user": dict(updated_row)
    }), 200


@app.route('/api/get/userbyid/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id: int):
    conn = get_db()
    data_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if data_row is None:
        return jsonify({"error": "user not found"}), 404

    return jsonify({"user": dict(data_row)}), 200  # dict() makes the Row JSON-serializable


@app.route('/api/get/allusers')
def get_all_users():
    db = get_db()
    cursor = db.execute("SELECT * FROM user")

    user_data_l = []
    for cursor_row in cursor:
        user_data_d = {
            "id": cursor_row[0],
            "user_fname": cursor_row[1],
            "user_lname": cursor_row[2],
            "location": cursor_row[3],
        }
        user_data_l.append(user_data_d)

    db.close()
    return jsonify(user_data_l)




if __name__ == '__main__':
    init_db()
    app.run(debug=True)