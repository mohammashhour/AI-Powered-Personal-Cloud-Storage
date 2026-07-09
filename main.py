from typing import Optional
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from argon2.exceptions import VerifyMismatchError
import hashlib, os
import sqlite3
from argon2 import PasswordHasher
from httpx import request
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import RedirectResponse
import os
from dotenv import load_dotenv, dotenv_values
from fastapi import UploadFile, File
from fastapi.responses import RedirectResponse, FileResponse

load_dotenv() 
ph = PasswordHasher()

DB_PATH = "app.db"


conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rtpass BOOLEAN NOT NULL,
    storageused INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS userdata (
    data_id INTEGER PRIMARY KEY ,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(data_id) REFERENCES data(user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS data (
    data_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    size INTEGER Not NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS shared (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    shared_with INTEGER NOT NULL,

    FOREIGN KEY(data_id) REFERENCES data(data_id),
    FOREIGN KEY(owner_id) REFERENCES users(user_id),
    FOREIGN KEY(shared_with) REFERENCES users(user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS recentfiles(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    data_id INTEGER NOT NULL,
    last_opened TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(data_id) REFERENCES data(data_id)
)
""")

conn.commit()


app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key= os.getenv("secretkey")
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("secretkey"),
    max_age=60 * 60 * 24  #1 day
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="pages")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="login.html"
)

@app.post("/share/{filename}")
async def share_file(
    request: Request,
    filename: str,
    username: str = Form(...)
):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    owner_id = request.session["user_id"]
    owner_username = request.session["username"]

    file_path = os.path.join(owner_username, filename)

    cursor.execute(
        "SELECT data_id FROM data WHERE location=?",
        (file_path,)
    )

    row = cursor.fetchone()

    if not row:
        return {"error":"File not found"}

    data_id = row[0]

    cursor.execute(
        "SELECT user_id FROM users WHERE username=?",
        (username,)
    )

    row = cursor.fetchone()

    if not row:
        return {"error":"User not found"}

    shared_with = row[0]

    cursor.execute(
        """
        INSERT INTO shared(data_id, owner_id, shared_with)
        VALUES(?,?,?)
        """,
        (data_id, owner_id, shared_with)
    )

    conn.commit()

    return {"success":True}

@app.get("/dashboard")
async def dashboard(request: Request, search: str = ""):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    user_id = request.session["user_id"]
    username = request.session["username"]

    user_folder = username
    user_folder = username
    user_files = []

    if os.path.exists(user_folder):
        user_files = sorted(os.listdir(user_folder))
    
    if search:
        user_files = [
            file for file in user_files
            if search.lower() in file.lower()
        ]

    cursor.execute("""
        SELECT data.location
        FROM recentfiles
        JOIN data
        ON recentfiles.data_id = data.data_id
        WHERE recentfiles.user_id = ?
        ORDER BY recentfiles.last_opened DESC
        LIMIT 3
    """, (user_id,))

    recent_files = [
        os.path.basename(row[0])
        for row in cursor.fetchall()
    ]

    cursor.execute("""
        SELECT data.location
        FROM shared
        JOIN data
        ON shared.data_id = data.data_id
        WHERE shared.shared_with = ?
        """, (user_id,))

    shared_files = [
            os.path.basename(row[0])
            for row in cursor.fetchall()
        ]

    cursor.execute(
        "SELECT storageused FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    storage_used = row[0] if row and row[0] else 0

    STORAGE_LIMIT = 150 * 1024 * 1024 * 1024

    storage_percent = round(
        (storage_used / STORAGE_LIMIT) * 100,
        2
    )

    storage_used_gb = round(
        storage_used / (1024 ** 3),
        2
    )

    storage_remaining_gb = round(
        150 - storage_used_gb,
        2
    )

    return templates.TemplateResponse(
        request=request,
        name="Dashboard.html",
        context={
            "name": request.session["name"],
            "recent_files": recent_files,
            "shared_files": shared_files,
            "storage_used": storage_used_gb,
            "storage_remaining": storage_remaining_gb,
            "storage_percent": storage_percent,
            "user_files": user_files,
            "search": search,

}
)

@app.post("/delete/{filename}")
async def delete_file(request: Request, filename: str):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    user_id = request.session["user_id"]
    username = request.session["username"]

    file_path = os.path.join(username, filename)

    if not os.path.isfile(file_path):
        return RedirectResponse("/dashboard", status_code=303)

    size = os.path.getsize(file_path)

    # Remove from disk
    os.remove(file_path)

    # Find the database record
    cursor.execute(
        """
        SELECT data_id
        FROM data
        WHERE location = ?
        """,
        (file_path,)
    )

    row = cursor.fetchone()

    if row:
        data_id = row[0]

        cursor.execute(
            "DELETE FROM userdata WHERE data_id = ?",
            (data_id,)
        )

        cursor.execute(
            "DELETE FROM recentfiles WHERE data_id = ?",
            (data_id,)
        )

        cursor.execute(
            "DELETE FROM data WHERE data_id = ?",
            (data_id,)
        )

    cursor.execute(
        """
        UPDATE users
        SET storageused = storageused - ?
        WHERE user_id = ?
        """,
        (size, user_id)
    )

    conn.commit()

    return RedirectResponse("/dashboard", status_code=303)

@app.get("/download-shared/{filename}")
async def download_shared_file(request: Request, filename: str):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    user_id = request.session["user_id"]

    cursor.execute("""
        SELECT data.location
        FROM shared
        JOIN data
        ON shared.data_id = data.data_id
        WHERE shared.shared_with = ?
        AND data.location LIKE ?
    """, (user_id, f"%/{filename}"))

    row = cursor.fetchone()

    if not row:
        cursor.execute("""
            SELECT data.location
            FROM shared
            JOIN data
            ON shared.data_id = data.data_id
            WHERE shared.shared_with = ?
            AND data.location LIKE ?
        """, (user_id, f"%\\{filename}"))

        row = cursor.fetchone()

    if not row:
        return {"error": "File not found"}

    file_path = row[0]

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.post("/upload-file")
async def upload_file(
    request: Request,
    folder: str = Form(""),
    file: UploadFile = File(...)
):
    user_id = request.session["user_id"]
    username = request.session["username"]
    data_id = cursor.lastrowid



    # Root folder for this user
    user_root = username

    # Upload destination
    destination = os.path.join(user_root, folder)

    os.makedirs(destination, exist_ok=True)

    file_path = os.path.join(destination, file.filename)

    contents = await file.read()

    with open(file_path, "wb") as f:
        f.write(contents)

    size = len(contents)

    cursor.execute(
        """
        INSERT INTO data(location,size)
        VALUES(?,?)
        """,
        (file_path, size)
    )

    data_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO userdata(user_id,data_id)
        VALUES(?,?)
        """,
        (user_id, data_id)
    )

    cursor.execute(
        """
        UPDATE users
        SET storageused = COALESCE(storageused,0) + ?
        WHERE user_id = ?
        """,
        (size, user_id)
    )

    cursor.execute(
        """
        INSERT INTO recentfiles (user_id, data_id)
        VALUES (?, ?)
        """,
        (user_id, data_id)
    )

    conn.commit()

    return RedirectResponse("/dashboard", status_code=303)

@app.get("/download/{filename}")
async def download_file(request: Request, filename: str):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    user_id = request.session["user_id"]
    username = request.session["username"]

    file_path = os.path.join(username, filename)

    if not os.path.isfile(file_path):
        return {"error": "File not found"}

    # Find the file in the database
    cursor.execute(
        """
        SELECT data_id
        FROM data
        WHERE location = ?
        """,
        (file_path,)
    )

    row = cursor.fetchone()

    if row:
        data_id = row[0]

        # Remove old recent entry
        cursor.execute(
            """
            DELETE FROM recentfiles
            WHERE user_id = ? AND data_id = ?
            """,
            (user_id, data_id)
        )

        # Insert a new one with the current timestamp
        cursor.execute(
            """
            INSERT INTO recentfiles(user_id, data_id)
            VALUES(?, ?)
            """,
            (user_id, data_id)
        )

        conn.commit()

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/search")
async def search(request: Request, search: str = ""):
    if "user_id" not in request.session:
        return RedirectResponse("/loginpage")

    username = request.session["username"]

    user_folder = username

    user_files = []

    if os.path.exists(user_folder):

        for file in os.listdir(user_folder):
            if search.lower() in file.lower():
                user_files.append(file)

    return templates.TemplateResponse(
        request=request,
        name="Dashboard.html",
        context={
            "name": request.session["name"],
            "recent_files": [],
            "shared_files": [],
            "storage_used": 0,
            "storage_remaining": 150,
            "storage_percent": 0,
            "user_files": sorted(user_files),
            "search": search
        }
    )

@app.get("/forgotpassword")
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="Forgot.html"
)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/loginpage", status_code=302)

@app.get("/loginpage")
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="login.html"
)

@app.get("/signuppage")
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="signup.html" 
    )


@app.post("/signup")
async def signup(
    request: Request, 
    username: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    remember_me: Optional[bool] = Form(False)
):

    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "ERROR Username already taken"}
        )
    cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "ERROR email already taken"}
        )
    if len(username) < 3:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "ERROR Username is less than 3 characters"}
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
            context={"error": "ERROR password is less than 8 characters"}
        )
    
    
    cursor.execute(
        "INSERT INTO users (name, email, username, password_hash, rtpass) VALUES (?, ?, ?, ?, ?)",
        (name, email, username, ph.hash(password), False),
    )
    os.mkdir(username)
    conn.commit()
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    user_id = cursor.fetchone()[0]
    request.session["user_id"] = user_id
    request.session["username"] = username
    request.session["name"] = name

    return RedirectResponse(url="/dashboard", status_code=302)


@app.post("/login")
async def login(
    request: Request,  
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    remember_me: Optional[bool] = Form(False)
):
    
    if remember_me:
        request.session.permanent = True
        request.session.max_age = 60 * 60 * 24 * 30  # 30 days
    else:
        request.session.permanent = False
        request.session.max_age = 60 * 60 * 2  # 2 hours

    if not username or not password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "ERROR Invalid username or password"}
        )

    cursor.execute(
        "SELECT user_id, password_hash, name FROM users WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()

    if not row:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "ERROR Invalid username or password"}
        )

    user_id, stored_hash, forename = row

    try:
        ph.verify(stored_hash, password)
    except VerifyMismatchError:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "ERROR Invalid username or password"}
        )

    request.session["user_id"] = user_id
    request.session["username"] = username
    request.session["name"] = forename

    return RedirectResponse(url="/dashboard", status_code=302)