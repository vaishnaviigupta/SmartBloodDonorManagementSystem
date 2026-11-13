from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from io import BytesIO
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook
import os
import uuid
from werkzeug.utils import secure_filename
from flask import send_from_directory, abort

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, "private_uploads")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Secret key for login session
app.secret_key = "smart_blood_donor_secret"


# =========================
# MYSQL CONNECTION
# =========================

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="smart_blood_donor"
)

cursor = db.cursor()


# =========================
# GET STATISTICS
# =========================

def get_statistics():
    cursor.execute("SELECT COUNT(*) FROM donors")
    total_donors = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT city) FROM donors")
    total_cities = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT blood_group) FROM donors")
    total_blood_groups = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM blood_requests")
    total_requests = cursor.fetchone()[0]

    return total_donors, total_requests, total_cities, total_blood_groups

# =========================
# HOME
# =========================
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )
@app.route("/")
def home():

    total_donors, total_requests, total_cities, total_blood_groups = get_statistics()

    return render_template(
        "index.html",
        total_donors=total_donors,
        total_requests=total_requests,
        total_cities=total_cities,
        total_blood_groups=total_blood_groups
    )


# =========================
# ABOUT
# =========================

@app.route("/about")
def about():
    return render_template("about.html")


# =========================
# CONTACT
# =========================

@app.route("/contact")
def contact():
    return render_template("contact.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":

            session["logged_in"] = True
            session["username"] = username

            return redirect("/dashboard")

        else:

            return render_template(
                "login.html",
                error="Invalid username or password."
            )

    return render_template("login.html")


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):
        return redirect("/login")

    total_donors, total_requests, total_cities, total_blood_groups = get_statistics()

    return render_template(
        "dashboard.html",
        total_donors=total_donors,
        total_requests=total_requests,
        total_cities=total_cities,
        total_blood_groups=total_blood_groups
    )
# =========================
# ANALYTICS DASHBOARD
# =========================

@app.route("/analytics")
def analytics():

    if not session.get("logged_in"):
        return redirect("/login")

    # Donor statistics by blood group
    cursor.execute("""
        SELECT blood_group, COUNT(*)
        FROM donors
        GROUP BY blood_group
    """)
    blood_group_data = cursor.fetchall()

    blood_groups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    donor_counts = {group: 0 for group in blood_groups}

    for group, count in blood_group_data:
        if group in donor_counts:
            donor_counts[group] = count

    # Blood request status statistics
    cursor.execute("""
        SELECT request_status, COUNT(*)
        FROM blood_requests
        GROUP BY request_status
    """)
    request_status_data = cursor.fetchall()

    statuses = ["Pending", "Approved", "Rejected", "Completed"]
    status_counts = {status: 0 for status in statuses}

    for status, count in request_status_data:
        if status in status_counts:
            status_counts[status] = count

    # Hospital statistics
    cursor.execute("""
        SELECT approval_status, COUNT(*)
        FROM hospitals
        GROUP BY approval_status
    """)
    hospital_data = cursor.fetchall()

    hospital_statuses = ["Pending", "Approved", "Rejected"]
    hospital_counts = {status: 0 for status in hospital_statuses}

    for status, count in hospital_data:
        if status in hospital_counts:
            hospital_counts[status] = count

    return render_template(
        "analytics.html",
        blood_group_labels=blood_groups,
        blood_group_counts=[donor_counts[g] for g in blood_groups],
        request_status_labels=statuses,
        request_status_counts=[status_counts[s] for s in statuses],
        hospital_status_labels=hospital_statuses,
        hospital_status_counts=[hospital_counts[s] for s in hospital_statuses]
    )
# =========================
# MANAGE HOSPITALS
# =========================
@app.route("/manage-hospitals")
def manage_hospitals():

    if not session.get("logged_in"):
        return redirect("/login")

    cursor.execute("""
        SELECT id, hospital_name, city, address, phone,
               email, approval_status
        FROM hospitals
        ORDER BY id DESC
    """)

    hospitals = cursor.fetchall()

    return render_template(
        "manage_hospitals.html",
        hospitals=hospitals
    )


# =========================
# APPROVE OR REJECT HOSPITAL
# =========================

