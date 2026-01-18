from flask import Flask, render_template,request, redirect, session, flash, send_file  
import sqlite3, hashlib, csv
from functools import wraps
from datetime import date

app = Flask(__name__)
app.secret_key = "super-secret-key"

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

def get_db():
    conn = sqlite3.connect("students.db",timeout=30,check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

# Create table
with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        name TEXT,
        age INTEGER,
        course_id TEXT,
        active INTEGER,
        created_at TEXT
    )
    """)


with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id TEXT PRIMARY KEY,
        name TEXT,
        duration INTEGER,
        start_date TEXT,
        end_date TEXT                         
    )
    """)


with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        course_id TEXT
    )
    """)    

with get_db() as conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        date TEXT,
        status INTEGER,
        FOREIGN KEY(student_id) REFERENCES students(id),
        UNIQUE(student_id, date)         
    )
    """)


@app.route("/")
@login_required
def dashboard():
    conn = sqlite3.connect("students.db")

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    active_students = conn.execute(
        "SELECT COUNT(*) FROM students WHERE active = 1"
    ).fetchone()[0]

    total_courses = conn.execute(
        "SELECT COUNT(*) FROM courses"
    ).fetchone()[0]

    attendance_rate = conn.execute("""
        SELECT 
        CASE 
            WHEN COUNT(*) = 0 THEN 0
            ELSE ROUND(AVG(status)*100, 2)
        END
        FROM attendance
    """).fetchone()[0]

    # Pie chart data
    raw_course_data = conn.execute("""
        SELECT courses.name, COUNT(students.id)
        FROM students
        LEFT JOIN courses ON students.course_id = courses.id
        GROUP BY courses.name
    """).fetchall()

    course_labels = [row[0] for row in raw_course_data]
    course_counts = [row[1] for row in raw_course_data]

    # Line chart data
    raw_monthly_data = conn.execute("""
        SELECT strftime('%Y-%m', date), ROUND(AVG(status)*100, 2)
        FROM attendance
        GROUP BY strftime('%Y-%m', date)
    """).fetchall()

    months = [row[0] for row in raw_monthly_data]
    monthly_counts = [row[1] for row in raw_monthly_data]

    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        active_students=active_students,
        total_courses=total_courses,
        attendance_rate=attendance_rate,
        course_labels=course_labels,
        course_counts=course_counts,
        months=months,
        monthly_counts=monthly_counts
    )


@app.route("/add-course-temp")
def add_course_temp():
    conn = get_db()
    conn.execute("INSERT INTO courses (name) VALUES ('Python')")
    conn.commit()
    conn.close()
    return "Course added"

@app.route("/students")
def students():
    conn = sqlite3.connect("students.db")

    course_id = request.args.get("course_id")
    active = request.args.get("active")

    query = """
        SELECT
            students.id,
            students.name,
            students.age,
            courses.name,
            students.active
        FROM students
        LEFT JOIN courses
        ON students.course_id = courses.id
        WHERE 1=1
    """

    params = []

    if course_id:
        query += " AND students.course_id = ?"
        params.append(course_id)

    if active:
        query += " AND students.active = ?"
        params.append(active)

    students = conn.execute(query, params).fetchall()
    courses = conn.execute("SELECT * FROM courses").fetchall()

    conn.close()

    return render_template(
        "students.html",
        students=students,
        courses=courses
    )

