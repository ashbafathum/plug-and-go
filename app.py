from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import UniqueConstraint

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for session management

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///plugandgo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'

    def __repr__(self):
        return f'<User {self.username}>'

# ChargingStation Model
class ChargingStation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    price_per_kwh = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<ChargingStation {self.name}>'

# Booking Model with Unique Constraint to prevent double bookings
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('charging_station.id'), nullable=False)
    booking_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    booking_time = db.Column(db.String(5), nullable=False)   # HH:MM
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp for expiration

    # Relationship to ChargingStation
    station = db.relationship('ChargingStation', backref='bookings')

    __table_args__ = (UniqueConstraint('station_id', 'booking_date', 'booking_time', name='unique_booking'),)

    @property
    def is_expired(self):
        # Check if the booking is older than 20 minutes
        return datetime.utcnow() > self.created_at + timedelta(minutes=20)

    def __repr__(self):
        return f'<Booking {self.id}>'

# Create the database and tables, and add extra user if not present
with app.app_context():
    db.create_all()

    # Create an extra user 'user2' if not already present
    user2 = User.query.filter_by(email='user2@example.com').first()
    if not user2:
        user2 = User(username='user2', email='user2@example.com', password='password2', role='user')
        db.session.add(user2)
        db.session.commit()

# Home Page Route
@app.route('/')
def home():
    return render_template('index.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if the user exists and the password matches
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['logged_in'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role

            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('profile'))
        else:
            flash('Invalid email or password!', 'error')
    return render_template('login.html')

# Signup Route
@app.route('/signup', methods=['POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('login'))

        # Check if the email is already registered
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return redirect(url_for('login'))

        # Create a new user
        new_user = User(username=username, email=email, password=password, role='user')
        db.session.add(new_user)
        db.session.commit()

        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

# Admin Dashboard Route
@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    # Fetch all users, stations, and bookings
    users = User.query.all()
    stations = ChargingStation.query.all()
    bookings = Booking.query.all()

    return render_template('admin.html', users=users, stations=stations, bookings=bookings)

# Add Station Route
@app.route('/add_station', methods=['POST'])
def add_station():
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    name = request.form.get('name')
    location = request.form.get('location')
    available_slots = int(request.form.get('available_slots'))
    price_per_kwh = float(request.form.get('price_per_kwh'))

    new_station = ChargingStation(
        name=name,
        location=location,
        available_slots=available_slots,
        price_per_kwh=price_per_kwh
    )
    db.session.add(new_station)
    db.session.commit()

    flash('Station added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Edit Station Route
@app.route('/edit_station/<int:station_id>', methods=['POST'])
def edit_station(station_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    station = ChargingStation.query.get_or_404(station_id)
    station.name = request.form.get('name')
    station.location = request.form.get('location')
    station.available_slots = int(request.form.get('available_slots'))
    station.price_per_kwh = float(request.form.get('price_per_kwh'))
    db.session.commit()

    flash('Station updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Edit User Route
@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)
    user.username = request.form.get('username')
    user.email = request.form.get('email')
    user.role = request.form.get('role')
    db.session.commit()

    flash('User updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Delete Station Route
@app.route('/delete_station/<int:station_id>', methods=['POST'])
def delete_station(station_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    station = ChargingStation.query.get_or_404(station_id)

    # Check if there are bookings for this station
    if station.bookings:
        flash('Cannot delete station. There are active bookings for this station.', 'error')
        return redirect(url_for('admin_dashboard'))

    db.session.delete(station)
    db.session.commit()

    flash('Station deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Delete User Route
@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('You are not authorized to access this page.', 'error')
        return redirect(url_for('home'))

    user = User.query.get_or_404(user_id)

    # Check if the user has any bookings
    if Booking.query.filter_by(user_id=user.id).first():
        flash('Cannot delete user. The user has active bookings.', 'error')
        return redirect(url_for('admin_dashboard'))

    db.session.delete(user)
    db.session.commit()

    flash('User deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Profile Route
@app.route('/profile')
def profile():
    if not session.get('logged_in'):
        flash('Please login to access this page.', 'error')
        return redirect(url_for('login'))

    # Fetch the logged-in user's bookings
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    bookings = Booking.query.filter_by(user_id=user_id).all()

    # Fetch all charging stations
    stations = ChargingStation.query.all()

    return render_template('profile.html', username=user.username, stations=stations, bookings=bookings)

# Payment Route with double-book prevention and next available slot suggestion
@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if not session.get('logged_in'):
        flash('Please login to access this page.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        station_id = request.form.get('station_id')
        booking_date = request.form.get('booking_date')
        booking_time = request.form.get('booking_time')

        # Application-level check for existing booking in the same time slot
        existing = Booking.query.filter_by(
            station_id=station_id,
            booking_date=booking_date,
            booking_time=booking_time
        ).first()

        if existing:
            # Suggest next available slot (30 minutes later)
            current_time = datetime.strptime(existing.booking_time, "%H:%M")
            suggested_time = (current_time + timedelta(minutes=30)).strftime("%H:%M")
            flash(f'Time slot {booking_time} is already booked. Next available slot: {suggested_time}.', 'error')
            return redirect(url_for('payment', station_id=station_id, date=booking_date, time=suggested_time))

        new_booking = Booking(
            user_id=session.get('user_id'),
            station_id=station_id,
            booking_date=booking_date,
            booking_time=booking_time
        )
        db.session.add(new_booking)

        # Reduce available slots at the station
        station = ChargingStation.query.get(station_id)
        station.available_slots -= 1

        try:
            db.session.commit()
            flash('Payment successful! Booking confirmed.', 'success')
            return redirect(url_for('profile'))
        except IntegrityError:
            db.session.rollback()
            flash('Time slot already booked. Please select a different time.', 'error')
            return redirect(url_for('payment', station_id=station_id, date=booking_date, time=booking_time))

    # GET request: Get booking details from query parameters
    station_id = request.args.get('station_id')
    booking_date = request.args.get('date')
    booking_time = request.args.get('time')

    return render_template('payment.html', station_id=station_id, booking_date=booking_date, booking_time=booking_time)

# Cancel Booking Route
@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if not session.get('logged_in'):
        flash('Please login to access this page.', 'error')
        return redirect(url_for('login'))

    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != session.get('user_id'):
        flash('You are not authorized to cancel this booking.', 'error')
        return redirect(url_for('profile'))

    # Increase available slots at the station
    station = ChargingStation.query.get(booking.station_id)
    station.available_slots += 1

    db.session.delete(booking)
    db.session.commit()

    flash('Booking canceled successfully!', 'success')
    return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(debug=True)
