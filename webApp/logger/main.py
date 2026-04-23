import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import psycopg2

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def get_conn():
    return psycopg2.connect(
        host=os.getenv("LOGGER_POSTGRES_HOST"),
        database=os.getenv("LOGGER_POSTGRES_DB"),
        user=os.getenv("LOGGER_POSTGRES_USER"),
        password=os.getenv("LOGGER_POSTGRES_PASSWORD")
    )

@app.get("/logs")
def logs_page(request: Request):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, action, details, created_at FROM logs ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    logs = [{"id": r[0], "action": r[1], "details": r[2], "created_at": r[3]} for r in rows]
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})

@app.post("/log")
async def add_log(request: Request):
    data = await request.json()
    action = data.get("action", "")
    details = data.get("details", "")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO logs (action, details) VALUES (%s, %s)", (action, details))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "ok"}