@app.route("/add-student", methods=["GET", "POST"])
def add_student():
    conn = get_db()

    if request.method == "POST":
        student_id = request.form["id"]
        course_id = request.form["course_id"]

        from datetime import date
        created_at = date.today().isoformat()

        try:
            conn.execute(
                "INSERT INTO students VALUES (?,?,?,?,?,?)",
                (
                    student_id,
                    request.form["name"],
                    request.form["age"],
                    course_id,
                    request.form["active"],
                    created_at
                )
            )

            conn.execute(
                "INSERT INTO enrollments (student_id, course_id) VALUES (?,?)",
                (student_id, course_id)
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "❌ Student ID already exists. Please use a different ID."

        conn.close()
        return redirect("/students")

    courses = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template("add_student.html", courses=courses)

@app.route("/edit-student/<id>", methods=["GET", "POST"])
def edit_student(id):
    conn = sqlite3.connect("students.db")

    if request.method == "POST":
        course_id = request.form["course_id"]
        conn.execute(
            "UPDATE students SET name=?, age=?, active=?, course_id=? WHERE id=?",
            (
                request.form["name"],
                request.form["age"],
                request.form["course_id"],
                request.form["active"],
                id
            )
        )
        
        conn.commit()
        conn.close()
        return redirect("/students")

    student = conn.execute(
        "SELECT * FROM students WHERE id=?", (id,)
    ).fetchone()

    courses = conn.execute("SELECT * FROM courses").fetchall()

    conn.close()

    return render_template("edit_student.html", s=student, courses=courses)


@app.route("/delete-student/<id>")
def delete_student(id):
    conn = sqlite3.connect("students.db")
    conn.execute("DELETE FROM students WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/students")


@app.route("/courses")
def courses():
    conn = get_db()
    data = conn.execute("SELECT * FROM courses").fetchall()
    conn.close()
    return render_template("courses.html", courses=data)

@app.route("/add-course", methods=["GET", "POST"])
def add_course():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            "INSERT INTO courses VALUES (?,?,?,?,?)",
            (
                request.form["id"],
                request.form["name"],
                request.form["duration"],
                request.form["start_date"],
                request.form["end_date"]    
            )
        )
        conn.commit()
        conn.close()
        return redirect("/courses")

    return render_template("add_course.html")


@app.route("/edit-course/<id>", methods=["GET", "POST"])
def edit_course(id):
    conn = get_db()

    if request.method == "POST":
        conn.execute(
            "UPDATE courses SET name=?, duration=? WHERE id=?",
            (
                request.form["name"],
                request.form["duration"],
                id
            )
        )
        conn.commit()
        conn.close()
        return redirect("/courses")

    course = conn.execute(
        "SELECT * FROM courses WHERE id=?", (id,)
    ).fetchone()
    conn.close()

    return render_template("edit_course.html", c=course)


@app.route("/delete-course/<id>")
def delete_course(id):
    conn = get_db()
    conn.execute("DELETE FROM courses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/courses")

@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    conn = sqlite3.connect("students.db")

    selected_date = request.args.get("date")

    if request.method == "POST":
        date = request.form["date"]

        for key in request.form:
            if key.startswith("status_"):
                student_id = key.split("_")[1]
                status = int(request.form[key])

                existing = conn.execute(
                    "SELECT id FROM attendance WHERE student_id=? AND date=?",
                    (student_id, date)
                ).fetchone()

                if existing:
                    conn.execute(
                        "UPDATE attendance SET status=? WHERE student_id=? AND date=?",
                        (status, student_id, date)
                    )
                else:
                    conn.execute(
                        "INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)",
                        (student_id, date, status)
                    )

        conn.commit()
        conn.close()
        return redirect(f"/attendance?date={date}")

    students = conn.execute(
        "SELECT id, name FROM students WHERE active=1"
    ).fetchall()

    records = []
    if selected_date:
        records = conn.execute(
            """
            SELECT students.id,students.name, attendance.date, attendance.status
            FROM attendance
            JOIN students ON attendance.student_id = students.id
            WHERE attendance.date = ?
            """,
            (selected_date,)
        ).fetchall()

    conn.close()

    return render_template(
        "attendance.html",
        students=students,
        records=records,
        selected_date=selected_date
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hashed)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = username
            return redirect("/")
        else:
            flash("Invalid credentials")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/export/students")
def export_students():
    conn = get_db()
    data = conn.execute("""
        SELECT students.id, students.name, students.age,
               courses.name, students.active
        FROM students
        LEFT JOIN courses ON students.course_id = courses.id
    """).fetchall()
    conn.close()

    with open("students_report.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Name", "Age", "Course", "Active"])
        writer.writerows([tuple(row) for row in data])

    return send_file("students_report.csv", as_attachment=True)

@app.route("/export/attendance")
@login_required
def export_attendance():
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    if not from_date or not to_date:
        return "Please select from and to dates"

    conn = get_db()
    data = conn.execute("""
        SELECT 
            students.id,
            students.name,
            attendance.date,
            attendance.status
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        WHERE attendance.date BETWEEN ? AND ?
        ORDER BY attendance.date
    """, (from_date, to_date)).fetchall()
    conn.close()

    with open("attendance_report.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Student ID", "Name", "Date", "Status"])
        for row in data:
            writer.writerow([
                row["id"],
                row["name"],
                row["date"],
                "Present" if row["status"] == 1 else "Absent"
            ])

    return send_file("attendance_report.csv", as_attachment=True)

@app.route("/reports")
def reports():
    return render_template("reports.html")


if __name__ == "__main__":
    app.run(debug=False)