from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta, timezone
import json
import bcrypt
from pymongo import MongoClient
from bson import ObjectId
import os
import urllib.parse
import csv
import io
import requests
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import re  # Add this import

app = Flask(__name__)
app.config.from_object('config.Config')

# Authentic Karnataka Police Stations List
KARNATAKA_POLICE_STATIONS = [
    # Bengaluru City Police Stations
    "Ashok Nagar Police Station", "Basavanagudi Police Station", "Chamarajpet Police Station",
    "Commercial Street Police Station", "Cubbon Park Police Station", "Halasuru Police Station",
    "High Grounds Police Station", "Jayanagar Police Station", "K.G. Halli Police Station",
    "K.R. Market Police Station", "Koramangala Police Station", "Madiwala Police Station",
    "Mahalakshmi Layout Police Station", "Malleshwaram Police Station", "Seshadripuram Police Station",
    "Shivajinagar Police Station", "Ulsoor Police Station", "Vijayanagar Police Station",
    "Whitefield Police Station", "Yelahanka Police Station",
    
    # Davanagere District Police Stations
    "Davanagere Traffic Police Station", "Davanagere Women Police Station", "Jagalur Police Station",
    "Channagiri Police Station", "Harapanahalli Police Station", "Harihar Police Station",
    "Honnali Police Station", "Nyamathi Police Station",
    
    # Mysuru City Police Stations
    "Vijayanagar Police Station Mysuru", "Nazarabad Police Station", "K.R. Police Station Mysuru",
    "Metagalli Police Station", "Lashkar Police Station", "Jayanagar Police Station Mysuru",
    
    # Hubballi-Dharwad Police Stations
    "Hubballi Traffic Police Station", "Old Hubballi Police Station", "Vidyanagar Police Station",
    "Dharwad Police Station", "Keshavpur Police Station",
    
    # Mangaluru Police Stations
    "Mangaluru North Police Station", "Mangaluru South Police Station", "Kadri Police Station",
    "Bunder Police Station", "Pandeshwar Police Station",
    
    # Belagavi Police Stations
    "Belagavi Traffic Police Station", "Khanapur Police Station", "Gokul Road Police Station",
    "Sadashiv Nagar Police Station",
    
    # Kalaburagi Police Stations
    "Kalaburagi Traffic Police Station", "Jewargi Police Station", "Sedam Police Station",
    
    # Other Major District Police Stations
    "Tumakuru Rural Police Station", "Shivamogga Traffic Police Station", "Ballari Rural Police Station",
    "Vijayapura City Police Station", "Hassan Traffic Police Station", "Udupi Women Police Station",
    "Mandya Rural Police Station", "Kolar Traffic Police Station", "Kolar Traffic Police Station",
    "Chikkamagaluru Police Station", "Chitradurga Police Station", "Raichur Rural Police Station", 
    "Bidar City Police Station",
    "Bagalkote Police Station", "Gadag Police Station", "Haveri Police Station",
    "Koppal Police Station", "Yadgir Police Station", "Ramanagara Police Station",
    "Chikkaballapura Police Station", "Kodagu Madikeri Police Station", "Dakshina Kannada Puttur Police Station"
]

# MongoDB Atlas Connection
def get_mongodb_connection():
    mongodb_uri = app.config['MONGODB_URI']
    
    print(f"🔗 Connecting to MongoDB Atlas...")
    print(f"📡 URI: {mongodb_uri.split('@')[0]}@***")
    
    try:
        # For MongoDB Atlas with special characters in password
        client = MongoClient(mongodb_uri, retryWrites=True, w='majority')
        
        # Test connection
        client.admin.command('ismaster')
        print("✅ MongoDB Atlas connection successful!")
        
        # Get database name from URI
        db_name = 'SwiftAid'  # Your database name
        
        print(f"📊 Using database: {db_name}")
        return client, db_name
        
    except Exception as e:
        print(f"❌ MongoDB Atlas connection failed: {e}")
        raise e

# Initialize MongoDB connection
try:
    client, db_name = get_mongodb_connection()
    db = client[db_name]
    print("✅ MongoDB database connection established!")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    print("💡 Please check your MongoDB Atlas connection string in .env file")
    exit(1)

# Collections
POLICE_users = db.POLICE_users  # Collection for police users (login credentials)
incidents_collection = db.incidents  # Original collection (preserved)
incidents_police_collection = db.incidents_police  # Collection for police operations
police_officers_collection = db.police_officers  # Collection for police officers data
assigned_cases_collection = db.ASSIGNED_CASES  # New collection for assigned cases
police_stations_collection = db.police_stations  # Collection for police station registration info

# FIXED: Improved index handling with proper error handling
def fix_police_officers_index():
    try:
        # Get all indexes first
        indexes = list(police_officers_collection.list_indexes())
        print("🔍 Checking existing indexes...")
        
        # Look for username index
        username_index = None
        for index in indexes:
            if 'username' in index['key']:
                username_index = index
                break
        
        if username_index:
            print(f"📝 Found username index: {username_index['name']}")
            try:
                # Drop the problematic unique index
                police_officers_collection.drop_index(username_index['name'])
                print(f"✅ Removed problematic unique index: {username_index['name']}")
            except Exception as e:
                print(f"ℹ️ Index removal note: {e}")
        else:
            print("ℹ️ No username index found to remove")
            
    except Exception as e:
        print(f"ℹ️ Index check note: {e}")

def fix_existing_null_usernames():
    try:
        # Fix documents with null usernames
        result = police_officers_collection.update_many(
            {'username': None},
            {'$set': {'username': ''}}
        )
        print(f"✅ Fixed {result.modified_count} documents with null usernames")
        
        # Fix documents without username field
        result2 = police_officers_collection.update_many(
            {'username': {'$exists': False}},
            {'$set': {'username': ''}}
        )
        print(f"✅ Fixed {result2.modified_count} documents without username field")
    except Exception as e:
        print(f"ℹ️ Null username fix note: {e}")