@app.route("/hospital-status/<int:hospital_id>", methods=["POST"])
def update_hospital_status(hospital_id):

    if not session.get("logged_in"):
        return redirect("/login")

    status = request.form.get("status")

    if status not in ["Approved", "Rejected", "Pending"]:
        return redirect("/manage-hospitals")

    cursor.execute(
        "UPDATE hospitals SET approval_status=%s WHERE id=%s",
        (status, hospital_id)
    )
    db.commit()

    return redirect("/manage-hospitals")

@app.route("/manage-blood-requests")
def manage_blood_requests():
    if not session.get("logged_in"):
        return redirect("/login")

    cursor.execute("""
        SELECT br.id, h.hospital_name, h.city,
               br.blood_group, br.units_needed,
               br.required_date, br.urgency,
               br.notes, br.request_status
        FROM blood_requests br
        JOIN hospitals h ON br.hospital_id = h.id
        ORDER BY br.id DESC
    """)
    requests_list = cursor.fetchall()

    return render_template(
        "manage_blood_requests.html",
        requests_list=requests_list
    )


@app.route("/blood-request-status/<int:request_id>", methods=["POST"])
def update_blood_request_status(request_id):
    if not session.get("logged_in"):
        return redirect("/login")

    status = request.form.get("status")

    if status not in ["Pending", "Approved", "Rejected", "Completed"]:
        return redirect("/manage-blood-requests")

    cursor.execute(
        "UPDATE blood_requests SET request_status=%s WHERE id=%s",
        (status, request_id)
    )
    db.commit()

    return redirect("/manage-blood-requests")
# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")
# =========================
# HOSPITAL REGISTRATION
# =========================

