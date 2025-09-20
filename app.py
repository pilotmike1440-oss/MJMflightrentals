import os, sqlite3, smtplib
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, role TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, message TEXT, created_at TEXT)")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    ("owner", generate_password_hash("ChangeMeNow!123"), "admin"))
        conn.commit()
    conn.close()

def send_email(name, phone, msg):
    server = os.getenv("SMTP_SERVER")
    if not server: return
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USERNAME")
    pw = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")
    email_from = os.getenv("EMAIL_FROM", user)
    subject = "New MJM Rental Flights Message"
    body = f"Name: {name}\nPhone: {phone}\nMessage: {msg}\nTime: {datetime.now()}"
    message = MIMEText(body)
    message["From"] = email_from
    message["To"] = email_to
    message["Subject"] = subject
    with smtplib.SMTP(server, port) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(message)

@app.context_processor
def inject_year():
    return {"year": datetime.now().year}

@app.route("/")
def index(): return render_template("index.html", title="Home")

@app.route("/fleet")
def fleet(): return render_template("fleet.html", title="Fleet")

@app.route("/about")
def about(): return render_template("about.html", title="About")

@app.route("/contact", methods=["GET","POST"])
def contact():
    success=False
    if request.method=="POST":
        name=request.form["name"]; phone=request.form["phone"]; msg=request.form["message"]
        conn=get_db(); cur=conn.cursor()
        cur.execute("INSERT INTO messages (name,phone,message,created_at) VALUES (?,?,?,?)",
                    (name,phone,msg,datetime.now().isoformat()))
        conn.commit(); conn.close()
        try: send_email(name,phone,msg)
        except: pass
        success=True
    return render_template("contact.html", title="Contact", success=success)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a,**k):
        if not session.get("user_id"): return redirect(url_for("admin_login"))
        return f(*a,**k)
    return wrap

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    error=None
    if request.method=="POST":
        u=request.form["username"]; p=request.form["password"]
        conn=get_db(); cur=conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=?",(u,)); row=cur.fetchone(); conn.close()
        if row and check_password_hash(row["password_hash"],p):
            session["user_id"]=row["id"]; session["username"]=row["username"]
            return redirect(url_for("admin_messages"))
        else: error="Invalid login"
    return render_template("admin/login.html", error=error, title="Login")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin/messages")
@login_required
def admin_messages():
    conn=get_db(); cur=conn.cursor()
    cur.execute("SELECT * FROM messages ORDER BY id DESC"); rows=[dict(r) for r in cur.fetchall()]; conn.close()
    return render_template("admin/messages.html", messages=rows, title="Messages")

if __name__=="__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