# Run fixes immediately
fix_police_officers_index()
fix_existing_null_usernames()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.role = user_data.get('role', 'police')
        self.police_station = user_data.get('police_station', '')
        self.police_station_reg_no = user_data.get('police_station_reg_no', '')  # Add this
        self.full_name = user_data.get('full_name', '')
        self.designation = user_data.get('designation', 'Police Officer')
        self.created_at = user_data.get('created_at', datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = POLICE_users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception as e:
        print(f"Error loading user: {e}")
    return None

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(hashed_password, password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_address_from_coordinates(lat, lng):
    """Get address from coordinates using Nominatim (OpenStreetMap)"""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
        headers = {
            'User-Agent': 'SwiftAid Police System/1.0 (contact@swiftaid.com)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            address = data.get('display_name', 'Address not found')
            return address
        else:
            return f"Location at {lat}, {lng}"
    except Exception as e:
        print(f"Error getting address: {e}")
        return f"Location at {lat}, {lng}"

def process_public_incident(incident):
    """Process public incident from mobile app to standard format"""
    incident_id = str(incident.get('_id'))
    
    # Get coordinates - handle different field names
    lat = incident.get('lat') or incident.get('latitude', 0)
    lng = incident.get('lng') or incident.get('longitude', 0)
    
    # Get user information
    user_name = incident.get('user_name', 'Unknown User')
    user_email = incident.get('user_email', 'Unknown Email')
    
    # Determine incident type based on available data
    incident_type = "Emergency Alert"
    if incident.get('metadata', {}).get('sos_type'):
        incident_type = f"SOS - {incident['metadata']['sos_type'].title()}"
    if incident.get('accel_mag', 0) > 1.5:
        incident_type = "Possible Accident"
    
    # Determine severity
    severity = "high"  # Default to high for public emergencies
    if incident.get('speed', 0) > 0:
        severity = "high"
    elif incident.get('accel_mag', 0) > 1.0:
        severity = "medium"
    else:
        severity = "low"
    
    # Get address from coordinates
    address = get_address_from_coordinates(lat, lng)
    
    # Get timestamp
    created_at = incident.get('timestamp') or incident.get('created_at', datetime.now(timezone.utc))
    if isinstance(created_at, dict) and '$date' in created_at:
        created_at = datetime.fromisoformat(created_at['$date'].replace('Z', '+00:00'))
    
    return {
        '_id': incident_id,
        'incident_id': incident.get('incident_id', 'PUB-' + incident_id),
        'title': f"Emergency Alert from {user_name}",
        'description': f"Emergency alert triggered by {user_name} ({user_email}). " +
                      f"Location: {address}. " +
                      f"Speed: {incident.get('speed', 0)} km/h, " +
                      f"Acceleration: {incident.get('accel_mag', 0):.2f}",
        'incident_type': incident_type,
        'severity': severity,
        'status': 'active',  # Public incidents are always active initially
        'latitude': float(lat),
        'longitude': float(lng),
        'address': address,
        'reported_by': user_name,
        'assigned_officer': incident.get('assigned_officer', 'Unassigned'), # FIXED: Read assigned_officer from document
        'created_at': created_at,
        'source': 'public',
        'original_data': {  # Keep original data for reference
            'user_email': user_email,
            'accel_mag': incident.get('accel_mag'),
            'speed': incident.get('speed'),
            'metadata': incident.get('metadata', {})
        }
    }
def process_police_incident(incident):
    """Process police incident to standard format"""
    incident_id = str(incident.get('_id'))
    
    return {
        '_id': incident_id,
        'incident_id': incident.get('incident_id', 'POL-' + incident_id),
        'title': incident.get('title', 'Untitled Incident'),
        'description': incident.get('description', 'No description'),
        'incident_type': incident.get('incident_type', 'Unknown'),
        'severity': incident.get('severity', 'medium'),
        'status': incident.get('status', 'pending'),
        'latitude': float(incident.get('latitude', 0)),
        'longitude': float(incident.get('longitude', 0)),
        'address': incident.get('address', 'Unknown location'),
        'reported_by': incident.get('reported_by', 'Unknown'),
        'assigned_officer': incident.get('assigned_officer', 'Unassigned'),
        'created_at': incident.get('created_at', datetime.now(timezone.utc)),
        'source': 'police'
    }

def assign_case_to_officer(incident_id, source, assigned_officer, incident_data):
    """Assign case to officer and create record in ASSIGNED_CASES collection"""
    try:
        print(f"🔍 DEBUG assign_case_to_officer called:")
        print(f"   Incident ID: {incident_id}")
        print(f"   Source: {source}")
        print(f"   Assigned Officer: {assigned_officer}")
        
        # Update the incident data with the assigned officer
        incident_data['assigned_officer'] = assigned_officer
        incident_data['updated_at'] = datetime.now(timezone.utc)
        
        # Create assigned case record
        assigned_case = {
            'incident_id': incident_id,
            'source_collection': source,  # 'police' or 'public'
            'assigned_officer': assigned_officer,
            'assigned_by': current_user.username,
            'assigned_at': datetime.now(timezone.utc),
            'incident_data': incident_data,  # Already updated with assigned officer
            'status': 'assigned',  # assigned, in_progress, completed
            'last_updated': datetime.now(timezone.utc)
        }
        
        print(f"   Assigned Case Data: {assigned_case}")
        
        result = assigned_cases_collection.insert_one(assigned_case)
        
        print(f"✅ Assigned case inserted with ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        print(f"❌ Error in assign_case_to_officer: {e}")
        import traceback
        traceback.print_exc()
        return None

# Routes
@app.route('/')
@login_required
def dashboard():
    try:
        # FIXED: Get recent incidents from BOTH collections (ALL statuses, not just active)
        recent_police_incidents = list(incidents_police_collection.find().sort('created_at', -1).limit(5))
        recent_public_incidents = list(incidents_collection.find().sort('created_at', -1).limit(5))
        
        # Combine and sort recent incidents
        recent_incidents = []
        
        # Process police incidents
        for incident in recent_police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Process public incidents
        for incident in recent_public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Sort by creation date (newest first) and take top 5
        recent_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        recent_incidents = recent_incidents[:5]
        
        # CORRECTED: Get stats from police and public collections ONLY (exclude resolved_cases)
        total_police_incidents = incidents_police_collection.count_documents({})
        total_public_incidents = incidents_collection.count_documents({})
        
        # Total incidents = police + public (EXCLUDING resolved_cases)
        total_incidents = total_police_incidents + total_public_incidents
        
        # Active incidents = only active status from police and public
        active_police_incidents = incidents_police_collection.count_documents({'status': 'active'})
        active_public_incidents = incidents_collection.count_documents({'status': 'active'})
        active_incidents = active_police_incidents + active_public_incidents
        
        # Resolved incidents = resolved from police + resolved from public + resolved_cases
        resolved_police_incidents = incidents_police_collection.count_documents({'status': 'resolved'})
        resolved_public_incidents = incidents_collection.count_documents({'status': 'resolved'})
        resolved_from_cases = db.resolved_cases.count_documents({})
        total_resolved_incidents = resolved_police_incidents + resolved_public_incidents + resolved_from_cases
        
        # Get incidents assigned to current user from police and public collections only
        user_police_incidents = incidents_police_collection.count_documents({'assigned_officer': current_user.username})
        user_public_incidents = incidents_collection.count_documents({'assigned_officer': current_user.username})
        user_incidents = user_police_incidents + user_public_incidents
        
        # Get active officers count
        active_officers = police_officers_collection.count_documents({'status': 'active'})
        
        # Get assigned cases count
        assigned_count = assigned_cases_collection.count_documents({})
        unassigned_count = total_incidents - assigned_count
        
        print(f"🔍 DASHBOARD COUNTS:")
        print(f"   Police Incidents: {total_police_incidents}")
        print(f"   Public Incidents: {total_public_incidents}")
        print(f"   Resolved Cases: {resolved_from_cases}")
        print(f"   TOTAL (Police+Public): {total_incidents}")
        print(f"   Active: {active_incidents}")
        print(f"   Resolved (All): {total_resolved_incidents}")
        print(f"   User Assigned: {user_incidents}")
        print(f"   Assigned Cases: {assigned_count}")
        print(f"   Unassigned Cases: {unassigned_count}")
        print(f"   Recent Incidents Found: {len(recent_incidents)}")
        
        return render_template('dashboard.html', 
                             incidents=recent_incidents,
                             total_incidents=total_incidents,
                             active_incidents=active_incidents,
                             resolved_incidents=total_resolved_incidents,
                             user_incidents=user_incidents,
                             active_officers=active_officers,
                             assigned_count=assigned_count,
                             unassigned_count=unassigned_count)
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        # Return safe defaults if there's an error
        return render_template('dashboard.html', 
                             incidents=[],
                             total_incidents=0,
                             active_incidents=0,
                             resolved_incidents=0,
                             user_incidents=0,
                             active_officers=0,
                             assigned_count=0,
                             unassigned_count=0)
    
@app.route('/api/reverse-geocode')
@login_required
def reverse_geocode():
    """API endpoint to get address from coordinates"""
    try:
        lat = request.args.get('lat')
        lng = request.args.get('lng')
        
        if not lat or not lng:
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        address = get_address_from_coordinates(float(lat), float(lng))
        return jsonify({'address': address})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# In the register route, update the duplicate check section:
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        police_station = request.form.get('police_station')
        ward_number = request.form.get('ward_number')
        police_station_reg_no = request.form.get('police_station_reg_no')  # 6-digit registration number
        
        # Validation
        if not all([password, confirm_password, police_station, ward_number, police_station_reg_no]):
            flash('All fields are required', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        # Validate 6-digit registration number
        if not re.match(r'^\d{6}$', police_station_reg_no):
            flash('Police Station Registration Number must be exactly 6 digits', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        # Check if registration number already exists
        if POLICE_users.find_one({'police_station_reg_no': police_station_reg_no}):
            flash('This Police Station Registration Number is already registered', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        # Check if police station with same ward number is already registered
        existing_station = POLICE_users.find_one({
            'police_station': police_station,
            'ward_number': ward_number
        })
        
        if existing_station:
            flash(f'{police_station} (Ward: {ward_number}) is already registered. Please login instead.', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        # Also check if same police station exists with different ward number
        same_station_diff_ward = POLICE_users.find_one({'police_station': police_station})
        if same_station_diff_ward:
            existing_ward = same_station_diff_ward.get('ward_number', 'Not specified')
            flash(f'{police_station} is already registered with Ward: {existing_ward}. Each police station can only register once.', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        # Enhanced password validation
        password_regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
        if not re.match(password_regex, password):
            flash('Password must contain at least 8 characters including uppercase, lowercase, number, and special character', 'danger')
            return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
        
        try:
            # Generate username from police station name and registration number
            base_username = re.sub(r'[^a-zA-Z0-9]', '', police_station).lower()[:15]
            reg_suffix = police_station_reg_no[-4:]
            username = f"{base_username}_{reg_suffix}"
            
            # Check if username already exists, append number if needed
            counter = 1
            original_username = username
            while POLICE_users.find_one({'username': username}):
                username = f"{original_username}_{counter}"
                counter += 1
                if counter > 100:  # Safety limit
                    flash('Too many similar police station registrations', 'danger')
                    return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)
            
            # Generate email from police station
            email = f"{username}@karnatakapolice.gov.in"
            
            # Generate full name from police station
            full_name = police_station
            
            # Create new user with new fields
            new_user = {
                'username': username,
                'email': email,
                'password_hash': hash_password(password),
                'police_station': police_station,
                'police_station_reg_no': police_station_reg_no,  # Store registration number
                'ward_number': ward_number,
                'full_name': full_name,
                'designation': 'Police Station Admin',
                'role': 'police_admin',
                'status': 'active',
                'created_at': datetime.now(timezone.utc),
                'last_login': None
            }
            
            result = POLICE_users.insert_one(new_user)
            
            # Also add to police_officers collection
            officer_data = {
                'user_id': result.inserted_id,
                'username': username,
                'email': email,
                'police_station': police_station,
                'police_station_reg_no': police_station_reg_no,
                'ward_number': ward_number,
                'full_name': full_name,
                'designation': 'Police Station Admin',
                'status': 'active',
                'created_at': datetime.now(timezone.utc)
            }
            
            police_officers_collection.insert_one(officer_data)
            
            # Auto-login after registration
            user = User(new_user)
            login_user(user)
            flash(f'Registration successful! Welcome {police_station} (Ward: {ward_number})! Your username is: {username}', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'danger')
    
    return render_template('register.html', police_stations=KARNATAKA_POLICE_STATIONS)

@app.route('/api/check-station-availability', methods=['POST'])
def check_station_availability():
    """API endpoint to check if police station is available for registration"""
    try:
        data = request.get_json()
        police_station = data.get('police_station')
        ward_number = data.get('ward_number')
        
        if not police_station:
            return jsonify({'error': 'Police station name is required'}), 400
        
        # Check if police station is already registered
        existing_station = POLICE_users.find_one({'police_station': police_station})
        
        if existing_station:
            existing_ward = existing_station.get('ward_number', 'Not specified')
            return jsonify({
                'available': False,
                'message': f'{police_station} is already registered with Ward: {existing_ward}.',
                'existing_ward': existing_ward
            })
        
        return jsonify({
            'available': True,
            'message': f'{police_station} is available for registration.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        police_station = request.form.get('police_station')
        police_station_reg_no = request.form.get('police_station_reg_no')
        password = request.form.get('password')
        
        try:
            # Find user by police station and registration number
            user_data = POLICE_users.find_one({
                'police_station': police_station,
                'police_station_reg_no': police_station_reg_no
            })
            
            if user_data and check_password(user_data['password_hash'], password):
                user = User(user_data)
                login_user(user)
                
                # Update last login
                POLICE_users.update_one(
                    {'_id': ObjectId(user.id)},
                    {'$set': {'last_login': datetime.now(timezone.utc)}}
                )
                
                flash(f'Welcome back to {police_station}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))
            else:
                flash('Invalid police station, registration number, or password', 'danger')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'danger')
    
    # Get registered police stations for dropdown
    registered_stations = POLICE_users.distinct('police_station')
    return render_template('login.html', registered_stations=registered_stations)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/incidents')
@login_required
def incidents():
    """Display all incidents page - from BOTH incidents and incidents_police collections"""
    try:
        print("🔄 Loading incidents from BOTH collections...")
        
        # Get incidents from BOTH collections
        police_incidents = list(incidents_police_collection.find().sort('created_at', -1))
        public_incidents = list(incidents_collection.find().sort('created_at', -1))
        
        print(f"📊 Found {len(police_incidents)} police incidents and {len(public_incidents)} public incidents")
        
        # Process both collections
        all_incidents = []
        
        # Process police incidents
        for incident in police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            incident_data['assignment_data'] = assignment
            all_incidents.append(incident_data)
        
        # Process public incidents
        for incident in public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            incident_data['assignment_data'] = assignment
            all_incidents.append(incident_data)
        
        # Sort all incidents by creation date (newest first)
        all_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Calculate statistics
        total_incidents = len(all_incidents)
        police_count = len([inc for inc in all_incidents if inc['source'] == 'police'])
        public_count = len([inc for inc in all_incidents if inc['source'] == 'public'])
        high_severity_count = len([inc for inc in all_incidents if inc['severity'] == 'high'])
        active_count = len([inc for inc in all_incidents if inc['status'] == 'active'])
        resolved_count = len([inc for inc in all_incidents if inc['status'] == 'resolved'])
        assigned_count = len([inc for inc in all_incidents if inc['is_assigned']])
        unassigned_count = total_incidents - assigned_count
        
        # Get officers for assignment dropdown
        active_officers = list(police_officers_collection.find({'status': 'active'}))
        
        print(f"✅ Sending {total_incidents} total incidents to template ({police_count} police, {public_count} public)")
        print(f"📋 Assignment stats: {assigned_count} assigned, {unassigned_count} unassigned")
        
        return render_template('incidents.html', 
                             all_incidents=all_incidents,
                             total_incidents=total_incidents,
                             police_count=police_count,
                             public_count=public_count,
                             high_severity_count=high_severity_count,
                             active_count=active_count,
                             resolved_count=resolved_count,
                             assigned_count=assigned_count,
                             unassigned_count=unassigned_count,
                             officers=active_officers)
        
    except Exception as e:
        print(f"❌ Error in incidents route: {e}")
        import traceback
        traceback.print_exc()
        return render_template('incidents.html', 
                             all_incidents=[],
                             total_incidents=0,
                             police_count=0,
                             public_count=0,
                             high_severity_count=0,
                             active_count=0,
                             resolved_count=0,
                             assigned_count=0,
                             unassigned_count=0,
                             officers=[])

@app.route('/api/incidents')
@login_required
def api_incidents():
    """API endpoint to get incidents data from BOTH collections"""
    try:
        # Get incidents from BOTH collections
        police_incidents = list(incidents_police_collection.find())
        public_incidents = list(incidents_collection.find())
        
        incidents_data = []
        
        # Process police incidents
        for incident in police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            # Create serializable response
            response_item = {
                'id': str(incident_data['_id']),  # Convert ObjectId to string
                'incident_id': incident_data['incident_id'],
                'title': incident_data['title'],
                'description': incident_data['description'],
                'type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'status': incident_data['status'],
                'lat': incident_data['latitude'],
                'lng': incident_data['longitude'],
                'address': incident_data['address'],
                'reported_by': incident_data['reported_by'],
                'assigned_officer': incident_data['assigned_officer'],
                'source': 'police',
                'is_assigned': assignment is not None
            }
            
            # Handle datetime serialization
            if 'created_at' in incident_data:
                if isinstance(incident_data['created_at'], datetime):
                    response_item['created_at'] = incident_data['created_at'].isoformat()
                else:
                    response_item['created_at'] = str(incident_data['created_at'])
            
            incidents_data.append(response_item)
        
        # Process public incidents
        for incident in public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            response_item = {
                'id': str(incident_data['_id']),  # Convert ObjectId to string
                'incident_id': incident_data['incident_id'],
                'title': incident_data['title'],
                'description': incident_data['description'],
                'type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'status': incident_data['status'],
                'lat': incident_data['latitude'],
                'lng': incident_data['longitude'],
                'address': incident_data['address'],
                'reported_by': incident_data['reported_by'],
                'assigned_officer': incident_data['assigned_officer'],
                'source': 'public',
                'is_assigned': assignment is not None
            }
            
            # Handle datetime serialization
            if 'created_at' in incident_data:
                if isinstance(incident_data['created_at'], datetime):
                    response_item['created_at'] = incident_data['created_at'].isoformat()
                else:
                    response_item['created_at'] = str(incident_data['created_at'])
            
            incidents_data.append(response_item)
        
        return jsonify(incidents_data)
    except Exception as e:
        print(f"Error in api_incidents: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
# Add new incident
@app.route('/api/incidents', methods=['POST'])
@login_required
def add_incident():
    """API endpoint to add new incident"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('title') or not data.get('description'):
            return jsonify({'error': 'Title and description are required'}), 400
        
        # Get address from coordinates if not provided
        address = data.get('address')
        if not address and data.get('latitude') and data.get('longitude'):
            address = get_address_from_coordinates(data.get('latitude'), data.get('longitude'))
        
        new_incident = {
            'incident_id': f'POL-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}',
            'title': data.get('title'),
            'description': data.get('description'),
            'incident_type': data.get('incident_type', 'Other'),
            'severity': data.get('severity', 'medium'),
            'status': data.get('status', 'active'),
            'latitude': float(data.get('latitude', 14.4664)),
            'longitude': float(data.get('longitude', 75.9238)),
            'address': address or 'Unknown Location',
            'reported_by': current_user.username,
            'assigned_officer': data.get('assigned_officer', current_user.username),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
            'location_details': data.get('location_details', {})
        }
        
        result = incidents_police_collection.insert_one(new_incident)
        
        return jsonify({
            'message': 'Incident added successfully',
            'incident_id': new_incident['incident_id'],
            'id': str(result.inserted_id)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update incident
# Get incident details - FIXED VERSION
@app.route('/api/incidents/<incident_id>/details')
@login_required
def get_incident_details(incident_id):
    """API endpoint to get detailed incident information - SIMPLE FIX"""
    try:
        source = request.args.get('source', 'police')
        
        incident_data = None
        assignment = None
        
        if source == 'police':
            incident = incidents_police_collection.find_one({'_id': ObjectId(incident_id)})
            if incident:
                incident_data = process_police_incident(incident)
        else:
            incident = incidents_collection.find_one({'_id': ObjectId(incident_id)})
            if incident:
                incident_data = process_public_incident(incident)
        
        if not incident_data:
            return jsonify({'error': 'Incident not found'}), 404
        
        # Check assignment status
        assignment = assigned_cases_collection.find_one({
            'incident_id': incident_id
        })
        
        # MANUALLY CREATE A JSON-SERIALIZABLE RESPONSE
        response_data = {
            'id': str(incident_data.get('_id', '')),  # Convert to string
            'incident_id': incident_data.get('incident_id', ''),
            'title': incident_data.get('title', ''),
            'description': incident_data.get('description', ''),
            'incident_type': incident_data.get('incident_type', ''),
            'severity': incident_data.get('severity', ''),
            'status': incident_data.get('status', ''),
            'latitude': float(incident_data.get('latitude', 0)),
            'longitude': float(incident_data.get('longitude', 0)),
            'address': incident_data.get('address', ''),
            'reported_by': incident_data.get('reported_by', ''),
            'assigned_officer': incident_data.get('assigned_officer', ''),
            'source': source,
            'is_assigned': assignment is not None
        }
        
        # Handle datetime serialization
        created_at = incident_data.get('created_at')
        if created_at:
            if isinstance(created_at, datetime):
                response_data['created_at'] = created_at.isoformat()
            else:
                response_data['created_at'] = str(created_at)
        else:
            response_data['created_at'] = ''
        
        updated_at = incident_data.get('updated_at')
        if updated_at:
            if isinstance(updated_at, datetime):
                response_data['updated_at'] = updated_at.isoformat()
            else:
                response_data['updated_at'] = str(updated_at)
        else:
            response_data['updated_at'] = response_data['created_at']
        
        # Add assignment data if exists
        if assignment:
            response_data['assignment_data'] = {
                'assigned_officer': assignment.get('assigned_officer', ''),
                'assigned_by': assignment.get('assigned_by', ''),
                'assigned_at': assignment.get('assigned_at', '').isoformat() if isinstance(assignment.get('assigned_at'), datetime) else str(assignment.get('assigned_at', '')),
                'status': assignment.get('status', '')
            }
        
        print(f"✅ Sending incident details: {incident_data.get('title')}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ Error in get_incident_details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/assigned-cases')
@login_required
def get_assigned_cases():
    """API endpoint to get all assigned cases from ASSIGNED_CASES collection"""
    try:
        # Get all assigned cases
        assigned_cases = list(assigned_cases_collection.find().sort('assigned_at', -1))
        
        cases_data = []
        
        for case in assigned_cases:
            # Get incident data from the appropriate collection
            incident_id = case.get('incident_id')
            source = case.get('source_collection', 'police')
            
            incident_data = None
            
            if source == 'police':
                incident = incidents_police_collection.find_one({'_id': ObjectId(incident_id)})
                if incident:
                    incident_data = process_police_incident(incident)
            else:
                incident = incidents_collection.find_one({'_id': ObjectId(incident_id)})
                if incident:
                    incident_data = process_public_incident(incident)
            
            if incident_data:
                # Create a JSON-serializable response
                case_response = {
                    'assignment_data': {
                        'assigned_officer': case.get('assigned_officer'),
                        'assigned_by': case.get('assigned_by'),
                        'assigned_at': case.get('assigned_at').isoformat() if isinstance(case.get('assigned_at'), datetime) else str(case.get('assigned_at')),
                        'status': case.get('status', 'assigned')
                    },
                    'incident_data': {
                        '_id': str(incident_data.get('_id', '')),
                        'id': str(incident_data.get('_id', '')),
                        'incident_id': incident_data.get('incident_id', ''),
                        'title': incident_data.get('title', ''),
                        'description': incident_data.get('description', ''),
                        'incident_type': incident_data.get('incident_type', ''),
                        'severity': incident_data.get('severity', ''),
                        'status': incident_data.get('status', ''),
                        'latitude': float(incident_data.get('latitude', 0)),
                        'longitude': float(incident_data.get('longitude', 0)),
                        'address': incident_data.get('address', ''),
                        'reported_by': incident_data.get('reported_by', ''),
                        'assigned_officer': incident_data.get('assigned_officer', ''),
                        'source': source,
                        'created_at': incident_data.get('created_at').isoformat() if isinstance(incident_data.get('created_at'), datetime) else str(incident_data.get('created_at'))
                    }
                }
                
                cases_data.append(case_response)
        
        print(f"✅ Returning {len(cases_data)} assigned cases")
        return jsonify(cases_data)
        
    except Exception as e:
        print(f"❌ Error in get_assigned_cases: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
# NEW: Assign officer to incident
@app.route('/api/incidents/<incident_id>/assign-officer', methods=['PUT'])
@login_required
def assign_officer_to_incident(incident_id):
    """API endpoint to assign officer to incident - FIXED VERSION"""
    try:
        print(f"🔍 ASSIGNMENT REQUEST for incident: {incident_id}")
        data = request.get_json()
        source = data.get('source', 'police')
        assigned_officer = data.get('assigned_officer')
        
        print(f"   Request data: {data}")
        print(f"   Source: {source}")
        print(f"   Assigned Officer: {assigned_officer}")
        
        if not assigned_officer:
            print("❌ No officer specified")
            return jsonify({'error': 'Officer username is required'}), 400
        
        # Determine which collection to update based on source
        if source == 'police':
            collection = incidents_police_collection
            print("   Using police collection")
        else:
            collection = incidents_collection
            print("   Using public collection")
        
        # Get the incident data first
        try:
            incident = collection.find_one({'_id': ObjectId(incident_id)})
            if not incident:
                print(f"❌ Incident not found: {incident_id}")
                return jsonify({'message': 'Incident not found'}), 404
            print(f"✅ Found incident: {incident.get('title', 'No title')}")
        except Exception as e:
            print(f"❌ Error finding incident: {e}")
            return jsonify({'error': f'Invalid incident ID: {str(e)}'}), 400
        
        # Process incident data for storage
        if source == 'police':
            processed_incident = process_police_incident(incident)
        else:
            processed_incident = process_public_incident(incident)
        
        print(f"   Processed incident keys: {list(processed_incident.keys())}")
        
        # Check if case is already assigned
        existing_assignment = assigned_cases_collection.find_one({
            'incident_id': incident_id
        })
        
        if existing_assignment:
            print(f"⚠️ Incident already assigned to: {existing_assignment.get('assigned_officer')}")
            # Still update the assignment
            assigned_cases_collection.update_one(
                {'_id': existing_assignment['_id']},
                {'$set': {
                    'assigned_officer': assigned_officer,
                    'assigned_by': current_user.username,
                    'assigned_at': datetime.now(timezone.utc),
                    'last_updated': datetime.now(timezone.utc)
                }}
            )
            print(f"✅ Updated existing assignment")
            assignment_id = existing_assignment['_id']
        else:
            # Assign case to officer in the new collection
            assignment_id = assign_case_to_officer(
                incident_id, 
                source, 
                assigned_officer, 
                processed_incident
            )
            
            if not assignment_id:
                print("❌ assign_case_to_officer returned None")
                return jsonify({'error': 'Failed to assign case in database'}), 500
        
        print(f"✅ Case assigned with ID: {assignment_id}")
        
        # CRITICAL FIX: Update the original incident with assigned officer
        try:
            result = collection.update_one(
                {'_id': ObjectId(incident_id)},
                {'$set': {
                    'assigned_officer': assigned_officer,
                    'updated_at': datetime.now(timezone.utc)
                }}
            )
            
            print(f"✅ Original incident updated: {result.modified_count} document(s) modified")
            
            if result.modified_count > 0:
                # Also update the processed incident data
                processed_incident['assigned_officer'] = assigned_officer
                processed_incident['updated_at'] = datetime.now(timezone.utc)
                
                # Update the assignment record with updated incident data
                assigned_cases_collection.update_one(
                    {'_id': assignment_id},
                    {'$set': {
                        'incident_data': processed_incident,
                        'last_updated': datetime.now(timezone.utc)
                    }}
                )
                
                return jsonify({
                    'message': 'Officer assigned successfully!',
                    'assignment_id': str(assignment_id),
                    'assigned_officer': assigned_officer,
                    'updated_original': True
                })
            else:
                print(f"⚠️ No documents modified in original collection")
                # Still return success if assignment was created
                return jsonify({
                    'message': 'Officer assigned (original incident not updated)',
                    'assignment_id': str(assignment_id),
                    'assigned_officer': assigned_officer,
                    'updated_original': False
                })
        except Exception as e:
            print(f"⚠️ Error updating original incident: {e}")
            # Still return success if assignment was created
            return jsonify({
                'message': 'Officer assigned (with note about original incident)',
                'assignment_id': str(assignment_id),
                'assigned_officer': assigned_officer,
                'warning': 'Could not update original incident',
                'error_details': str(e)
            })
    except Exception as e:
        print(f"❌ Unhandled error in assign_officer_to_incident: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Get police officers - FILTERED by current user's police station
@app.route('/api/police-officers')
@login_required
def get_police_officers():
    """API endpoint to get police officers - FILTERED by current user's police station"""
    try:
        # Get officers from the same police station as current user
        officers = list(police_officers_collection.find({
            'police_station': current_user.police_station,
            'status': 'active'
        }))
        
        officers_data = []
        for officer in officers:
            officers_data.append({
                '_id': str(officer['_id']),  # Add ID for reference
                'username': officer.get('username', ''),
                'full_name': officer.get('full_name', ''),
                'badge_number': officer.get('badge_number', ''),
                'designation': officer.get('designation', 'Police Officer'),
                'email': officer.get('email', ''),
                'phone': officer.get('phone', ''),
                'police_station': officer.get('police_station', ''),
                'rank': officer.get('designation', 'Police Officer')  # For compatibility
            })
        
        print(f"🔍 Returning {len(officers_data)} officers from station: {current_user.police_station}")
        return jsonify(officers_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add police officer (from dashboard) - UPDATED VERSION

@app.route('/api/police-officers', methods=['POST'])
@login_required
def add_police_officer():
    """API endpoint to add new police officer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['badge_number', 'full_name', 'designation', 'email']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
        
        # Use current user's police station (not from form)
        police_station = current_user.police_station
        
        # Generate a username if not provided
        username = data.get('username')
        if not username:
            # Create username from full name and badge number
            base_username = data.get('full_name', '').lower().replace(' ', '.')
            badge_suffix = data.get('badge_number', '')[-4:]
            username = f"{base_username}.{badge_suffix}" if badge_suffix else base_username
        
        # Check if officer already exists (by badge number or email)
        existing_officer = police_officers_collection.find_one({
            '$or': [
                {'badge_number': data.get('badge_number')},
                {'email': data.get('email')},
                {'username': username}
            ]
        })
        
        if existing_officer:
            return jsonify({'error': 'Officer with this badge number, email or username already exists'}), 400
        
        # Create new officer record with username
        new_officer = {
            'badge_number': data.get('badge_number'),
            'full_name': data.get('full_name'),
            'designation': data.get('designation'),
            'police_station': police_station,  # Use current user's station
            'email': data.get('email'),
            'username': username,
            'phone': data.get('phone', ''),
            'status': 'active',
            'created_by': current_user.username,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        result = police_officers_collection.insert_one(new_officer)
        
        return jsonify({
            'message': 'Police officer added successfully',
            'officer_id': str(result.inserted_id),
            'officer': {
                'badge_number': new_officer['badge_number'],
                'full_name': new_officer['full_name'],
                'designation': new_officer['designation'],
                'police_station': new_officer['police_station'],
                'username': new_officer['username']
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Update user profile
@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    """API endpoint to update user profile"""
    try:
        data = request.get_json()
        
        update_data = {
            'email': data.get('email'),
            'full_name': data.get('full_name'),
            'designation': data.get('designation'),
            'ward_number': data.get('ward_number'),  # Keep only ward number
            'updated_at': datetime.now(timezone.utc)
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        result = POLICE_users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'message': 'Profile updated successfully'})
        else:
            return jsonify({'message': 'Profile update failed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live-locations')
@login_required
def live_locations():
    """API endpoint to get real-time incident locations from both collections"""
    try:
        # Get only active incidents for live tracking from both collections
        active_incidents_police = list(incidents_police_collection.find(
            {'status': 'active'},
            {'latitude': 1, 'longitude': 1, 'title': 1, 'severity': 1, 'incident_type': 1}
        ))
        
        active_incidents_public = list(incidents_collection.find(
            {'status': 'active'},
            {'latitude': 1, 'longitude': 1, 'title': 1, 'severity': 1, 'incident_type': 1}
        ))
        
        locations_data = []
        
        # Process police incidents
        for incident in active_incidents_police:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            locations_data.append({
                'id': incident_data['_id'],
                'lat': incident_data['latitude'],
                'lng': incident_data['longitude'],
                'title': incident_data['title'],
                'type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'source': 'police',
                'is_assigned': assignment is not None
            })
        
        # Process public incidents
        for incident in active_incidents_public:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            locations_data.append({
                'id': incident_data['_id'],
                'lat': incident_data['latitude'],
                'lng': incident_data['longitude'],
                'title': incident_data['title'],
                'type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'source': 'public',
                'is_assigned': assignment is not None
            })
        
        return jsonify(locations_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add new API endpoint to get assignment status
@app.route('/api/incidents/<incident_id>/assignment-status')
@login_required
def get_assignment_status(incident_id):
    """API endpoint to check if incident is assigned"""
    try:
        assignment = assigned_cases_collection.find_one({
            'incident_id': incident_id
        })
        
        if assignment:
            return jsonify({
                'is_assigned': True,
                'assigned_officer': assignment.get('assigned_officer'),
                'assigned_at': assignment.get('assigned_at').isoformat(),
                'assigned_by': assignment.get('assigned_by')
            })
        else:
            return jsonify({'is_assigned': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reports')
@login_required
def reports():
    """Reports page - Show incidents from police and public collections only (exclude resolved_cases from total)"""
    try:
        # Get report data from police and public collections ONLY
        total_police_incidents = incidents_police_collection.count_documents({})
        total_public_incidents = incidents_collection.count_documents({})
        
        # Active incidents from police and public
        active_police_incidents = incidents_police_collection.count_documents({'status': 'active'})
        active_public_incidents = incidents_collection.count_documents({'status': 'active'})
        
        # Get resolved incidents from ALL sources (for resolved count only)
        resolved_police = incidents_police_collection.count_documents({'status': 'resolved'})
        resolved_public = incidents_collection.count_documents({'status': 'resolved'})
        resolved_cases = db.resolved_cases.count_documents({})
        
        # High severity incidents from police and public only
        high_severity_police = incidents_police_collection.count_documents({'severity': 'high'})
        high_severity_public = incidents_collection.count_documents({'severity': 'high'})
        
        # Get assigned cases count
        assigned_count = assigned_cases_collection.count_documents({})
        
        # CORRECTED: Total incidents = police + public ONLY (exclude resolved_cases)
        incident_stats = {
            'total': total_police_incidents + total_public_incidents,  # Police + Public only
            'active': active_police_incidents + active_public_incidents,
            'resolved': resolved_police + resolved_public + resolved_cases,  # All resolved sources
            'high_severity': high_severity_police + high_severity_public,  # Police + Public only
            'assigned': assigned_count
        }
        
        print(f"📊 REPORTS COUNTS: Total={incident_stats['total']} (Police+Public only), Active={incident_stats['active']}, Resolved={incident_stats['resolved']}, Assigned={incident_stats['assigned']}")
        
        # Pass current time to template
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        
        return render_template('reports.html', stats=incident_stats, current_time=current_time)
    except Exception as e:
        print(f"Reports error: {e}")
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        flash(f'Error loading reports: {e}', 'danger')
        return render_template('reports.html', stats={}, current_time=current_time)

# Export CSV - Only police incidents
# Export CSV - BOTH police and public incidents
@app.route('/reports/export/csv')
@login_required
def export_csv():
    try:
        # Get incidents from BOTH collections
        incidents_police = list(incidents_police_collection.find())
        incidents_public = list(incidents_collection.find())
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header with additional field for source
        writer.writerow(['Source', 'Incident ID', 'Title', 'Type', 'Severity', 'Status', 'Address', 'Reported By', 'Assigned Officer', 'Created At', 'Latitude', 'Longitude'])
        
        # Write police incidents data
        for incident in incidents_police:
            created_at = incident.get('created_at', '')
            if created_at and isinstance(created_at, datetime):
                created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_str = str(created_at) if created_at else ''
                
            writer.writerow([
                'Police',
                incident.get('incident_id', ''),
                incident.get('title', ''),
                incident.get('incident_type', ''),
                incident.get('severity', ''),
                incident.get('status', ''),
                incident.get('address', ''),
                incident.get('reported_by', ''),
                incident.get('assigned_officer', ''),
                created_str,
                incident.get('latitude', ''),
                incident.get('longitude', '')
            ])
        
        # Write public incidents data
        for incident in incidents_public:
            incident_data = process_public_incident(incident)
            created_at = incident_data['created_at']
            if isinstance(created_at, datetime):
                created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_str = str(created_at)
                
            writer.writerow([
                'Public',
                incident_data['incident_id'],
                incident_data['title'],
                incident_data['incident_type'],
                incident_data['severity'],
                incident_data['status'],
                incident_data['address'],
                incident_data['reported_by'],
                incident_data['assigned_officer'],
                created_str,
                incident_data['latitude'],
                incident_data['longitude']
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=swiftaid_all_incidents_export.csv"}
        )
    except Exception as e:
        flash(f'Error exporting CSV: {e}', 'danger')
        return redirect(url_for('reports'))

# Export PDF - All incidents from all collections including resolved cases
@app.route('/reports/export/pdf')
@login_required
def export_pdf():
    try:
        # Create a BytesIO buffer for the PDF
        buffer = io.BytesIO()
        
        # Create the PDF object using the buffer
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Get data from ALL collections
        incidents_police = list(incidents_police_collection.find().sort('created_at', -1))
        incidents_public = list(incidents_collection.find().sort('created_at', -1))
        resolved_cases = list(db.resolved_cases.find().sort('resolved_at', -1))
        assigned_cases = list(assigned_cases_collection.find().sort('assigned_at', -1))
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Center aligned
            textColor=colors.HexColor('#0d6efd')
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            textColor=colors.HexColor('#2c3e50')
        )
        
        normal_style = styles["Normal"]
        
        # Title
        title = Paragraph("SWIFTAID POLICE DEPARTMENT - COMPLETE INCIDENTS REPORT", title_style)
        elements.append(title)
        
        # Report metadata
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        metadata_text = f"""
        <b>Generated on:</b> {current_time}<br/>
        <b>Total Incidents:</b> {len(incidents_police) + len(incidents_public) + len(resolved_cases)}<br/>
        <b>Police Incidents:</b> {len(incidents_police)} | <b>Public Incidents:</b> {len(incidents_public)} | <b>Resolved Cases:</b> {len(resolved_cases)}<br/>
        <b>Assigned Cases:</b> {len(assigned_cases)}<br/>
        <b>Generated by:</b> {current_user.username}<br/>
        <b>Police Station:</b> {current_user.police_station}
        """
        metadata = Paragraph(metadata_text, normal_style)
        elements.append(metadata)
        elements.append(Spacer(1, 20))
        
        # Police Incidents Section
        if incidents_police:
            police_title = Paragraph("POLICE INCIDENTS", heading_style)
            elements.append(police_title)
            
            # Create table for police incidents
            police_data = [['ID', 'Title', 'Type', 'Severity', 'Status', 'Location', 'Reported', 'Officer']]
            
            for incident in incidents_police:
                created_at = incident.get('created_at', '')
                if created_at:
                    if isinstance(created_at, datetime):
                        created_str = created_at.strftime('%m/%d/%Y')
                    else:
                        created_str = str(created_at)[:10]
                else:
                    created_str = 'Unknown'
                
                police_data.append([
                    incident.get('incident_id', 'N/A')[:8],
                    incident.get('title', 'No Title')[:20],
                    incident.get('incident_type', 'Unknown')[:15],
                    incident.get('severity', 'medium').title(),
                    incident.get('status', 'pending').title(),
                    incident.get('address', 'Unknown')[:15],
                    created_str,
                    incident.get('assigned_officer', 'Unassigned')[:12]
                ])
            
            police_table = Table(police_data, colWidths=[0.6*inch, 1.2*inch, 0.8*inch, 0.6*inch, 0.6*inch, 1.0*inch, 0.6*inch, 0.8*inch])
            police_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(police_table)
            elements.append(Spacer(1, 20))
        
        # Public Incidents Section
        if incidents_public:
            public_title = Paragraph("PUBLIC INCIDENTS", heading_style)
            elements.append(public_title)
            
            # Create table for public incidents
            public_data = [['ID', 'Title', 'Type', 'Severity', 'Status', 'Location', 'Reported By']]
            
            for incident in incidents_public:
                incident_data = process_public_incident(incident)
                created_at = incident_data.get('created_at', '')
                if created_at:
                    if isinstance(created_at, datetime):
                        created_str = created_at.strftime('%m/%d/%Y')
                    else:
                        created_str = str(created_at)[:10]
                else:
                    created_str = 'Unknown'
                
                public_data.append([
                    incident_data['incident_id'][:8],
                    incident_data['title'][:20],
                    incident_data['incident_type'][:15],
                    incident_data['severity'].title(),
                    incident_data['status'].title(),
                    incident_data['address'][:15],
                    incident_data['reported_by'][:12]
                ])
            
            public_table = Table(public_data, colWidths=[0.6*inch, 1.2*inch, 0.8*inch, 0.6*inch, 0.6*inch, 1.0*inch, 0.8*inch])
            public_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(public_table)
            elements.append(Spacer(1, 20))
        
        # Assigned Cases Section
        if assigned_cases:
            assigned_title = Paragraph("ASSIGNED CASES", heading_style)
            elements.append(assigned_title)
            
            # Create table for assigned cases
            assigned_data = [['Incident ID', 'Title', 'Assigned Officer', 'Assigned By', 'Assigned At']]
            
            for case in assigned_cases:
                assigned_at = case.get('assigned_at', '')
                if assigned_at:
                    if isinstance(assigned_at, datetime):
                        assigned_str = assigned_at.strftime('%m/%d/%Y')
                    else:
                        assigned_str = str(assigned_at)[:10]
                else:
                    assigned_str = 'Unknown'
                
                incident_data = case.get('incident_data', {})
                assigned_data.append([
                    incident_data.get('incident_id', 'N/A')[:8],
                    incident_data.get('title', 'No Title')[:20],
                    case.get('assigned_officer', 'Unknown')[:15],
                    case.get('assigned_by', 'Unknown')[:12],
                    assigned_str
                ])
            
            assigned_table = Table(assigned_data, colWidths=[0.8*inch, 1.2*inch, 0.8*inch, 0.8*inch, 0.6*inch])
            assigned_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#198754')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8f5e8')),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(assigned_table)
            elements.append(Spacer(1, 20))
        
        # Resolved Cases Section
        if resolved_cases:
            resolved_title = Paragraph("RESOLVED CASES", heading_style)
            elements.append(resolved_title)
            
            # Create table for resolved cases
            resolved_data = [['ID', 'Title', 'Type', 'Severity', 'Location', 'Resolved By', 'Resolved At']]
            
            for case in resolved_cases:
                resolved_at = case.get('resolved_at', '')
                if resolved_at:
                    if isinstance(resolved_at, datetime):
                        resolved_str = resolved_at.strftime('%m/%d/%Y')
                    else:
                        resolved_str = str(resolved_at)[:10]
                else:
                    resolved_str = 'Unknown'
                
                resolved_data.append([
                    case.get('incident_id', 'N/A')[:8],
                    case.get('title', 'No Title')[:20],
                    case.get('incident_type', 'Unknown')[:15],
                    case.get('severity', 'medium').title(),
                    case.get('address', 'Unknown')[:15],
                    case.get('resolved_by', 'Unknown')[:12],
                    resolved_str
                ])
            
            resolved_table = Table(resolved_data, colWidths=[0.6*inch, 1.2*inch, 0.8*inch, 0.6*inch, 1.0*inch, 0.8*inch, 0.6*inch])
            resolved_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(resolved_table)
            elements.append(Spacer(1, 20))
        
        # Summary Statistics
        summary_title = Paragraph("SUMMARY STATISTICS", heading_style)
        elements.append(summary_title)
        
        active_police = len([inc for inc in incidents_police if inc.get('status') == 'active'])
        active_public = len([inc for inc in incidents_public if process_public_incident(inc).get('status') == 'active'])
        
        high_severity_police = len([inc for inc in incidents_police if inc.get('severity') == 'high'])
        high_severity_public = len([inc for inc in incidents_public if process_public_incident(inc).get('severity') == 'high'])
        high_severity_resolved = len([case for case in resolved_cases if case.get('severity') == 'high'])
        
        summary_data = [
            ['Category', 'Police', 'Public', 'Resolved', 'Assigned', 'Total'],
            ['Total Incidents', len(incidents_police), len(incidents_public), len(resolved_cases), len(assigned_cases), len(incidents_police) + len(incidents_public) + len(resolved_cases)],
            ['Active', active_police, active_public, 0, len(assigned_cases), active_police + active_public],
            ['High Severity', high_severity_police, high_severity_public, high_severity_resolved, 0, high_severity_police + high_severity_public + high_severity_resolved]
        ]
        
        summary_table = Table(summary_data, colWidths=[1.2*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6f42c1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(summary_table)
        
        # Footer note
        elements.append(Spacer(1, 20))
        footer = Paragraph(
            "<i>This report was generated automatically by the SwiftAid Police System. " +
            "For official use only.</i>",
            ParagraphStyle(
                'Footer',
                parent=normal_style,
                fontSize=8,
                textColor=colors.gray,
                alignment=1
            )
        )
        elements.append(footer)
        
        # Build PDF
        doc.build(elements)
        
        # Get the value from the buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create response with proper PDF headers
        response = Response(
            pdf,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'attachment;filename=swiftaid_complete_incidents_report.pdf',
                'Content-Type': 'application/pdf'
            }
        )
        
        return response
        
    except Exception as e:
        print(f"PDF export error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error exporting PDF: {e}', 'danger')
        return redirect(url_for('reports'))

# Export Excel - All incidents from both collections (CSV format)
@app.route('/reports/export/excel')
@login_required
def export_excel():
    try:
        incidents_police = list(incidents_police_collection.find())
        incidents_public = list(incidents_collection.find())
        
        # Create a BytesIO object for binary data
        output = io.BytesIO()
        
        # Use csv writer with proper encoding
        output.write(b'\xef\xbb\xbf')  # UTF-8 BOM for Excel compatibility
        
        # Create a text wrapper for the BytesIO object
        text_output = io.TextIOWrapper(output, encoding='utf-8', newline='')
        writer = csv.writer(text_output)
        
        # Write header
        writer.writerow(['Source', 'Incident ID', 'Title', 'Type', 'Severity', 'Status', 'Address', 'Reported By', 'Assigned Officer', 'Created At', 'Latitude', 'Longitude'])
        
        # Write police incidents data
        for incident in incidents_police:
            created_at = incident.get('created_at', '')
            if created_at and isinstance(created_at, datetime):
                created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_str = str(created_at) if created_at else ''
                
            writer.writerow([
                'Police',
                incident.get('incident_id', ''),
                incident.get('title', ''),
                incident.get('incident_type', ''),
                incident.get('severity', ''),
                incident.get('status', ''),
                incident.get('address', ''),
                incident.get('reported_by', ''),
                incident.get('assigned_officer', ''),
                created_str,
                incident.get('latitude', ''),
                incident.get('longitude', '')
            ])
        
        # Write public incidents data
        for incident in incidents_public:
            incident_data = process_public_incident(incident)
            created_at = incident_data['created_at']
            if isinstance(created_at, datetime):
                created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            else:
                created_str = str(created_at)
                
            writer.writerow([
                'Public',
                incident_data['incident_id'],
                incident_data['title'],
                incident_data['incident_type'],
                incident_data['severity'],
                incident_data['status'],
                incident_data['address'],
                incident_data['reported_by'],
                incident_data['assigned_officer'],
                created_str,
                incident_data['latitude'],
                incident_data['longitude']
            ])
        
        # Flush the text wrapper and get the bytes
        text_output.flush()
        csv_data = output.getvalue()
        text_output.close()
        output.close()
        
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=swiftaid_incidents_export.csv"}
        )
    except Exception as e:
        print(f"Excel export error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error exporting Excel: {e}', 'danger')
        return redirect(url_for('reports'))

@app.route('/database')
@login_required
def database():
    """Database search page with recent incidents and complete statistics"""
    try:
        # Get recent incidents from BOTH collections (ALL statuses)
        recent_police_incidents = list(incidents_police_collection.find().sort('created_at', -1).limit(5))
        recent_public_incidents = list(incidents_collection.find().sort('created_at', -1).limit(5))
        
        # Combine and process incidents
        recent_incidents = []
        
        # Process police incidents
        for incident in recent_police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Process public incidents
        for incident in recent_public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Sort by creation date (newest first) and take top 5
        recent_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        recent_incidents = recent_incidents[:5]
        
        # Get complete stats same as dashboard page
        total_police_incidents = incidents_police_collection.count_documents({})
        total_public_incidents = incidents_collection.count_documents({})
        
        # Total incidents = police + public (EXCLUDING resolved_cases)
        total_incidents = total_police_incidents + total_public_incidents
        
        # Active incidents = only active status from police and public
        active_police_incidents = incidents_police_collection.count_documents({'status': 'active'})
        active_public_incidents = incidents_collection.count_documents({'status': 'active'})
        active_incidents = active_police_incidents + active_public_incidents
        
        # Resolved incidents = resolved from police + resolved from public + resolved_cases
        resolved_police_incidents = incidents_police_collection.count_documents({'status': 'resolved'})
        resolved_public_incidents = incidents_collection.count_documents({'status': 'resolved'})
        resolved_from_cases = db.resolved_cases.count_documents({})
        total_resolved_incidents = resolved_police_incidents + resolved_public_incidents + resolved_from_cases
        
        # Get incidents assigned to current user from police and public collections only
        user_police_incidents = incidents_police_collection.count_documents({'assigned_officer': current_user.username})
        user_public_incidents = incidents_collection.count_documents({'assigned_officer': current_user.username})
        user_incidents = user_police_incidents + user_public_incidents
        
        # Get active officers count
        active_officers = police_officers_collection.count_documents({'status': 'active'})
        
        # Get assigned cases count
        assigned_count = assigned_cases_collection.count_documents({})
        unassigned_count = total_incidents - assigned_count
        
        print(f"📊 DATABASE PAGE COUNTS:")
        print(f"   Police Incidents: {total_police_incidents}")
        print(f"   Public Incidents: {total_public_incidents}")
        print(f"   Resolved Cases: {resolved_from_cases}")
        print(f"   TOTAL (Police+Public): {total_incidents}")
        print(f"   Active: {active_incidents}")
        print(f"   Resolved (All): {total_resolved_incidents}")
        print(f"   User Assigned: {user_incidents}")
        print(f"   Assigned Cases: {assigned_count}")
        print(f"   Unassigned Cases: {unassigned_count}")
        print(f"   Recent Incidents Found: {len(recent_incidents)}")
        
        return render_template('database.html', 
                             incidents=recent_incidents,
                             total_incidents=total_incidents,
                             active_incidents=active_incidents,
                             resolved_incidents=total_resolved_incidents,
                             user_incidents=user_incidents,
                             active_officers=active_officers,
                             assigned_count=assigned_count,
                             unassigned_count=unassigned_count)
    except Exception as e:
        print(f"Database page error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('database.html', 
                             incidents=[],
                             total_incidents=0,
                             active_incidents=0,
                             resolved_incidents=0,
                             user_incidents=0,
                             active_officers=0,
                             assigned_count=0,
                             unassigned_count=0)
    
# Profile page
@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    try:
        user_data = POLICE_users.find_one({'_id': ObjectId(current_user.id)})
        return render_template('profile.html', user=user_data)
    except Exception as e:
        flash(f'Error loading profile: {e}', 'danger')
        return render_template('profile.html', user=None)

@app.route('/api/police-users-count')
@login_required
def police_users_count():
    """API endpoint to get police users count"""
    try:
        users_count = POLICE_users.count_documents({})
        return jsonify({'count': users_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-incidents')
@login_required
def recent_incidents():
    """API endpoint to get recent incidents for dashboard"""
    try:
        # FIXED: Get recent incidents from BOTH collections (ALL statuses)
        recent_police_incidents = list(incidents_police_collection.find().sort('created_at', -1).limit(5))
        recent_public_incidents = list(incidents_collection.find().sort('created_at', -1).limit(5))
        
        # Combine and process incidents
        recent_incidents = []
        
        # Process police incidents
        for incident in recent_police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Process public incidents
        for incident in recent_public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        # Sort by creation date (newest first) and take top 5
        recent_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        recent_incidents = recent_incidents[:5]
        
        # Convert to JSON serializable format
        incidents_data = []
        for incident in recent_incidents:
            incidents_data.append({
                'id': incident['_id'],
                'title': incident['title'],
                'description': incident['description'],
                'severity': incident['severity'],
                'status': incident['status'],
                'latitude': incident['latitude'],
                'longitude': incident['longitude'],
                'address': incident['address'],
                'source': incident['source'],
                'is_assigned': incident['is_assigned'],
                'created_at': incident['created_at'].isoformat() if hasattr(incident['created_at'], 'isoformat') else incident['created_at']
            })
        
        print(f"🔄 API Recent Incidents: Returning {len(incidents_data)} incidents")
        return jsonify(incidents_data)
        
    except Exception as e:
        print(f"Error in recent incidents API: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/debug/check-assignments')
@login_required
def debug_check_assignments():
    """Debug endpoint to check assignment functionality"""
    try:
        # Check if ASSIGNED_CASES collection exists and is accessible
        collections = db.list_collection_names()
        
        # Try to insert a test document
        test_doc = {
            'test': 'assignment_test',
            'timestamp': datetime.now(timezone.utc),
            'user': current_user.username
        }
        
        result = assigned_cases_collection.insert_one(test_doc)
        
        # Delete the test document
        assigned_cases_collection.delete_one({'_id': result.inserted_id})
        
        return jsonify({
            'status': 'success',
            'collections': collections,
            'assigned_cases_count': assigned_cases_collection.count_documents({}),
            'message': 'ASSIGNED_CASES collection is accessible'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'ASSIGNED_CASES collection has issues'
        }), 500

@app.route('/api/recent-activity')
@login_required
def recent_activity():
    """API endpoint to get recent database activity"""
    try:
        activities = []
        
        # Helper function to get safe time string
        def get_safe_time(time_obj):
            if isinstance(time_obj, datetime):
                return time_obj.strftime('%Y-%m-%d %H:%M')
            elif isinstance(time_obj, str):
                # For string timestamps, just return a simplified version
                if len(time_obj) >= 10:
                    return time_obj[:16]  # Take first 16 chars (YYYY-MM-DD HH:MM)
                else:
                    return "Recently"
            else:
                return "Recently"
        
        # Get recent police incidents
        recent_police_incidents = list(incidents_police_collection.find()
            .sort('created_at', -1)
            .limit(2))
        
        for incident in recent_police_incidents:
            time_str = get_safe_time(incident.get('created_at'))
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            is_assigned = assignment is not None
            
            activities.append({
                'type': 'incident',
                'icon': 'fa-exclamation-triangle',
                'color': 'danger' if incident.get('severity') == 'high' else 'warning',
                'text': f"Police Incident: {incident.get('title', 'Untitled')} {'(Assigned)' if is_assigned else '(Unassigned)'}",
                'time': time_str,
                'timestamp': incident.get('created_at')
            })
        
        # Get recent public incidents
        recent_public_incidents = list(incidents_collection.find()
            .sort('created_at', -1)
            .limit(2))
        
        for incident in recent_public_incidents:
            incident_data = process_public_incident(incident)
            time_str = get_safe_time(incident_data.get('created_at'))
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            is_assigned = assignment is not None
            
            activities.append({
                'type': 'incident',
                'icon': 'fa-exclamation-triangle',
                'color': 'danger' if incident_data.get('severity') == 'high' else 'warning',
                'text': f"Public Alert: {incident_data.get('title', 'Untitled')} {'(Assigned)' if is_assigned else '(Unassigned)'}",
                'time': time_str,
                'timestamp': incident_data.get('created_at')
            })
        
        # Get recent assigned cases
        recent_assignments = list(assigned_cases_collection.find()
            .sort('assigned_at', -1)
            .limit(2))
        
        for assignment in recent_assignments:
            time_str = get_safe_time(assignment.get('assigned_at'))
            activities.append({
                'type': 'assignment',
                'icon': 'fa-user-check',
                'color': 'success',
                'text': f"Case Assigned: {assignment.get('incident_data', {}).get('title', 'Untitled')} to {assignment.get('assigned_officer')}",
                'time': time_str,
                'timestamp': assignment.get('assigned_at')
            })
        
        # Get recent resolved cases
        recent_resolved_cases = list(db.resolved_cases.find()
            .sort('resolved_at', -1)
            .limit(1))
        
        for resolved_case in recent_resolved_cases:
            time_str = get_safe_time(resolved_case.get('resolved_at'))
            activities.append({
                'type': 'resolved',
                'icon': 'fa-check-circle',
                'color': 'success',
                'text': f"Case Resolved: {resolved_case.get('title', 'Untitled')}",
                'time': time_str,
                'timestamp': resolved_case.get('resolved_at')
            })
        
        # Get recent officers
        recent_officers = list(police_officers_collection.find()
            .sort('created_at', -1)
            .limit(2))
        
        for officer in recent_officers:
            time_str = get_safe_time(officer.get('created_at'))
            activities.append({
                'type': 'officer',
                'icon': 'fa-user-plus',
                'color': 'success',
                'text': f"Officer added: {officer.get('full_name', officer.get('username', 'Unknown'))}",
                'time': time_str,
                'timestamp': officer.get('created_at')
            })
        
        # Add system activity
        activities.append({
            'type': 'system',
            'icon': 'fa-sync-alt',
            'color': 'primary',
            'text': 'Database backup completed',
            'time': '1 hour ago',
            'timestamp': None
        })
        
        # Sort activities - handle different timestamp types safely
        def get_safe_sort_key(activity):
            timestamp = activity.get('timestamp')
            if not timestamp:
                return "0000-00-00T00:00:00"
            
            if isinstance(timestamp, datetime):
                return timestamp.isoformat()
            elif isinstance(timestamp, str):
                return timestamp
            else:
                return "0000-00-00T00:00:00"
        
        activities.sort(key=get_safe_sort_key, reverse=True)
        
        return jsonify({'activities': activities[:5]})
        
    except Exception as e:
        print(f"❌ Error getting recent activity: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/public-incidents-count')
@login_required
def public_incidents_count():
    """API endpoint to get public incidents count"""
    try:
        public_count = incidents_collection.count_documents({})
        return jsonify({'count': public_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-stats')
@login_required
def database_stats():
    """API endpoint to get all database statistics"""
    try:
        # Get resolved counts from all sources
        resolved_police = incidents_police_collection.count_documents({'status': 'resolved'})
        resolved_public = incidents_collection.count_documents({'status': 'resolved'})
        resolved_cases = db.resolved_cases.count_documents({})
        
        stats = {
            'police_incidents': incidents_police_collection.count_documents({}),
            'public_incidents': incidents_collection.count_documents({}),
            'resolved_cases': db.resolved_cases.count_documents({}),
            'assigned_cases': assigned_cases_collection.count_documents({}),
            'total_resolved': resolved_police + resolved_public + resolved_cases,  # Total resolved
            'officers': police_officers_collection.count_documents({}),
            'users': POLICE_users.count_documents({}),
            'collections': 6  # incidents_police, police_officers, POLICE_users, incidents, resolved_cases, ASSIGNED_CASES
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Debug routes
@app.route('/debug/database')
def debug_database():
    """Debug route to check database contents"""
    try:
        # Check all collections
        collections_info = {
            'POLICE_users_count': POLICE_users.count_documents({}),
            'incidents_count': incidents_collection.count_documents({}),
            'incidents_police_count': incidents_police_collection.count_documents({}),
            'police_officers_count': police_officers_collection.count_documents({}),
            'assigned_cases_count': assigned_cases_collection.count_documents({}),
        }
        
        # Get sample data from each collection
        police_users_sample = list(POLICE_users.find().limit(3))
        incidents_police_sample = list(incidents_police_collection.find().limit(3))
        incidents_public_sample = list(incidents_collection.find().limit(3))
        police_officers_sample = list(police_officers_collection.find().limit(3))
        assigned_cases_sample = list(assigned_cases_collection.find().limit(3))
        
        return jsonify({
            'collections': collections_info,
            'police_users_sample': police_users_sample,
            'incidents_police_sample': incidents_police_sample,
            'incidents_public_sample': incidents_public_sample,
            'police_officers_sample': police_officers_sample,
            'assigned_cases_sample': assigned_cases_sample,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/incidents-data')
@login_required
def debug_incidents_data():
    """Debug route to see raw incidents data"""
    try:
        public_incidents = list(incidents_collection.find())
        police_incidents = list(incidents_police_collection.find())
        assigned_cases = list(assigned_cases_collection.find())
        
        result = {
            'public_count': len(public_incidents),
            'police_count': len(police_incidents),
            'assigned_cases_count': len(assigned_cases),
            'public_incidents': [],
            'police_incidents': [],
            'assigned_cases': []
        }
        
        for incident in public_incidents:
            incident_data = process_public_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            result['public_incidents'].append({
                'id': incident_data['_id'],
                'title': incident_data['title'],
                'description': incident_data['description'],
                'incident_type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'status': incident_data['status'],
                'address': incident_data['address'],
                'assigned_officer': incident_data['assigned_officer'],
                'created_at': incident_data['created_at'].isoformat(),
                'is_assigned': assignment is not None
            })
        
        for incident in police_incidents:
            incident_data = process_police_incident(incident)
            # Check assignment status
            assignment = assigned_cases_collection.find_one({
                'incident_id': str(incident['_id'])
            })
            
            result['police_incidents'].append({
                'id': incident_data['_id'],
                'title': incident_data['title'],
                'description': incident_data['description'],
                'incident_type': incident_data['incident_type'],
                'severity': incident_data['severity'],
                'status': incident_data['status'],
                'address': incident_data['address'],
                'assigned_officer': incident_data['assigned_officer'],
                'created_at': incident_data['created_at'].isoformat(),
                'is_assigned': assignment is not None
            })
        
        for case in assigned_cases:
            result['assigned_cases'].append({
                'incident_id': case.get('incident_id'),
                'assigned_officer': case.get('assigned_officer'),
                'assigned_by': case.get('assigned_by'),
                'assigned_at': case.get('assigned_at').isoformat() if case.get('assigned_at') else None,
                'incident_title': case.get('incident_data', {}).get('title', 'Unknown')
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-incidents')
@login_required
def test_incidents():
    """Simple test to see incidents from both collections"""
    try:
        # Count incidents in each collection
        police_count = incidents_police_collection.count_documents({})
        public_count = incidents_collection.count_documents({})
        assigned_count = assigned_cases_collection.count_documents({})
        
        # Get sample titles
        police_titles = [inc.get('title', 'No title') for inc in incidents_police_collection.find().limit(3)]
        public_incidents = list(incidents_collection.find().limit(3))
        public_titles = [process_public_incident(inc)['title'] for inc in public_incidents]
        assigned_titles = [case.get('incident_data', {}).get('title', 'No title') for case in assigned_cases_collection.find().limit(3)]
        
        return jsonify({
            'police_collection_count': police_count,
            'public_collection_count': public_count,
            'assigned_cases_count': assigned_count,
            'police_sample_titles': police_titles,
            'public_sample_titles': public_titles,
            'assigned_sample_titles': assigned_titles,
            'total_incidents': police_count + public_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Initialize database
def init_db():
    try:
        print("🔄 Initializing database...")
        
        # Create indexes for the new ASSIGNED_CASES collection
        try:
            assigned_cases_collection.create_index([('incident_id', 1)], unique=True)
            assigned_cases_collection.create_index([('assigned_officer', 1)])
            assigned_cases_collection.create_index([('assigned_at', -1)])
            print("✅ Created indexes for ASSIGNED_CASES collection")
        except Exception as e:
            print(f"ℹ️ ASSIGNED_CASES index creation note: {e}")
        
        # Just fix the badge numbers and skip index creation entirely
        officers_without_badge = police_officers_collection.find({
            '$or': [
                {'badge_number': None},
                {'badge_number': {'$exists': False}}
            ]
        })
        
        badge_updates = 0
        for officer in officers_without_badge:
            new_badge_number = f"BDG-{str(officer['_id'])[-6:].upper()}"
            police_officers_collection.update_one(
                {'_id': officer['_id']},
                {'$set': {'badge_number': new_badge_number}}
            )
            badge_updates += 1
        
        if badge_updates > 0:
            print(f"   ✅ Updated {badge_updates} officers with badge numbers")
        
        print("✅ Database initialization completed")
        
        # Check existing data counts
        existing_police_users = POLICE_users.count_documents({})
        existing_police_incidents = incidents_police_collection.count_documents({})
        existing_public_incidents = incidents_collection.count_documents({})
        existing_officers = police_officers_collection.count_documents({})
        existing_assigned_cases = assigned_cases_collection.count_documents({})
        
        print(f"📊 Current database state:")
        print(f"   👮 POLICE Users: {existing_police_users}")
        print(f"   🚨 Police Incidents: {existing_police_incidents}")
        print(f"   📱 Public Incidents: {existing_public_incidents}")
        print(f"   👥 Police Officers: {existing_officers}")
        print(f"   📋 Assigned Cases: {existing_assigned_cases}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        # Don't crash the app, just log the error
        import traceback
        traceback.print_exc()
@app.route('/debug/resolved-cases')
@login_required
def debug_resolved_cases():
    """Debug route to see resolved cases data"""
    try:
        resolved_cases = list(db.resolved_cases.find())
        
        result = {
            'total_resolved_cases': len(resolved_cases),
            'resolved_cases_data': []
        }
        
        for case in resolved_cases:
            result['resolved_cases_data'].append({
                'id': str(case.get('_id')),
                'incident_id': case.get('incident_id'),
                'title': case.get('title'),
                'incident_type': case.get('incident_type'),
                'severity': case.get('severity'),
                'address': case.get('address'),
                'resolved_by': case.get('resolved_by'),
                'resolved_at': case.get('resolved_at'),
                'has_incident_data': 'incident_data' in case,
                'incident_data_keys': list(case.get('incident_data', {}).keys()) if case.get('incident_data') else []
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/debug/incident-counts')
@login_required
def debug_incident_counts():
    """Debug route to see exact incident counts in all collections"""
    try:
        # Get all incidents from all collections
        police_incidents = list(incidents_police_collection.find())
        public_incidents = list(incidents_collection.find())
        resolved_cases = list(db.resolved_cases.find())
        assigned_cases = list(assigned_cases_collection.find())
        
        # Count by status for police incidents
        police_active = incidents_police_collection.count_documents({'status': 'active'})
        police_resolved = incidents_police_collection.count_documents({'status': 'resolved'})
        police_pending = incidents_police_collection.count_documents({'status': 'pending'})
        
        # Count by status for public incidents
        public_active = incidents_collection.count_documents({'status': 'active'})
        public_resolved = incidents_collection.count_documents({'status': 'resolved'})
        public_pending = incidents_collection.count_documents({'status': 'pending'})
        
        # Show sample data
        police_sample = list(incidents_police_collection.find().limit(3))
        public_sample = list(incidents_collection.find().limit(3))
        resolved_sample = list(db.resolved_cases.find().limit(3))
        assigned_sample = list(assigned_cases_collection.find().limit(3))
        
        return jsonify({
            'counts': {
                'police_incidents_total': len(police_incidents),
                'public_incidents_total': len(public_incidents),
                'resolved_cases_total': len(resolved_cases),
                'assigned_cases_total': len(assigned_cases),
                'calculated_total': len(police_incidents) + len(public_incidents) + len(resolved_cases),
                'police_by_status': {
                    'active': police_active,
                    'resolved': police_resolved,
                    'pending': police_pending
                },
                'public_by_status': {
                    'active': public_active,
                    'resolved': public_resolved,
                    'pending': public_pending
                }
            },
            'samples': {
                'police_incidents': police_sample,
                'public_incidents': public_sample,
                'resolved_cases': resolved_sample,
                'assigned_cases': assigned_sample
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting SwiftAid Police Dashboard...")
    print("📍 Karnataka Police Stations Network")
    print("=" * 50)
    init_db()
    print("=" * 50)
    print("🌐 Starting Flask server on http://127.0.0.1:5000")
    print("🔐 Register police stations at /register")
    print("🐛 Debug routes available at /debug/database, /debug/incidents-data, /test-incidents")
    app.run(debug=True)