@app.route("/hospital-register", methods=["GET", "POST"])
def hospital_register():

    if request.method == "POST":
        hospital_name = request.form.get("hospital_name", "").strip()
        city = request.form.get("city", "").strip()
        address = request.form.get("address", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not all([hospital_name, city, address, phone, email, password]):
            return render_template(
                "hospital_register.html",
                error="Please fill in all required fields."
            )

        if len(password) < 8:
            return render_template(
                "hospital_register.html",
                error="Password must contain at least 8 characters."
            )

        password_hash = generate_password_hash(password)

        try:
            cursor.execute(
                """
                INSERT INTO hospitals
                (hospital_name, city, address, contact_person,
                 phone, email, password_hash, approval_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
                """,
                (
                    hospital_name, city, address, contact_person,
                    phone, email, password_hash
                )
            )
            db.commit()

            return render_template(
                "hospital_register.html",
                success="Registration submitted! Wait for admin approval."
            )

        except mysql.connector.IntegrityError:
            db.rollback()
            return render_template(
                "hospital_register.html",
                error="This email is already registered."
            )

        except mysql.connector.Error:
            db.rollback()
            return render_template(
                "hospital_register.html",
                error="Database error. Please try again."
            )

    return render_template("hospital_register.html")

# =========================
# HOSPITAL LOGIN
# =========================

@app.route("/hospital-login", methods=["GET", "POST"])
def hospital_login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        cursor.execute(
            """
            SELECT id, hospital_name, password_hash, approval_status
            FROM hospitals
            WHERE email = %s
            """,
            (email,)
        )
        hospital = cursor.fetchone()

        if not hospital or not check_password_hash(hospital[2], password):
            return render_template(
                "hospital_login.html",
                error="Invalid email or password."
            )

        if hospital[3] != "Approved":
            return render_template(
                "hospital_login.html",
                error="Your registration is pending admin approval."
            )

        session["hospital_id"] = hospital[0]
        session["hospital_name"] = hospital[1]

        return redirect("/hospital-dashboard")

    return render_template("hospital_login.html")


# =========================
# HOSPITAL DASHBOARD
# =========================

@app.route("/hospital-dashboard")
def hospital_dashboard():

    if not session.get("hospital_id"):
        return redirect("/hospital-login")

    cursor.execute(
        """
        SELECT id, blood_group, units_needed, required_date,
               urgency, request_status, created_at
        FROM blood_requests
        WHERE hospital_id = %s
        ORDER BY id DESC
        """,
        (session["hospital_id"],)
    )

    requests_list = cursor.fetchall()

    return render_template(
        "hospital_dashboard.html",
        hospital_name=session["hospital_name"],
        requests_list=requests_list
    )
# =========================
# SUBMIT BLOOD REQUEST
# =========================

@app.route("/blood-request", methods=["GET", "POST"])
def blood_request():

    if not session.get("hospital_id"):
        return redirect("/hospital-login")

    if request.method == "POST":
        blood_group = request.form.get("blood_group", "").strip()
        units = request.form.get("units_needed", "").strip()
        required_date = request.form.get("required_date", "").strip()
        urgency = request.form.get("urgency", "Normal").strip()
        notes = request.form.get("notes", "").strip()

        allowed_groups = [
            "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
        ]

        if blood_group not in allowed_groups:
            return render_template(
                "blood_request.html",
                error="Please select a valid blood group."
            )

        try:
            units = int(units)
            if units < 1 or units > 100:
                raise ValueError
        except ValueError:
            return render_template(
                "blood_request.html",
                error="Enter a number of units between 1 and 100."
            )

        if not required_date:
            return render_template(
                "blood_request.html",
                error="Please select the required date."
            )

        if urgency not in ["Normal", "Urgent", "Emergency"]:
            urgency = "Normal"

        cursor.execute(
            """
            INSERT INTO blood_requests
            (hospital_id, blood_group, units_needed,
             required_date, urgency, notes, request_status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
            """,
            (
                session["hospital_id"], blood_group, units,
                required_date, urgency, notes
            )
        )
        db.commit()

        return redirect("/hospital-dashboard")

    return render_template("blood_request.html")
# =========================
# HOSPITAL LOGOUT
# =========================

@app.route("/hospital-logout")
def hospital_logout():

    session.pop("hospital_id", None)
    session.pop("hospital_name", None)

    return redirect("/hospital-login")
# =========================
# REGISTER DONOR
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # Check health declaration
        if request.form.get("health_declaration") != "yes":
            flash("Please accept the health declaration.")
            return render_template("register.html")

        name = request.form.get("name")
        age = request.form.get("age")
        blood_group = request.form.get("blood_group")
        city = request.form.get("city")
        phone = request.form.get("phone")
        email = request.form.get("email")
        last_donation = request.form.get("last_donation")

        # Receive optional medical document
        uploaded_file = request.files.get("medical_document")
        saved_filename = None

        if uploaded_file and uploaded_file.filename:

            if not allowed_file(uploaded_file.filename):
                flash("Invalid file type. Upload PDF, JPG, JPEG or PNG.")
                return render_template("register.html")

            # Generate a unique filename
            extension = uploaded_file.filename.rsplit(".", 1)[1].lower()
            saved_filename = secure_filename(
                f"{uuid.uuid4().hex}.{extension}"
            )

            uploaded_file.save(
                os.path.join(UPLOAD_FOLDER, saved_filename)
            )

        query = """
        INSERT INTO donors
        (name, age, blood_group, city, phone, email, last_donation,
         medical_document, medical_verification_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            name,
            age,
            blood_group,
            city,
            phone,
            email,
            last_donation if last_donation else None,
            saved_filename,
            "Pending"
        )

        try:
            cursor.execute(query, values)
            db.commit()

        except Exception:
            db.rollback()

            # Remove uploaded file if database insertion fails
            if saved_filename:
                file_path = os.path.join(UPLOAD_FOLDER, saved_filename)
                if os.path.exists(file_path):
                    os.remove(file_path)

            app.logger.exception("Donor registration failed")
            flash("Registration failed. Please check the details and try again.")
            return render_template("register.html")

        return render_template("success.html", name=name)

    return render_template("register.html")

# =========================
# SEARCH DONOR
# =========================

@app.route("/search", methods=["POST"])
def search():

    blood_group = request.form.get("blood_group")
    city = request.form.get("city")

    if city and city.strip():

        query = """
        SELECT name, age, blood_group, city, phone, email, last_donation
        FROM donors
        WHERE blood_group = %s
        AND city LIKE %s
        """

        values = (
            blood_group,
            "%" + city.strip() + "%"
        )

    else:

        query = """
        SELECT name, age, blood_group, city, phone, email, last_donation
        FROM donors
        WHERE blood_group = %s
        """

        values = (blood_group,)

    cursor.execute(query, values)

    donors = cursor.fetchall()

    total_donors, total_requests, total_cities, total_blood_groups = get_statistics()

    return render_template(
        "index.html",
        donors=donors,
        searched=True,
        blood_group=blood_group,
        city=city,
        total_donors=total_donors,
        total_requests=total_requests,
        total_cities=total_cities,
        total_blood_groups=total_blood_groups
    )


# =========================
# MANAGE DONORS
# =========================
@app.route("/admin/medical-document/<int:donor_id>")
def view_medical_document(donor_id):

    if not session.get("logged_in"):
        flash("Please log in as admin to view medical documents.")
        return redirect("/login")

    cursor.execute(
        "SELECT medical_document FROM donors WHERE id = %s",
        (donor_id,)
    )
    result = cursor.fetchone()

    if not result or not result[0]:
        flash("No medical document is available for this donor.")
        return redirect("/manage-donors")

    filename = os.path.basename(result[0])
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.isfile(file_path):
        flash("The medical document could not be found.")
        return redirect("/manage-donors")

    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=False
    )
@app.route("/update-medical-status/<int:donor_id>", methods=["POST"])
def update_medical_status(donor_id):

    if not session.get("logged_in"):
        flash("Please log in as admin.")
        return redirect("/login")

    status = request.form.get("status")

    if status not in ["Pending", "Verified", "Rejected"]:
        flash("Invalid verification status.")
        return redirect("/manage-donors")

    cursor.execute(
        """
        UPDATE donors
        SET medical_verification_status = %s
        WHERE id = %s
        """,
        (status, donor_id)
    )
    db.commit()

    flash("Medical document review status updated.")
    return redirect("/manage-donors")
@app.route("/manage-donors")
def manage_donors():

    if not session.get("logged_in"):
        return redirect("/login")

    query = """
SELECT id, name, age, blood_group, city, phone, email,
       last_donation, medical_document, medical_verification_status
FROM donors
ORDER BY id DESC
"""

    cursor.execute(query)

    donors = cursor.fetchall()

    return render_template(
        "manage_donors.html",
        donors=donors
    )


# =========================
# EDIT DONOR
# =========================

@app.route("/edit-donor/<int:id>", methods=["GET", "POST"])
def edit_donor(id):

    if not session.get("logged_in"):
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name")
        age = request.form.get("age")
        blood_group = request.form.get("blood_group")
        city = request.form.get("city")
        phone = request.form.get("phone")
        email = request.form.get("email")
        last_donation = request.form.get("last_donation")

        query = """
        UPDATE donors
        SET name=%s,
            age=%s,
            blood_group=%s,
            city=%s,
            phone=%s,
            email=%s,
            last_donation=%s
        WHERE id=%s
        """

        values = (
            name,
            age,
            blood_group,
            city,
            phone,
            email,
            last_donation if last_donation else None,
            id
        )

        cursor.execute(query, values)
        db.commit()

        return redirect("/manage-donors")

    query = """
    SELECT id, name, age, blood_group, city, phone, email, last_donation
    FROM donors
    WHERE id=%s
    """

    cursor.execute(query, (id,))

    donor = cursor.fetchone()

    return render_template(
        "edit_donor.html",
        donor=donor
    )


# =========================
# DELETE DONOR
# =========================

@app.route("/delete-donor/<int:id>", methods=["POST"])
def delete_donor(id):

    if not session.get("logged_in"):
        return redirect("/login")

    query = """
    DELETE FROM donors
    WHERE id=%s
    """

    cursor.execute(query, (id,))
    db.commit()

    return redirect("/manage-donors")


# =========================
# RUN FLASK
# =========================
@app.route("/chat", methods=["POST"])
def chat():
    from flask import jsonify
    import requests

    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"reply": "Please type a message."}), 400

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2",
                "messages": [
                    {
                        "role": "system",
                         "content": (
    "You are the AI assistant for Smart Blood Donor Management System. "
    "Help users with donor registration, donor search, blood groups, "
    "hospital registration, and blood requests. "

    "IMPORTANT LANGUAGE RULES: "
    "If the user asks in English, reply entirely in English. "
    "If the user asks in Hindi, reply in Hindi. "
    "If the user asks in Hinglish (Hindi written using English letters), "
    "reply in Hinglish using English letters. "
    "Always identify the language of the user's latest message and "
    "reply in that same language. Do not default to Hindi. "

    "Keep replies simple and concise. "
    "Never invent donor records, donor availability, or request statuses. "
    "Tell users to check the website for actual results."
)
                    },
                    {"role": "user", "content": message}
                ],
                "stream": False
            },
            timeout=90
        )

        response.raise_for_status()
        reply = response.json()["message"]["content"]
        return jsonify({"reply": reply})

    except requests.exceptions.ConnectionError:
        return jsonify({
            "reply": "AI service is not running. Please start Ollama and try again."
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({
            "reply": "The AI is taking too long to respond. Please try again."
        }), 504

    except requests.exceptions.RequestException:
        return jsonify({
            "reply": "Sorry, the AI service encountered an error."
        }), 502
# =========================
# DOWNLOAD PDF REPORT
# =========================

@app.route("/download-report/pdf")
def download_pdf_report():

    if not session.get("logged_in"):
        return redirect("/login")

    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet
    from flask import send_file

    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph(
        "Smart Blood Donor Management System",
        styles["Title"]
    ))
    content.append(Spacer(1, 15))
    content.append(Paragraph("Analytics Report", styles["Heading2"]))
    content.append(Spacer(1, 15))

    cursor.execute("SELECT COUNT(*) FROM donors")
    total_donors = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM blood_requests")
    total_requests = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT city) FROM donors")
    total_cities = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hospitals")
    total_hospitals = cursor.fetchone()[0]

    report_data = [
        ["Metric", "Total"],
        ["Registered Donors", total_donors],
        ["Blood Requests", total_requests],
        ["Cities Covered", total_cities],
        ["Registered Hospitals", total_hospitals]
    ]

    report_table = Table(report_data, colWidths=[260, 150])
    report_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkred),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    content.append(report_table)

    document.build(content)
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="blood_donor_analytics.pdf",
        mimetype="application/pdf"
    )


# =========================
# DOWNLOAD EXCEL REPORT
# =========================

@app.route("/download-report/excel")
def download_excel_report():

    if not session.get("logged_in"):
        return redirect("/login")

    from io import BytesIO
    from openpyxl import Workbook
    from flask import send_file

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Analytics"

    sheet.append(["Smart Blood Donor Management System"])
    sheet.append(["Metric", "Total"])

    cursor.execute("SELECT COUNT(*) FROM donors")
    sheet.append(["Registered Donors", cursor.fetchone()[0]])

    cursor.execute("SELECT COUNT(*) FROM blood_requests")
    sheet.append(["Blood Requests", cursor.fetchone()[0]])

    cursor.execute("SELECT COUNT(DISTINCT city) FROM donors")
    sheet.append(["Cities Covered", cursor.fetchone()[0]])

    cursor.execute("SELECT COUNT(*) FROM hospitals")
    sheet.append(["Registered Hospitals", cursor.fetchone()[0]])

    # Donor counts by blood group
    sheet.append([])
    sheet.append(["Blood Group", "Donor Count"])

    cursor.execute("""
        SELECT blood_group, COUNT(*)
        FROM donors
        GROUP BY blood_group
        ORDER BY blood_group
    """)

    for group, count in cursor.fetchall():
        sheet.append([group, count])

    # Blood request status counts
    sheet.append([])
    sheet.append(["Request Status", "Count"])

    cursor.execute("""
        SELECT request_status, COUNT(*)
        FROM blood_requests
        GROUP BY request_status
    """)

    for status, count in cursor.fetchall():
        sheet.append([status, count])

    sheet.column_dimensions["A"].width = 35
    sheet.column_dimensions["B"].width = 20

    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name="blood_donor_analytics.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# =========================
# RUN FLASK APPLICATION
# =========================

if __name__ == "__main__":
    app.run(debug=True)