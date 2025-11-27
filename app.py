from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from config import Config
from models import db, User, Department, Doctor, Patient, Appointment, Treatment
from datetime import datetime, date, time

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    def initial_data():
        if Department.query.count() == 0:
            deps = [
                Department(name='General Medicine', description='General health issues'),
                Department(name='Pediatrics', description='Kids and child health'),
                Department(name='Orthopedics', description='Bones and joints'),
                Department(name='Cardiology', description='Heart specialist'),
            ]
            db.session.bulk_save_objects(deps)
            db.session.commit()

        if not User.query.filter_by(role='admin').first():
            admin = User(username='admin', password='admin123', role='admin')
            db.session.add(admin)
            db.session.commit()

    with app.app_context():
        db.create_all()
        initial_data()

    def login_user(user):
        session['user_id'] = user.id
        session['role'] = user.role
        session['username'] = user.username

    def logout_user():
        session.pop('user_id', None)
        session.pop('role', None)
        session.pop('username', None)

    def current_user():
        uid = session.get('user_id')
        if not uid:
            return None
        return User.query.get(uid)

    def login_required(role=None):
        def wrapper(fn):
            from functools import wraps
            @wraps(fn)
            def decorated(*args, **kwargs):
                if 'user_id' not in session:
                    flash("Please login first.", "warning")
                    return redirect(url_for('login'))
                if role and session.get('role') != role:
                    abort(403)
                return fn(*args, **kwargs)
            return decorated
        return wrapper

    @app.route('/')
    def index():
        return render_template('index.html', user=current_user())

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username'].strip()
            password = request.form['password']
            full_name = request.form['full_name'].strip() or username

            age_raw = request.form.get('age')  # may be empty
            contact = request.form.get('contact', '').strip()
            address = request.form.get('address', '').strip()

            if User.query.filter_by(username=username).first():
                flash("Username already exists", "danger")
                return redirect(url_for('register'))

            user = User(username=username, password=password, role='patient')
            db.session.add(user)
            db.session.commit()

            age = int(age_raw) if age_raw else None

            patient = Patient(
                user_id=user.id,
                full_name=full_name,
                age=age,
                contact=contact or None,
                address=address or None
            )
            db.session.add(patient)
            db.session.commit()

            flash("Registration successful. Please login.", "success")
            return redirect(url_for('login'))

        return render_template('auth/register.html')


    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username'].strip()
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and user.password == password:
                login_user(user)
                flash("Logged in successfully", "success")
                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.role == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                else:
                    return redirect(url_for('patient_dashboard'))
            flash("Invalid credentials", "danger")
        return render_template('auth/login.html')

    @app.route('/logout')
    def logout():
        logout_user()
        flash("Logged out", "info")
        return redirect(url_for('index'))

    @app.route('/admin/dashboard')
    @login_required(role='admin')
    def admin_dashboard():
        total_doctors = Doctor.query.count()
        total_patients = Patient.query.count()
        total_appointments = Appointment.query.count()
        doctors = Doctor.query.all()
        patients = Patient.query.all()
        appointments = Appointment.query.order_by(Appointment.date.desc()).limit(20).all()

    
        import matplotlib
        matplotlib.use('Agg')   
        import matplotlib.pyplot as plt

    
        department_names = []
        departments_counts = []

        for dept in Department.query.all():
            count = Appointment.query.join(Doctor).filter(Doctor.specialization_id == dept.id).count()
            department_names.append(dept.name)
            departments_counts.append(count)

    
        plt.figure(figsize=(5, 5))
        plt.pie(departments_counts, labels=department_names, autopct='%1.1f%%', startangle=40)
        plt.title('Appointments Per Department')
        chart_path = 'static/appointments_pie.png'
        plt.savefig(chart_path)
        plt.close()

        return render_template('admin/dashboard.html',
                           total_doctors=total_doctors,
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           doctors=doctors,
                           patients=patients,
                           appointments=appointments,
                           chart_path=chart_path)
    @app.route('/admin/doctors', methods=['GET', 'POST'])
    @login_required(role='admin')
    def admin_doctors():
        if request.method == 'POST':
            name = request.form['full_name'].strip()
            username = request.form['username'].strip()
            password = request.form['password']
            specialization_id = request.form.get('specialization') or None
            availability = request.form.get('availability', '')
            if User.query.filter_by(username=username).first():
                flash("Username already exists", "danger")
                return redirect(url_for('admin_doctors'))
            user = User(username=username, password=password, role='doctor')
            db.session.add(user)
            db.session.commit()
            doctor = Doctor(user_id=user.id, full_name=name, specialization_id=specialization_id, availability=availability)
            db.session.add(doctor)
            db.session.commit()
            flash("Doctor added", "success")
            return redirect(url_for('admin_doctors'))
        departments = Department.query.all()
        doctors = Doctor.query.all()
        return render_template('admin/doctors_list.html', doctors=doctors, departments=Departments)

    @app.route('/admin/doctors/delete/<int:id>', methods=['POST'])
    @login_required(role='admin')
    def admin_delete_doctor(id):
        doctor = Doctor.query.get_or_404(id)
        user = doctor.user
        db.session.delete(doctor)
        if user:
            db.session.delete(user)
        db.session.commit()
        flash("Doctor removed", "info")
        return redirect(url_for('admin_doctors'))

    @app.route('/admin/appointments')
    @login_required(role='admin')
    def admin_appointments():
        q = request.args.get('q','')
        if q:
            appointments = Appointment.query.join(Patient).join(Doctor).filter(
                (Patient.full_name.ilike(f"%{q}%")) | (Doctor.full_name.ilike(f"%{q}%"))
            ).all()
        else:
            appointments = Appointment.query.order_by(Appointment.date.desc()).all()
        return render_template('admin/appointments.html', appointments=appointments, query=q)

    @app.route('/doctor/dashboard')
    @login_required(role='doctor')
    def doctor_dashboard():
        user = current_user()
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        today = date.today()
        upcoming = Appointment.query.filter_by(doctor_id=doctor.id).filter(Appointment.date >= today).order_by(Appointment.date.asc()).all()
        patients = []
        seen = set()
        for apt in upcoming:
            if apt.patient_id not in seen:
                patients.append(apt.patient)
                seen.add(apt.patient_id)
        return render_template('doctor/dashboard.html', doctor=doctor, upcoming=upcoming, patients=patients)

    @app.route('/doctor/appointment/<int:aid>', methods=['GET', 'POST'])
    @login_required(role='doctor')
    def doctor_appointment_detail(aid):
        user = current_user()
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        appointment = Appointment.query.get_or_404(aid)

        if appointment.doctor_id != doctor.id:
            abort(403)

        if request.method == 'POST':
            if appointment.status == 'Cancelled':
                flash("This appointment was cancelled by the patient. You cannot modify it.", "warning")
                return redirect(url_for('doctor_appointment_detail', aid=appointment.id))

            action = request.form.get('action')

            if action == 'complete':
                appointment.status = 'Completed'
                diagnosis = request.form.get('diagnosis')
                prescription = request.form.get('prescription')
                notes = request.form.get('notes')

                if appointment.treatment:
                    t = appointment.treatment
                    t.diagnosis = diagnosis
                    t.prescription = prescription
                    t.notes = notes
                else:
                    t = Treatment(
                        appointment_id=appointment.id,
                        diagnosis=diagnosis,
                        prescription=prescription,
                        notes=notes
                    )
                    db.session.add(t)

                db.session.commit()
                flash("Appointment completed", "success")

            elif action == 'cancel':
                appointment.status = 'Cancelled'
                db.session.commit()
                flash("Appointment cancelled", "info")

            return redirect(url_for('doctor_dashboard'))

        return render_template('doctor/appointment_detail.html', appointment=appointment)

    @app.route('/patient/dashboard')
    @login_required(role='patient')
    def patient_dashboard():
        user = current_user()
        patient = Patient.query.filter_by(user_id=user.id).first()
        departments = Department.query.all()
        upcoming = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.date.asc()).all()
        return render_template('patient/dashboard.html', patient=patient, departments=departments, upcoming=upcoming)

    @app.route('/patient/search_doctors', methods=['GET'])
    @login_required(role='patient')
    def search_doctors():
        q = request.args.get('q','')
        dept = request.args.get('dept','')
        doctors = Doctor.query.filter(Doctor.is_active == True)
        if q:
            doctors = doctors.filter(Doctor.full_name.ilike(f"%{q}%"))
        if dept:
            try:
                doctors = doctors.filter(Doctor.specialization_id == int(dept))
            except ValueError:
                pass
        doctors = doctors.all()
        departments = Department.query.all()
        return render_template('patient/search_doctors.html', doctors=doctors, departments=departments, query=q)

    @app.route('/patient/book/<int:doctor_id>', methods=['GET', 'POST'])
    @login_required(role='patient')
    def book_appointment(doctor_id):
        user = current_user()
        patient = Patient.query.filter_by(user_id=user.id).first()
        doctor = Doctor.query.get_or_404(doctor_id)
        if request.method == 'POST':
            date_str = request.form['date']
            time_str = request.form['time']
            reason = request.form.get('reason','')
            try:
                sdate = datetime.strptime(date_str, "%Y-%m-%d").date()
                stime = datetime.strptime(time_str, "%H:%M").time()
            except Exception:
                flash("Invalid date/time format", "danger")
                return redirect(url_for('book_appointment', doctor_id=doctor_id))

            conflict = Appointment.query.filter_by(doctor_id=doctor.id, date=sdate, time=stime, status='Booked').first()
            if conflict:
                flash("Selected slot is not available", "danger")
                return redirect(url_for('book_appointment', doctor_id=doctor_id))

            apt = Appointment(doctor_id=doctor.id, patient_id=patient.id, date=sdate, time=stime, status='Booked', reason=reason)
            db.session.add(apt)
            db.session.commit()
            flash("Appointment booked", "success")
            return redirect(url_for('patient_dashboard'))
        return render_template('patient/book_appointment.html', doctor=doctor)

    @app.route('/patient/appointment/cancel/<int:aid>', methods=['POST'])
    @login_required(role='patient')
    def patient_cancel_appointment(aid):
        user = current_user()
        patient = Patient.query.filter_by(user_id=user.id).first()
        apt = Appointment.query.get_or_404(aid)
        if apt.patient_id != patient.id:
            abort(403)
        apt.status = 'Cancelled'
        db.session.commit()
        flash("Appointment cancelled", "info")
        return redirect(url_for('patient_dashboard'))

    @app.route('/patient/appointment/<int:aid>')
    @login_required(role='patient')
    def patient_view_appointment(aid):
        user = current_user()
        patient = Patient.query.filter_by(user_id=user.id).first()
        apt = Appointment.query.get_or_404(aid)
        if apt.patient_id != patient.id:
            abort(403)
        return render_template('patient/appointment_detail.html', appointment=apt)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
