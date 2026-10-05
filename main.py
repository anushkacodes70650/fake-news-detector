"""Nominators - browser-based real-estate management system."""

import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.getenv("DATABASE_PATH", BASE_DIR / "nominators.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
app.config["DATABASE"] = str(DATABASE)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN', 'MANAGER', 'TENANT')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            address TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            rent REAL NOT NULL CHECK(rent >= 0),
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
            tenant_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(property_id, tenant_id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            read_at TEXT
        );
        CREATE TABLE IF NOT EXISTS agreements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER UNIQUE NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            monthly_rent REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
        );
        """
    )
    admin = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not admin:
        db.execute(
            "INSERT INTO users(name, username, password, role) VALUES (?, ?, ?, ?)",
            ("System Admin", "admin", generate_password_hash("admin123"), "ADMIN"),
        )
    db.commit()


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def current_user():
    user_id = session.get("user_id")
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] not in roles:
                return jsonify(error="You do not have permission to perform this action."), 403
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {"user": current_user(), "year": datetime.now().year}


@app.route("/")
def home():
    db = get_db()
    properties = db.execute(
        """SELECT p.*, u.name AS manager_name FROM properties p
           JOIN users u ON u.id = p.manager_id
           WHERE p.status = 'APPROVED' ORDER BY p.created_at DESC"""
    ).fetchall()
    return render_template("index.html", properties=properties)


@app.post("/register")
def register():
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "TENANT").upper()
    if not name or not username or len(password) < 6 or role not in ("MANAGER", "TENANT"):
        flash("Use a name, username, six-character password, and valid role.", "error")
        return redirect(url_for("home"))
    try:
        db = get_db()
        db.execute(
            "INSERT INTO users(name, username, password, role) VALUES (?, ?, ?, ?)",
            (name, username, generate_password_hash(password), role),
        )
        db.commit()
        flash("Account created. You can now sign in.", "success")
    except sqlite3.IntegrityError:
        flash("That username is already registered.", "error")
    return redirect(url_for("home"))


@app.post("/login")
def login():
    username = request.form.get("username", "").strip().lower()
    account = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not account or not check_password_hash(account["password"], request.form.get("password", "")):
        flash("Invalid username or password.", "error")
        return redirect(url_for("home"))
    session.clear()
    session["user_id"] = account["id"]
    return redirect(url_for("dashboard"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    db = get_db()
    account = current_user()
    if account["role"] == "ADMIN":
        properties = db.execute(
            """SELECT p.*, u.name AS manager_name FROM properties p JOIN users u ON u.id=p.manager_id
               ORDER BY p.created_at DESC"""
        ).fetchall()
        applications = db.execute(
            """SELECT a.*, p.title, u.name AS tenant_name FROM applications a
               JOIN properties p ON p.id=a.property_id JOIN users u ON u.id=a.tenant_id
               ORDER BY a.created_at DESC"""
        ).fetchall()
    elif account["role"] == "MANAGER":
        properties = db.execute(
            "SELECT * FROM properties WHERE manager_id = ? ORDER BY created_at DESC", (account["id"],)
        ).fetchall()
        applications = db.execute(
            """SELECT a.*, p.title, u.name AS tenant_name FROM applications a
               JOIN properties p ON p.id=a.property_id JOIN users u ON u.id=a.tenant_id
               WHERE p.manager_id = ? ORDER BY a.created_at DESC""", (account["id"],)
        ).fetchall()
    else:
        properties = db.execute(
            """SELECT p.*, u.name AS manager_name FROM properties p JOIN users u ON u.id=p.manager_id
               WHERE p.status='APPROVED' ORDER BY p.created_at DESC"""
        ).fetchall()
        applications = db.execute(
            """SELECT a.*, p.title FROM applications a JOIN properties p ON p.id=a.property_id
               WHERE a.tenant_id = ? ORDER BY a.created_at DESC""", (account["id"],)
        ).fetchall()
    stats = {
        "properties": db.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM properties WHERE status='PENDING'").fetchone()[0],
        "applications": db.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
    }
    return render_template("dashboard.html", properties=properties, applications=applications, stats=stats)


@app.post("/properties")
@roles_required("MANAGER")
def create_property():
    data = request.form
    try:
        rent = float(data.get("rent", ""))
        title = data.get("title", "").strip()
        address = data.get("address", "").strip()
        if rent < 0 or not title or not address:
            raise ValueError
        get_db().execute(
            "INSERT INTO properties(manager_id,title,address,description,rent) VALUES(?,?,?,?,?)",
            (current_user()["id"], title, address,
             data.get("description", "").strip(), rent),
        )
        get_db().commit()
        flash("Property submitted for admin approval.", "success")
    except (ValueError, TypeError):
        flash("Enter a valid title, address, and non-negative rent.", "error")
    return redirect(url_for("dashboard"))


@app.post("/properties/<int:property_id>/status")
@roles_required("ADMIN")
def property_status(property_id):
    status = request.form.get("status", "").upper()
    if status not in ("APPROVED", "REJECTED", "PENDING"):
        return jsonify(error="Invalid property status."), 400
    get_db().execute("UPDATE properties SET status=? WHERE id=?", (status, property_id))
    get_db().commit()
    return redirect(url_for("dashboard"))


@app.post("/properties/<int:property_id>/delete")
@roles_required("MANAGER", "ADMIN")
def delete_property(property_id):
    property_row = get_db().execute("SELECT manager_id FROM properties WHERE id=?", (property_id,)).fetchone()
    if not property_row or (current_user()["role"] == "MANAGER" and property_row["manager_id"] != current_user()["id"]):
        return jsonify(error="Property not found or not owned by you."), 404
    get_db().execute("DELETE FROM properties WHERE id=?", (property_id,))
    get_db().commit()
    return redirect(url_for("dashboard"))


@app.post("/applications")
@roles_required("TENANT")
def apply_property():
    property_id = request.form.get("property_id")
    try:
        property_row = get_db().execute(
            "SELECT id FROM properties WHERE id=? AND status='APPROVED'", (int(property_id),)
        ).fetchone()
        if not property_row:
            raise ValueError
        get_db().execute(
            "INSERT INTO applications(property_id, tenant_id) VALUES (?, ?)",
            (property_row["id"], current_user()["id"]),
        )
        get_db().commit()
        flash("Application submitted.", "success")
    except (sqlite3.IntegrityError, TypeError, ValueError):
        flash("You have already applied or the property is unavailable.", "error")
    return redirect(url_for("dashboard"))


@app.post("/applications/<int:application_id>/status")
@roles_required("ADMIN", "MANAGER")
def application_status(application_id):
    status = request.form.get("status", "").upper()
    if status not in ("APPROVED", "REJECTED", "PENDING"):
        return jsonify(error="Invalid application status."), 400
    db = get_db()
    application = db.execute(
        """SELECT a.*, p.manager_id FROM applications a JOIN properties p ON p.id=a.property_id
           WHERE a.id=?""", (application_id,)
    ).fetchone()
    if not application or (current_user()["role"] == "MANAGER" and application["manager_id"] != current_user()["id"]):
        return jsonify(error="Application not found or not accessible."), 404
    db.execute("UPDATE applications SET status=? WHERE id=?", (status, application_id))
    db.commit()
    return redirect(url_for("dashboard"))


@app.post("/messages")
@roles_required("MANAGER", "TENANT")
def send_message():
    receiver = request.form.get("receiver_id")
    body = request.form.get("body", "").strip()
    if not receiver or not body:
        flash("Choose a recipient and enter a message.", "error")
    else:
        try:
            recipient = get_db().execute("SELECT id FROM users WHERE id=?", (int(receiver),)).fetchone()
            if not recipient:
                raise ValueError
            get_db().execute("INSERT INTO messages(sender_id,receiver_id,body) VALUES(?,?,?)",
                             (current_user()["id"], recipient["id"], body))
            get_db().commit()
            flash("Message sent.", "success")
        except (ValueError, TypeError):
            flash("That recipient does not exist.", "error")
    return redirect(url_for("dashboard"))


@app.get("/api/properties")
def api_properties():
    rows = get_db().execute(
        """SELECT p.id,p.title,p.address,p.description,p.rent,p.status,u.name manager
           FROM properties p JOIN users u ON u.id=p.manager_id WHERE p.status='APPROVED'
           ORDER BY p.created_at DESC"""
    ).fetchall()
    return jsonify([dict(row) for row in rows])


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
