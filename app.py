from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
import os
import jwt
import datetime
from functools import wraps

app = Flask(__name__)

CORS(
    app,
    resources={r"/api/*": {
        "origins": [
            "https://3d681f448795.ngrok-free.app",   # dev local
            "https://forum-backend-1-b0uk.onrender.com"  # FE build
        ]
    }},
    supports_credentials=True
)

SECRET_KEY = os.environ.get("SECRET_KEY", "secret_dev_key")

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS comments")
    cur.execute("DROP TABLE IF EXISTS posts")
    cur.execute("DROP TABLE IF EXISTS users")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id SERIAL PRIMARY KEY,
            post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
            (username, password)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Đăng ký thành công"})
    except errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": "Tên đăng nhập đã tồn tại"}), 400

# --- API đăng nhập ---
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "Thiếu username hoặc password"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username FROM users WHERE username = %s AND password = %s",
        (username, password)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        payload = {
            "username": user["username"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return jsonify({
            "message": "Đăng nhập thành công", "token": token
        })
    else:
        return jsonify({"message": "Sai username hoặc password"}), 401


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]  # Bearer <token>
        if not token:
            return jsonify({"error": "Token thiếu"}), 403
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data["username"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token hết hạn"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token không hợp lệ"}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@app.route("/api/logout", methods=["POST"])
def logout():
    return jsonify({"message": "Đã logout"})

# --- Đăng bài ---
@app.route("/api/create_post", methods=["POST"])
@token_required
def create_post(current_user):
    data = request.json
    title = data.get("title")
    content = data.get("content")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (username, title, content) VALUES (%s,%s,%s) RETURNING id",
                (current_user, title, content))
    post_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "tạo bài thành công", "post_id": post_id,  "username": current_user})

# --- Lấy danh sách bài ---
@app.route("/api/posts", methods=["GET"])
def get_posts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""SELECT id, username, title, content, created_at
                    FROM posts
                    ORDER BY created_at DESC""")
    posts = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(posts)

# --- Thêm bình luận ---
@app.route("/api/add_comment/<int:post_id>", methods=["POST"])
@token_required
def add_comment(current_user, post_id):
    data = request.json
    content = data.get("content")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO comments (post_id, username, content) VALUES (%s,%s,%s) RETURNING id",
                (post_id, current_user, content))
    comment_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "bình luận thành công", "comment_id": comment_id, "username": current_user})

# --- Lấy bình luận của 1 bài ---
@app.route("/api/comments/<int:post_id>", methods=["GET"])
def get_comments(post_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""SELECT id, username, content, created_at
                    FROM comments
                    WHERE post_id=%s
                    ORDER BY created_at ASC
                """, (post_id,))
    comments = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(comments)

# --- Xóa bài ---
@app.route("/api/delete_post/<int:post_id>", methods=["DELETE"])
@token_required
def delete_post(current_user, post_id):
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM posts WHERE id = %s AND username = %s",
        (post_id, current_user)
    )
    post = cur.fetchone()
    if not post:
        cur.close()
        conn.close()
        return jsonify({"error": "không tìm thấy bài hoặc không có quyền"}), 403

    # Xóa bài
    cur.execute("DELETE FROM posts WHERE id = %s", (post_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Đã xóa bài"})

if __name__ == "__main__":
    app.run(debug=True)
