from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///models.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, nullable=True)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    event = db.relationship('Event', backref=db.backref('registrations', lazy=True))

def init_db():
    db.create_all()
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
        db.session.add(admin)
    if Event.query.count() == 0:
        e1 = Event(title='Tech Talk: Web Development', description='Introductory talk on web development', date=datetime(2025,12,1,10,0), capacity=100)
        e2 = Event(title='Hackathon 24H', description='Team hackathon', date=datetime(2025,12,10,9,0), capacity=50)
        db.session.add_all([e1,e2])
    db.session.commit()

@app.before_first_request
def setup():
    init_db()

@app.route('/')
def index():
    events = Event.query.order_by(Event.date).all()
    return render_template('index.html', events=events)

@app.route('/events')
def events():
    events = Event.query.order_by(Event.date).all()
    return render_template('events.html', events=events)

@app.route('/event/<int:event_id>/register', methods=['GET','POST'])
def register(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        if not name or not email:
            flash('Name and email are required.', 'danger')
            return render_template('register.html', event=event)
        existing = Registration.query.filter_by(event_id=event.id, email=email).first()
        if existing:
            flash('You have already registered for this event.', 'warning')
            return redirect(url_for('my_regs'))
        reg = Registration(event_id=event.id, name=name, email=email, phone=phone, status='Pending')
        db.session.add(reg)
        db.session.commit()
        flash('Registration submitted. Waiting for admin approval.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', event=event)

@app.route('/my_registrations')
def my_regs():
    email = request.args.get('email','').strip()
    regs = []
    if email:
        regs = Registration.query.filter_by(email=email).order_by(Registration.timestamp.desc()).all()
    return render_template('my_regs.html', regs=regs, email=email)

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','').strip()
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('admin_login.html')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    events = Event.query.order_by(Event.date).all()
    pending_count = Registration.query.filter_by(status='Pending').count()
    return render_template('admin_dashboard.html', events=events, pending_count=pending_count)

@app.route('/admin/event/<int:event_id>/participants')
@admin_required
def participants(event_id):
    event = Event.query.get_or_404(event_id)
    regs = Registration.query.filter_by(event_id=event.id).order_by(Registration.timestamp.desc()).all()
    return render_template('participants.html', event=event, regs=regs)

@app.route('/admin/registration/<int:reg_id>/update', methods=['POST'])
@admin_required
def update_registration(reg_id):
    action = request.form.get('action')
    reg = Registration.query.get_or_404(reg_id)
    if action == 'approve':
        approved = Registration.query.filter_by(event_id=reg.event_id, status='Approved').count()
        if reg.event.capacity and approved >= reg.event.capacity:
            flash('Event is full. Cannot approve more participants.', 'danger')
        else:
            reg.status = 'Approved'
            db.session.commit()
            flash('Registration approved.', 'success')
    elif action == 'reject':
        reg.status = 'Rejected'
        db.session.commit()
        flash('Registration rejected.', 'info')
    return redirect(url_for('participants', event_id=reg.event_id))

if __name__ == '__main__':
    app.run(debug=True)
