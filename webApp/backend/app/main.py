import os
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from dotenv import load_dotenv
import requests

app = FastAPI()

LOGGER_URL = os.environ.get("LOGGER_URL", "http://logger:9000/log")
UPLOAD_DIR = "/app/uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

load_dotenv()

POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_DB = os.environ.get("POSTGRES_DB")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="/app/app/templates")
app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")


def connect_db():
    for _ in range(5):
        try:
            return psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
        except:
            time.sleep(2)
    raise Exception("Не удалось подключиться к базе")


def get_conn():
    return connect_db()


def log_action(action: str, details: str = ""):
    try:
        requests.post(LOGGER_URL, json={"action": action, "details": details})
    except:
        pass



@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",
                (username, password))
    user = cur.fetchone()
    cur.close()

    if not user:
        log_action("login_failed", f"Пользователь: {username}")
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный логин или пароль"})

    log_action("login_success", f"Пользователь: {username}")
    return RedirectResponse("/files", status_code=302)


@app.get("/files", response_class=HTMLResponse)
def files_page(request: Request):
    files = os.listdir(UPLOAD_DIR)
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.get("/list-files")
def list_files():
    files = os.listdir(UPLOAD_DIR)
    log_action("list_files", f"{len(files)} файлов")
    return {"files": files}

@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    uploaded_files = []
    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024*1024):
                f.write(chunk)
        uploaded_files.append(file.filename)
    log_action("upload", f"Файлы: {', '.join(uploaded_files)}")
    return {"status": "ok"}

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        log_action("download_failed", f"Файл: {filename}")
        raise HTTPException(status_code=404, detail="Файл не найден")
    log_action("download", f"Файл: {filename}")
    return FileResponse(file_path, filename=filename)

@app.delete("/delete/{filename}")
def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        log_action("delete", f"Файл: {filename}")
        return {"status": "deleted"}
    else:
        log_action("delete_failed", f"Файл: {filename}")
        raise HTTPException(status_code=404, detail="Файл не найден")


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    users = [dict(zip(cols, r)) for r in rows]
    cur.close()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.put("/users/{user_id}")
def update_user_api(user_id: int, data: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET username=%s, password=%s, fullname=%s, company=%s, position=%s
        WHERE id=%s
    """, (data["username"], data["password"], data["fullname"],
          data["company"], data["position"], user_id))
    conn.commit()
    cur.close()
    log_action("update_user", f"id={user_id}, username={data['username']}")
    return {"status": "updated"}

@app.delete("/users/{user_id}")
def delete_user_api(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    log_action("delete_user", f"id={user_id}")
    return {"status": "deleted"}



