from typing import Optional
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import hashlib, os
import sqlite3
from argon2 import PasswordHasher

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
    rtpass BOOLEAN NOT NULL
)
""")

"""
cursor.execute(
CREATE TABLE IF NOT EXISTS maps (
    map_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    location TEXT NOT NULL,
    counter INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
)
)
"""
conn.commit()


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="pages")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="login.html"
)

@app.get("/forgotpassword")
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="Forgot.html"
)

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
    conn.commit()
    
    return templates.TemplateResponse(
        request=request,
        name="Dashboard.html" 
    )


@app.post("/login")
async def login(
    request: Request,  
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    remember_me: Optional[bool] = Form(False)
):
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

    return templates.TemplateResponse(
        request=request,
        name="Dashboard.html"
    )