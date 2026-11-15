"""CarePath AI Stage 2: demo authentication and role-based dashboards.

This is an educational prototype. It is not a production healthcare system.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
import os
import re
import secrets
import sqlite3
import sys

from flask import (
    Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "carepath.db"

app = Flask(__name__)
secret_key = os.environ.get("CAREPATH_SECRET_KEY")
if not secret_key:
    # Convenient for local learning only. This changes every restart.
    secret_key = secrets.token_urlsafe(48)
    print("WARNING: CAREPATH_SECRET_KEY is not set. A temporary development key is in use.")
    print("Set CAREPATH_SECRET_KEY before relying on persistent sessions or deploying.")

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("CAREPATH_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    WTF_CSRF_TIME_LIMIT=3600,
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)
csrf = CSRFProtect(app)

# These entries are illustrative. Replace them only with authorized, verified feeds.
HOSPITALS = [
    {"id": 1, "name": "City Care Hospital", "area": "Central Bengaluru", "specialty": "Multi-speciality", "queue": 4, "avg_minutes": 8},
    {"id": 2, "name": "GreenLife Medical Centre", "area": "Indiranagar", "specialty": "General & Emergency", "queue": 7, "avg_minutes": 6},
    {"id": 3, "name": "Sunrise Health Clinic", "area": "Jayanagar", "specialty": "Family Medicine", "queue": 2, "avg_minutes": 12},
]
HOSPITAL_BY_ID = {hospital["id"]: hospital for hospital in HOSPITALS}


@contextmanager
def db():
    """Open and reliably close a SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_column_if_missing(conn, table, column, definition):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    """Create Stage 2 tables and safely extend the Stage 1 database."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('patient', 'pending_doctor', 'doctor')),
                hospital_id INTEGER,
                professional_id TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Stage 1 tables are retained. Old rows remain available as legacy demo data.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                hospital_id INTEGER NOT NULL,
                preferred_time TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emergency_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                location TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Additive migration: existing Stage 1 appointment data is not deleted.
        add_column_if_missing(conn, "appointments", "patient_user_id", "INTEGER")
        add_column_if_missing(conn, "appointments", "status", "TEXT NOT NULL DEFAULT 'requested'")
        add_column_if_missing(conn, "emergency_requests", "patient_user_id", "INTEGER")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_appointments_hospital ON appointments(hospital_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        with db() as conn:
            row = conn.execute(
                "SELECT id, full_name, email, phone, role, hospital_id, professional_id "
                "FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            session.clear()
        else:
            g.user = dict(row)


@app.context_processor
def inject_user():
    return {"current_user": g.get("user")}


def wants_json():
    return request.path.startswith("/api/") or request.is_json


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if wants_json():
                return jsonify({"error": "Please sign in to continue."}), 401
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in allowed_roles:
                if wants_json():
                    return jsonify({"error": "You do not have permission to access this resource."}), 403
                if g.user["role"] == "pending_doctor":
                    return redirect(url_for("doctor_pending"))
                flash("Your account does not have access to that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def clean_phone(value):
    return re.sub(r"[\s()+-]", "", value or "")


def valid_password(password):
    return (
        len(password) >= 10
        and any(char.isalpha() for char in password)
        and any(char.isdigit() for char in password)
    )


@app.get("/")
def home():
    return render_template("index.html", hospitals=HOSPITALS)


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        requested_role = request.form.get("role", "patient")
        hospital_raw = request.form.get("hospital_id", "")
        professional_id = request.form.get("professional_id", "").strip()

        if len(full_name) < 2 or len(full_name) > 80:
            flash("Enter a name between 2 and 80 characters.", "error")
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            flash("Enter a valid email address.", "error")
        elif not (7 <= len(clean_phone(phone)) <= 15 and clean_phone(phone).isdigit()):
            flash("Enter a valid phone number (7 to 15 digits).", "error")
        elif len(password) > 128 or not valid_password(password):
            flash("Use 10 to 128 characters, including a letter and a number.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif requested_role not in ("patient", "doctor"):
            flash("Choose a valid account type.", "error")
        else:
            hospital_id = None
            role = "patient"
            if requested_role == "doctor":
                try:
                    hospital_id = int(hospital_raw)
                except (TypeError, ValueError):
                    hospital_id = None
                if hospital_id not in HOSPITAL_BY_ID or not professional_id:
                    flash("Doctors must choose a sample hospital and enter a professional registration ID.", "error")
                    return render_template("register.html", hospitals=HOSPITALS)
                # Never grant doctor permissions just because someone selected Doctor.
                role = "pending_doctor"

            try:
                with db() as conn:
                    conn.execute(
                        """INSERT INTO users
                           (full_name, email, phone, password_hash, role, hospital_id, professional_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            full_name,
                            email,
                            phone,
                            generate_password_hash(password),
                            role,
                            hospital_id,
                            professional_id if requested_role == "doctor" else None,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                if role == "pending_doctor":
                    flash("Doctor application created. Your account is pending manual verification and approval.", "success")
                else:
                    flash("Patient account created. You can now sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")

    return render_template("register.html", hospitals=HOSPITALS)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            # Same message avoids revealing whether an email is registered.
            flash("Email or password is incorrect.", "error")
        else:
            session.clear()  # Avoid carrying an old session into a new login.
            session.permanent = True
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    if g.user["role"] == "patient":
        return redirect(url_for("patient_dashboard"))
    if g.user["role"] == "doctor":
        return redirect(url_for("doctor_dashboard"))
    return redirect(url_for("doctor_pending"))


@app.get("/patient/dashboard")
@role_required("patient")
def patient_dashboard():
    with db() as conn:
        rows = conn.execute(
            """SELECT id, hospital_id, preferred_time, created_at, status
               FROM appointments WHERE patient_user_id = ? ORDER BY id DESC""",
            (g.user["id"],),
        ).fetchall()
    appointments = []
    for row in rows:
        item = dict(row)
        item["hospital_name"] = HOSPITAL_BY_ID.get(item["hospital_id"], {}).get("name", "Unknown hospital")
        appointments.append(item)
    return render_template("patient_dashboard.html", hospitals=HOSPITALS, appointments=appointments)


@app.get("/doctor/pending")
@role_required("pending_doctor")
def doctor_pending():
    hospital_name = HOSPITAL_BY_ID.get(g.user["hospital_id"], {}).get("name", "Selected hospital")
    return render_template("doctor_pending.html", hospital_name=hospital_name)


@app.get("/doctor/dashboard")
@role_required("doctor")
def doctor_dashboard():
    hospital_id = g.user["hospital_id"]
    with db() as conn:
        rows = conn.execute(
            """SELECT id, patient_name, preferred_time, created_at, status
               FROM appointments WHERE hospital_id = ? AND patient_user_id IS NOT NULL
               ORDER BY id DESC""",
            (hospital_id,),
        ).fetchall()
    return render_template(
        "doctor_dashboard.html",
        appointments=[dict(row) for row in rows],
        hospital_name=HOSPITAL_BY_ID.get(hospital_id, {}).get("name", "Your hospital"),
    )


@app.get("/api/hospitals")
def hospitals():
    return jsonify({"demo": True, "hospitals": HOSPITALS})


@app.get("/api/queue/<int:hospital_id>")
def queue(hospital_id):
    hospital = HOSPITAL_BY_ID.get(hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found."}), 404
    estimated = hospital["queue"] * hospital["avg_minutes"]
    return jsonify({
        "demo": True,
        "hospital_id": hospital_id,
        "people_waiting": hospital["queue"],
        "estimated_wait_minutes": estimated,
        "message": "Illustrative sample only; this is not a live queue or a clinical prediction. Confirm directly with the hospital.",
    })


@app.post("/api/appointments")
@role_required("patient")
def create_appointment():
    data = request.get_json(silent=True) or request.form
    try:
        hospital_id = int(data.get("hospital_id", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "Choose a valid hospital."}), 400

    preferred_time = str(data.get("preferred_time", "")).strip()
    if hospital_id not in HOSPITAL_BY_ID or not preferred_time:
        return jsonify({"error": "Choose a hospital and preferred date/time."}), 400
    if len(preferred_time) > 40:
        return jsonify({"error": "The preferred date/time is invalid."}), 400

    with db() as conn:
        cursor = conn.execute(
            """INSERT INTO appointments
               (patient_name, phone, hospital_id, preferred_time, created_at, patient_user_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'requested')""",
            (
                g.user["full_name"],
                g.user["phone"],
                hospital_id,
                preferred_time,
                datetime.now(timezone.utc).isoformat(),
                g.user["id"],
            ),
        )
        appointment_id = cursor.lastrowid

    return jsonify({
        "success": True,
        "appointment_id": appointment_id,
        "message": "Demo appointment request saved. It is not a confirmed hospital booking.",
    }), 201


@app.get("/api/doctor/appointments")
@role_required("doctor")
def doctor_appointments_api():
    with db() as conn:
        rows = conn.execute(
            """SELECT id, patient_name, preferred_time, created_at, status
               FROM appointments WHERE hospital_id = ? AND patient_user_id IS NOT NULL
               ORDER BY id DESC""",
            (g.user["hospital_id"],),
        ).fetchall()
    return jsonify({"demo": True, "appointments": [dict(row) for row in rows]})


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    if not request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def approve_doctor(email):
    """Local machine-owner command after off-platform credential verification."""
    with db() as conn:
        cursor = conn.execute(
            "UPDATE users SET role = 'doctor' WHERE email = ? COLLATE NOCASE AND role = 'pending_doctor'",
            (email.strip(),),
        )
    if cursor.rowcount:
        print(f"Approved doctor account: {email}")
        print("The account can now access only its selected hospital's demo dashboard.")
    else:
        print("No pending doctor account found for that email.")


def list_pending_doctors():
    with db() as conn:
        rows = conn.execute(
            "SELECT full_name, email, professional_id, hospital_id FROM users WHERE role = 'pending_doctor' ORDER BY id"
        ).fetchall()
    if not rows:
        print("No pending doctor accounts.")
        return
    for row in rows:
        hospital_name = HOSPITAL_BY_ID.get(row["hospital_id"], {}).get("name", "Unknown hospital")
        print(f"{row['full_name']} | {row['email']} | ID: {row['professional_id']} | {hospital_name}")


# Ensure the schema is ready both for local execution and WSGI imports.
init_db()

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "approve-doctor":
        if len(sys.argv) != 3:
            print("Usage: py app.py approve-doctor doctor@example.com")
            raise SystemExit(2)
        approve_doctor(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "list-pending-doctors":
        list_pending_doctors()
    else:
        # Local development only. Use a production WSGI server for deployment.
        app.run(debug=False, host="127.0.0.1", port=5000)
