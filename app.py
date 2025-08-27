from flask import Flask, request, jsonify
from flask_cors import CORS
from flask import g
import sqlite3

app = Flask(__name__)
CORS(app)

# --- Tạo DB nếu chưa có ---
def init_db():
    conn = sqlite3.connect("forum.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- API đăng ký ---
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Thiếu username hoặc password"}), 400

    try:
        conn = sqlite3.connect("forum.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return jsonify({"message": "Đăng ký thành công"})
    except sqlite3.IntegrityError:
        return jsonify({"message": "Tên đăng nhập đã tồn tại"}), 400

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect("forum.db", check_same_thread=False)
    return g.db


if __name__ == "__main__":
    app.run(debug=True)
