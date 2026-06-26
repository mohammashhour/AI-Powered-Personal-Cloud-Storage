from typing import Optional
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3

DB_PATH = "app.db"

# ----------------- SQLITE SETUP -----------------

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL
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
async def login(
    request: Request, 
    username: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    remember_me: Optional[bool] = Form(False)
):

    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"name: {name}")
    print(f"Password: {email}")
    
    return {"message": "signup successful"}


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
            context={"error": "Username and password are required"}
        )

    print(f"Username: {username}")
    print(f"Password: {password}")
    
    return {"message": "Login successful"}
