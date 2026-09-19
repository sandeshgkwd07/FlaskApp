from flask import Flask, jsonify, request
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


def get_db():
    conn = sqlite3.connect('user.db')
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
                  password_hash TEXT NOT NULL
              )""")
        db.commit()
        db.close()


PUBLIC_ROUTES = {"register"}  # Flask endpoint names (function names) that skip auth


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ROUTES:
        return  # public route, no auth check

    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return jsonify({"error": "authentication required"}), 401

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM auth_user WHERE username = ?", (auth.username,)
    ).fetchone()
    conn.close()

    if user is None or not check_password_hash(user["password_hash"], auth.password):
        return jsonify({"error": "invalid username or password"}), 401
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
    conn.execute(
        "INSERT INTO auth_user (username, password_hash) VALUES (?, ?)",
        (data["username"], hashed_password)
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'User created successfully'}), 201


@app.route('/api/adduser', methods=['POST'])
def add_user():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_fname = data.get("user_fname")
    user_lname = data.get("user_lname")
    location = data.get("location")

    if not user_fname or not user_lname:
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

    user_fname = data.get("user_fname")
    if not user_fname:
        conn.close()
        return jsonify({"error": "user_fname is required"}), 400

    user_row = conn.execute("SELECT * FROM user WHERE user_id = ?", (user_id,)).fetchone()
    if user_row is None:
        conn.close()
        return jsonify({"error": "user not found"}), 404
    conn.execute("UPDATE user SET user_fname = ? WHERE user_id = ?", (user_fname, user_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "User updated successfully"}), 200


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
            "fname": cursor_row[1],
            "lname": cursor_row[2],
            "location": cursor_row[3],
        }
        user_data_l.append(user_data_d)

    db.close()
    return jsonify(user_data_l)


init_db()  # also runs at import time so it works under gunicorn, not just `python app.py`

if __name__ == '__main__':
    app.run(debug=True)