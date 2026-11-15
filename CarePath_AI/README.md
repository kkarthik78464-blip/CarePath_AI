# CarePath AI — Stage 2 (authentication + role-based dashboards)

A beginner-friendly educational prototype built with HTML, CSS, JavaScript, Python Flask and SQLite. This update adds patient registration/login, pending doctor registration, password hashing, CSRF protection, role-based route protection and separate patient/doctor dashboards.

> **Important:** This is still a demo, not a production healthcare service. The hospital names and queue estimates are illustrative sample data. Appointment requests are not confirmed bookings. The app does not contact hospitals, ambulances or emergency services. Do not enter real patient health information.

## 1. Requirements
- Windows 10/11
- Python 3.10 or newer
- Internet connection for the first package installation

## 2. Replace your Stage 1 project
1. Extract the Stage 2 ZIP.
2. Open the extracted `CarePath_AI` folder.
3. If you already have Stage 1, copy the new `app.py`, `requirements.txt`, `README.md`, `.gitignore`, `templates` folder and `static` folder over the old project. Keep a backup first.
4. The old `carepath.db` is preserved. The app adds the new user table and adds appointment ownership/status columns without deleting existing demo rows.

## 3. Run on Windows (PowerShell)
Open PowerShell in the `CarePath_AI` folder and run these commands one at a time:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:CAREPATH_SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
python app.py
```

If PowerShell blocks virtual-environment activation, use Command Prompt instead:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
set CAREPATH_SECRET_KEY=replace-this-with-a-long-random-secret
python app.py
```

Open **http://127.0.0.1:5000** in your browser. Keep the terminal window open while testing.

The PowerShell secret command creates a random key for that terminal session. If you close the terminal, create/set the key again; existing sessions will sign out. For a stable local setup, keep a long random value in your own private environment configuration. Never publish it or commit it to Git.

## 4. Test patient registration and login
1. Click **Create account**.
2. Select **Patient**.
3. Enter your name, email, phone and a password of at least 10 characters containing a letter and a number.
4. Submit, then sign in with that email and password.
5. You should reach the **Patient dashboard**.
6. Submit a sample appointment request. Refresh the dashboard to see the saved request.
7. Sign out. Try opening `/patient/dashboard` in a private/incognito window; it should redirect you to sign in.

Passwords are stored as Werkzeug password hashes, not as plain text. The app does not provide a password-recovery flow in this stage.

## 5. Test doctor registration and approval
Doctor registration is deliberately **not auto-approved**. Anyone can type a professional ID into a form; that does not prove they are a licensed doctor. The account is stored as `pending_doctor` and cannot open the doctor dashboard until the project owner verifies credentials outside the app.

1. Sign out and create another account.
2. Select **Doctor / healthcare professional**.
3. Choose one of the sample hospitals and enter a test professional registration ID.
4. Register and sign in. You should see the **Pending approval** page, not the doctor dashboard.
5. Stop the server with `Ctrl+C`.
6. In the same project folder and virtual environment, list pending applications:

```powershell
python app.py list-pending-doctors
```

7. Only after you have independently verified the person's credentials and their authorization to access the selected hospital's data, approve the account:

```powershell
python app.py approve-doctor doctor@example.com
```

8. Start the server again with `python app.py`, sign in as that doctor and open the doctor dashboard. It only displays patient-linked demo appointment requests associated with that doctor's assigned sample hospital.

This command is a local prototype approval mechanism, not a verified medical-credential integration. Do not approve fake/test credentials for a real deployment.


## 6. Test on Android
The site is responsive and includes a PWA manifest, service worker and app icons. For a quick phone preview on the same Wi-Fi network:

1. On your computer, stop the server with `Ctrl+C`.
2. Change the final `app.run(...)` line in `app.py` to `app.run(debug=False, host="0.0.0.0", port=5000)`.
3. Start the server again with `python app.py`.
4. Run `ipconfig` on Windows and note your computer's IPv4 address.
5. On your Android phone, open `http://YOUR-COMPUTER-IP:5000` in Chrome. Both devices must be on the same Wi-Fi.

This LAN HTTP address is for local testing only. For actual **Install app** / Add to Home Screen testing, deploy behind HTTPS; browsers generally require HTTPS for PWA installation. Do not expose Flask's built-in development server to the public internet. Set `CAREPATH_HTTPS=1` only when the app is genuinely served through HTTPS, otherwise secure cookies will not be sent over local HTTP.

## 7. What changed in the database
- Added `users` with unique email, profile fields, role and `password_hash`.
- Added `patient_user_id` and `status` to the existing `appointments` table.
- Added an index for patient-owned appointments and hospital-scoped doctor requests.
- Existing Stage 1 appointments are kept as legacy demo rows. They are not automatically assigned to a patient account.
- SQLite is suitable for local learning only; choose a managed database and backup strategy before production.

## 8. Security included in this stage
- Werkzeug password hashing and password verification.
- Patient, pending-doctor and doctor roles.
- Server-side authorization on dashboard routes and appointment APIs.
- Doctors can view only patient-linked demo requests for their assigned sample hospital.
- CSRF tokens on forms and the appointment API.
- HTTP-only, SameSite session cookies and a 30-minute session lifetime.
- Session cleared on login/logout; no-store headers on dynamic pages; basic security headers.
- Service worker caches static assets only, not authenticated pages or API responses.
- PWA manifest includes 192px and 512px app icons for install testing.

## 9. Known limitations before production
This is not yet suitable for real patients or clinical operations. Before any real-world launch, obtain professional security, privacy, legal and clinical review; use HTTPS and a production WSGI server; set and rotate strong secrets; add login throttling, account recovery, MFA, audit trails, monitoring, secure backups and tested incident response; validate all inputs; establish consent, retention and deletion policies; review applicable Indian data-protection and healthcare requirements; and integrate only with hospitals that have explicitly authorized the data sharing. Doctor identity and registration must be verified through an appropriate authoritative process. Use validated traffic/map feeds and live queue data only after contracts and integrations are in place.

For an emergency in India, call **112** or your local emergency service directly. CarePath AI does not dispatch help.
