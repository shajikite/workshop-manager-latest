from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import json
import os
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Database configuration from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

@contextmanager
def get_db():
    """Get database connection with context manager for automatic cleanup"""
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set")
    
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = RealDictCursor
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database with all tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Admin table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Participant table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS participant (
                pen_number TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                designation TEXT,
                district TEXT,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Programme table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programme (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                number_of_days INTEGER,
                from_date DATE,
                to_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Programme Participants (enrollment)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programme_participant (
                programme_id INTEGER REFERENCES programme(id) ON DELETE CASCADE,
                pen_number TEXT REFERENCES participant(pen_number) ON DELETE CASCADE,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (programme_id, pen_number)
            )
        ''')
        
        # Participant response for programme
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS participant_response (
                id SERIAL PRIMARY KEY,
                programme_id INTEGER REFERENCES programme(id) ON DELETE CASCADE,
                pen_number TEXT REFERENCES participant(pen_number) ON DELETE CASCADE,
                willingness TEXT,
                attendance_days TEXT,
                arrival_date DATE,
                arrival_time TEXT,
                food_preference TEXT,
                remarks TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(programme_id, pen_number)
            )
        ''')
        
        # Insert default admin if not exists
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        if not cursor.fetchone():
            hashed = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO admin (username, password) VALUES (%s, %s)",
                ('admin', hashed)
            )
        
        print("Database initialized successfully!")

# Initialize database if DATABASE_URL is set
if DATABASE_URL:
    init_db()
else:
    print("Warning: DATABASE_URL not set. Running without database!")

# Authentication decorators
def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def participant_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('participant_logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'database': 'connected'}), 200

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM admin WHERE username = %s AND password = %s",
            (username, password)
        )
        admin = cursor.fetchone()
    
    if admin:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid credentials'})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('index'))

@app.route('/participant/login', methods=['POST'])
def participant_login():
    data = request.json
    pen_number = data.get('pen_number')
    password = hashlib.sha256(data.get('password', '').encode()).hexdigest()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM participant WHERE pen_number = %s AND password = %s",
            (pen_number, password)
        )
        participant = cursor.fetchone()
    
    if participant:
        session['participant_logged_in'] = True
        session['participant_pen'] = pen_number
        session['participant_name'] = participant['name']
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid credentials'})

@app.route('/participant/logout')
def participant_logout():
    session.pop('participant_logged_in', None)
    session.pop('participant_pen', None)
    session.pop('participant_name', None)
    return redirect(url_for('index'))

@app.route('/api/check-auth')
def check_auth():
    return jsonify({
        'admin': session.get('admin_logged_in', False),
        'participant': session.get('participant_logged_in', False),
        'participant_name': session.get('participant_name', '')
    })

# Programme CRUD
@app.route('/api/programmes', methods=['GET'])
def get_programmes():
    with get_db() as conn:
        cursor = conn.cursor()
        if session.get('participant_logged_in'):
            pen = session['participant_pen']
            cursor.execute('''
                SELECT p.*, 
                    1 as is_enrolled,
                    pr.willingness, pr.attendance_days, pr.arrival_date, pr.arrival_time,
                    pr.food_preference, pr.remarks
                FROM programme p
                JOIN programme_participant pp ON p.id = pp.programme_id
                LEFT JOIN participant_response pr ON p.id = pr.programme_id AND pr.pen_number = %s
                WHERE pp.pen_number = %s
                ORDER BY p.from_date DESC
            ''', (pen, pen))
        else:
            cursor.execute('SELECT * FROM programme ORDER BY from_date DESC')
        
        programmes = cursor.fetchall()
    
    return jsonify([dict(row) for row in programmes])

@app.route('/api/programmes', methods=['POST'])
@admin_login_required
def create_programme():
    data = request.json
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO programme (name, description, number_of_days, from_date, to_date)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (data['name'], data['description'], data['number_of_days'], data['from_date'], data['to_date']))
        programme_id = cursor.fetchone()['id']
    
    return jsonify({'success': True, 'id': programme_id})

@app.route('/api/programmes/<int:programme_id>', methods=['PUT'])
@admin_login_required
def update_programme(programme_id):
    data = request.json
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE programme 
            SET name=%s, description=%s, number_of_days=%s, from_date=%s, to_date=%s
            WHERE id=%s
        ''', (data['name'], data['description'], data['number_of_days'], data['from_date'], data['to_date'], programme_id))
    
    return jsonify({'success': True})

@app.route('/api/programmes/<int:programme_id>', methods=['DELETE'])
@admin_login_required
def delete_programme(programme_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM programme_participant WHERE programme_id=%s', (programme_id,))
        cursor.execute('DELETE FROM participant_response WHERE programme_id=%s', (programme_id,))
        cursor.execute('DELETE FROM programme WHERE id=%s', (programme_id,))
    
    return jsonify({'success': True})

# Participant CRUD
@app.route('/api/participants', methods=['GET'])
@admin_login_required
def get_participants():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM participant ORDER BY created_at DESC')
        participants = cursor.fetchall()
    
    return jsonify([dict(row) for row in participants])

@app.route('/api/participants', methods=['POST'])
@admin_login_required
def create_participant():
    data = request.json
    hashed_password = hashlib.sha256(data['password'].encode()).hexdigest()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO participant (pen_number, name, designation, district, password)
                VALUES (%s, %s, %s, %s, %s)
            ''', (data['pen_number'], data['name'], data['designation'], data['district'], hashed_password))
        return jsonify({'success': True})
    except Exception:
        return jsonify({'success': False, 'error': 'PEN number already exists'})

@app.route('/api/participants/<pen_number>', methods=['PUT'])
@admin_login_required
def update_participant(pen_number):
    data = request.json
    with get_db() as conn:
        cursor = conn.cursor()
        if data.get('password'):
            hashed = hashlib.sha256(data['password'].encode()).hexdigest()
            cursor.execute('''
                UPDATE participant SET name=%s, designation=%s, district=%s, password=%s WHERE pen_number=%s
            ''', (data['name'], data['designation'], data['district'], hashed, pen_number))
        else:
            cursor.execute('''
                UPDATE participant SET name=%s, designation=%s, district=%s WHERE pen_number=%s
            ''', (data['name'], data['designation'], data['district'], pen_number))
    
    return jsonify({'success': True})

@app.route('/api/participants/<pen_number>', methods=['DELETE'])
@admin_login_required
def delete_participant(pen_number):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM programme_participant WHERE pen_number=%s', (pen_number,))
        cursor.execute('DELETE FROM participant_response WHERE pen_number=%s', (pen_number,))
        cursor.execute('DELETE FROM participant WHERE pen_number=%s', (pen_number,))
    
    return jsonify({'success': True})

# Enroll participants to programme
@app.route('/api/programmes/<int:programme_id>/enroll', methods=['POST'])
@admin_login_required
def enroll_participants(programme_id):
    data = request.json
    pen_numbers = data.get('pen_numbers', [])
    
    with get_db() as conn:
        cursor = conn.cursor()
        for pen in pen_numbers:
            cursor.execute('''
                INSERT INTO programme_participant (programme_id, pen_number) 
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            ''', (programme_id, pen))
    
    return jsonify({'success': True})

@app.route('/api/programmes/<int:programme_id>/participants', methods=['GET'])
@admin_login_required
def get_programme_participants(programme_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                pr.willingness, pr.attendance_days, pr.arrival_date, pr.arrival_time,
                pr.food_preference, pr.remarks, pr.updated_at as response_date
            FROM participant p
            JOIN programme_participant pp ON p.pen_number = pp.pen_number
            LEFT JOIN participant_response pr ON pp.programme_id = pr.programme_id AND p.pen_number = pr.pen_number
            WHERE pp.programme_id = %s
            ORDER BY p.name
        ''', (programme_id,))
        participants = cursor.fetchall()
    
    return jsonify([dict(row) for row in participants])

@app.route('/api/programmes/<int:programme_id>/remove-participant/<pen_number>', methods=['DELETE'])
@admin_login_required
def remove_participant(programme_id, pen_number):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM programme_participant WHERE programme_id=%s AND pen_number=%s', (programme_id, pen_number))
        cursor.execute('DELETE FROM participant_response WHERE programme_id=%s AND pen_number=%s', (programme_id, pen_number))
    
    return jsonify({'success': True})

# Participant response
@app.route('/api/participant/response', methods=['POST'])
@participant_login_required
def save_response():
    data = request.json
    pen_number = session['participant_pen']
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO participant_response 
            (programme_id, pen_number, willingness, attendance_days, arrival_date, arrival_time, food_preference, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (programme_id, pen_number) 
            DO UPDATE SET 
                willingness = EXCLUDED.willingness,
                attendance_days = EXCLUDED.attendance_days,
                arrival_date = EXCLUDED.arrival_date,
                arrival_time = EXCLUDED.arrival_time,
                food_preference = EXCLUDED.food_preference,
                remarks = EXCLUDED.remarks,
                updated_at = CURRENT_TIMESTAMP
        ''', (data['programme_id'], pen_number, data['willingness'], 
              json.dumps(data.get('attendance_days', [])), data.get('arrival_date'), 
              data.get('arrival_time'), data.get('food_preference'), data.get('remarks')))
    
    return jsonify({'success': True})

# Programme-wise Catering Report (Vegetarian & Non-Vegetarian only)
@app.route('/api/programmes/<int:programme_id>/catering-report')
@admin_login_required
def catering_report(programme_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM programme WHERE id=%s', (programme_id,))
        programme = cursor.fetchone()
        
        cursor.execute('''
            SELECT p.*, 
                pr.willingness, pr.attendance_days, pr.food_preference,
                pr.arrival_date, pr.arrival_time
            FROM participant p
            JOIN programme_participant pp ON p.pen_number = pp.pen_number
            LEFT JOIN participant_response pr ON pp.programme_id = pr.programme_id AND p.pen_number = pr.pen_number
            WHERE pp.programme_id = %s
        ''', (programme_id,))
        participants = cursor.fetchall()
        
        cursor.execute('''
            SELECT p.id, p.name, p.from_date, p.to_date, p.number_of_days,
                   pp.pen_number, pr.food_preference, pr.willingness, pr.attendance_days
            FROM programme p
            JOIN programme_participant pp ON p.id = pp.programme_id
            LEFT JOIN participant_response pr ON p.id = pr.programme_id AND pr.pen_number = pp.pen_number
            WHERE p.id != %s 
            AND p.from_date <= %s 
            AND p.to_date >= %s
            AND pr.willingness = 'Yes'
        ''', (programme_id, programme['to_date'], programme['from_date']))
        overlapping_programmes = cursor.fetchall()
    
    participant_overlaps = {}
    for overlap in overlapping_programmes:
        pen = overlap['pen_number']
        if pen not in participant_overlaps:
            participant_overlaps[pen] = {'food_pref': overlap['food_preference'], 'dates': set()}
        
        from_date = datetime.strptime(overlap['from_date'], '%Y-%m-%d')
        to_date = datetime.strptime(overlap['to_date'], '%Y-%m-%d')
        attendance_days = json.loads(overlap['attendance_days']) if overlap['attendance_days'] else []
        
        current_date = from_date
        while current_date <= to_date:
            date_str = current_date.strftime('%Y-%m-%d')
            if not attendance_days or date_str in attendance_days:
                participant_overlaps[pen]['dates'].add(date_str)
            current_date += timedelta(days=1)
    
    from_date = datetime.strptime(programme['from_date'], '%Y-%m-%d')
    to_date = datetime.strptime(programme['to_date'], '%Y-%m-%d')
    date_range = []
    current_date = from_date
    while current_date <= to_date:
        date_range.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    daily_food = {}
    total_meals_summary = {
        'breakfast': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'morning_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'lunch': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'evening_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'dinner': {'Vegetarian': 0, 'Non-Vegetarian': 0}
    }
    
    for date in date_range:
        daily_food[date] = {
            'breakfast': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'morning_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'lunch': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'evening_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'dinner': {'Vegetarian': 0, 'Non-Vegetarian': 0}
        }
    
    for participant in participants:
        if participant['willingness'] == 'Yes':
            pen = participant['pen_number']
            attendance_days = json.loads(participant['attendance_days']) if participant['attendance_days'] else []
            food_pref = participant['food_preference'] if participant['food_preference'] else 'Vegetarian'
            
            for idx, date in enumerate(date_range):
                attends = not attendance_days or date in attendance_days
                
                if attends:
                    has_overlap = False
                    if pen in participant_overlaps and date in participant_overlaps[pen]['dates']:
                        has_overlap = True
                    
                    if not has_overlap:
                        is_first_day = (idx == 0)
                        is_last_day = (idx == len(date_range) - 1)
                        
                        if not is_first_day:
                            daily_food[date]['breakfast'][food_pref] += 1
                            total_meals_summary['breakfast'][food_pref] += 1
                        
                        daily_food[date]['morning_tea'][food_pref] += 1
                        total_meals_summary['morning_tea'][food_pref] += 1
                        
                        daily_food[date]['lunch'][food_pref] += 1
                        total_meals_summary['lunch'][food_pref] += 1
                        
                        daily_food[date]['evening_tea'][food_pref] += 1
                        total_meals_summary['evening_tea'][food_pref] += 1
                        
                        if not is_last_day:
                            daily_food[date]['dinner'][food_pref] += 1
                            total_meals_summary['dinner'][food_pref] += 1
    
    duplicate_count = 0
    for pen in participant_overlaps:
        for date in participant_overlaps[pen]['dates']:
            if date in date_range:
                duplicate_count += 1
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Catering Report - {programme['name']}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 15px; padding: 30px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 3px solid #3498db; }}
            h1 {{ color: #2c3e50; margin: 0; }}
            h2 {{ color: #34495e; margin: 10px 0 0 0; font-size: 1.3em; }}
            .programme-details {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 30px; }}
            .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
            .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; }}
            .card h3 {{ margin: 0 0 8px 0; font-size: 0.9em; }}
            .card .number {{ font-size: 1.5em; font-weight: bold; margin: 0; }}
            .preference-card {{ background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); }}
            .preference-card-nonveg {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }}
            .meal-section {{ margin-bottom: 30px; }}
            .meal-title {{ font-size: 1.3em; margin: 20px 0 10px 0; padding: 10px; background: #ecf0f1; border-radius: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f8f9fa; }}
            .total-row {{ background: #ecf0f1; font-weight: bold; }}
            .grand-total {{ font-size: 16px; font-weight: bold; margin-top: 20px; padding: 15px; background: #2ecc71; color: white; border-radius: 5px; text-align: center; }}
            @media print {{ body {{ margin: 0; padding: 10px; }} .no-print {{ display: none; }} }}
            .no-print {{ text-align: center; margin-bottom: 20px; }}
            button {{ padding: 10px 20px; margin: 0 5px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="no-print">
                <button onclick="window.print()">🖨️ Print Report</button>
                <button onclick="window.close()">❌ Close</button>
            </div>
            <div class="header">
                <h1>🍽️ Programme-wise Catering Report</h1>
                <h2>{programme['name']}</h2>
            </div>
            <div class="programme-details">
                <p><strong>📅 Dates:</strong> {programme['from_date']} to {programme['to_date']} ({programme['number_of_days']} days)</p>
                <p><strong>👥 Confirmed Participants:</strong> {len([p for p in participants if p['willingness'] == 'Yes'])}</p>
            </div>
    '''
    
    if duplicate_count > 0:
        html += f'<div class="warning-box">⚠️ {duplicate_count} participant-day(s) excluded due to overlapping programmes</div>'
    
    total_veg = sum(total_meals_summary[meal]['Vegetarian'] for meal in total_meals_summary)
    total_nonveg = sum(total_meals_summary[meal]['Non-Vegetarian'] for meal in total_meals_summary)
    
    html += f'''
        <div class="summary-cards">
            <div class="card preference-card">
                <h3>🥬 Vegetarian</h3>
                <p class="number">{total_veg}</p>
            </div>
            <div class="card preference-card-nonveg">
                <h3>🍗 Non-Vegetarian</h3>
                <p class="number">{total_nonveg}</p>
            </div>
        </div>
        <div class="summary-cards">
    '''
    
    for meal in ['breakfast', 'morning_tea', 'lunch', 'evening_tea', 'dinner']:
        meal_total = sum(total_meals_summary[meal].values())
        html += f'<div class="card"><h3>{meal.replace("_", " ").title()}</h3><p class="number">{meal_total}</p></div>'
    html += '</div>'
    
    for meal_name, meal_icon in [('breakfast', '🍳'), ('morning_tea', '☕'), ('lunch', '🍲'), ('evening_tea', '🍪'), ('dinner', '🍽️')]:
        html += f'''
            <div class="meal-section">
                <div class="meal-title">{meal_icon} {meal_name.title()}</div>
                <table>
                    <thead><tr><th>Date</th><th>Day</th><th>🥬 Veg</th><th>🍗 Non-Veg</th><th>Total</th></tr></thead>
                    <tbody>
        '''
        day_count = 1
        total_veg = total_nonveg = 0
        for date in date_range:
            veg = daily_food[date][meal_name]['Vegetarian']
            nonveg = daily_food[date][meal_name]['Non-Vegetarian']
            total_veg += veg
            total_nonveg += nonveg
            html += f'<tr><td>{date}</td><td>Day {day_count}</td><td>{veg}</td><td>{nonveg}</td><td><strong>{veg+nonveg}</strong></td></tr>'
            day_count += 1
        html += f'<tr class="total-row"><td colspan="2"><strong>Total</strong></td><td><strong>{total_veg}</strong></td><td><strong>{total_nonveg}</strong></td><td><strong>{total_veg+total_nonveg}</strong></td></tr>'
        html += '</tbody></table></div>'
    
    grand_total = total_veg + total_nonveg
    html += f'<div class="grand-total"><strong>Total Food Items Required: {grand_total}</strong><br>🥬 Vegetarian: {total_veg} | 🍗 Non-Vegetarian: {total_nonveg}</div>'
    html += '</div></body></html>'
    
    return html

# Date-wise Food Report
@app.route('/api/date-wise-food-report')
@admin_login_required
def date_wise_food_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date:
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Date-wise Food Report</title>
            <style>
                body { font-family: 'Segoe UI', Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                .picker-container { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); text-align: center; }
                h1 { color: #333; margin-bottom: 20px; }
                input { padding: 12px; margin: 10px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
                button { padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; margin-top: 20px; }
                button:hover { transform: translateY(-2px); }
            </style>
        </head>
        <body>
            <div class="picker-container">
                <h1>📅 Date-wise Food Requirement Report</h1>
                <input type="date" id="startDate" placeholder="Start Date">
                <span> to </span>
                <input type="date" id="endDate" placeholder="End Date">
                <br><button onclick="generateReport()">Generate Report</button>
            </div>
            <script>
                function generateReport() {
                    const startDate = document.getElementById('startDate').value;
                    const endDate = document.getElementById('endDate').value;
                    if(startDate && endDate) window.location.href = `/api/date-wise-food-report?start_date=${startDate}&end_date=${endDate}`;
                    else if(startDate) window.location.href = `/api/date-wise-food-report?start_date=${startDate}`;
                    else alert('Please select date');
                }
            </script>
        </body>
        </html>
        '''
    
    if not end_date:
        end_date = start_date
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM programme WHERE from_date <= %s AND to_date >= %s ORDER BY from_date', (end_date, start_date))
        programmes = cursor.fetchall()
    
    date_range = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    while current_date <= end_date_obj:
        date_range.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)
    
    date_wise_food = {}
    for date in date_range:
        date_wise_food[date] = {
            'breakfast': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'morning_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'lunch': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'evening_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
            'dinner': {'Vegetarian': 0, 'Non-Vegetarian': 0}
        }
    
    for programme in programmes:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, pr.willingness, pr.attendance_days, pr.food_preference
                FROM participant p
                JOIN programme_participant pp ON p.pen_number = pp.pen_number
                LEFT JOIN participant_response pr ON pp.programme_id = pr.programme_id AND p.pen_number = pr.pen_number
                WHERE pp.programme_id = %s AND pr.willingness = 'Yes'
            ''', (programme['id'],))
            participants = cursor.fetchall()
        
        prog_from = datetime.strptime(programme['from_date'], '%Y-%m-%d')
        prog_to = datetime.strptime(programme['to_date'], '%Y-%m-%d')
        
        for date in date_range:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            if prog_from <= date_obj <= prog_to:
                day_index = (date_obj - prog_from).days
                is_first_day = (day_index == 0)
                is_last_day = (date_obj == prog_to)
                
                for participant in participants:
                    attendance_days = json.loads(participant['attendance_days']) if participant['attendance_days'] else []
                    food_pref = participant['food_preference'] if participant['food_preference'] else 'Vegetarian'
                    
                    if not attendance_days or date in attendance_days:
                        if not is_first_day:
                            date_wise_food[date]['breakfast'][food_pref] += 1
                        date_wise_food[date]['morning_tea'][food_pref] += 1
                        date_wise_food[date]['lunch'][food_pref] += 1
                        date_wise_food[date]['evening_tea'][food_pref] += 1
                        if not is_last_day:
                            date_wise_food[date]['dinner'][food_pref] += 1
    
    total_by_meal = {
        'breakfast': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'morning_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'lunch': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'evening_tea': {'Vegetarian': 0, 'Non-Vegetarian': 0},
        'dinner': {'Vegetarian': 0, 'Non-Vegetarian': 0}
    }
    
    for date in date_range:
        for meal in total_by_meal:
            for pref in total_by_meal[meal]:
                total_by_meal[meal][pref] += date_wise_food[date][meal][pref]
    
    total_veg = sum(total_by_meal[meal]['Vegetarian'] for meal in total_by_meal)
    total_nonveg = sum(total_by_meal[meal]['Non-Vegetarian'] for meal in total_by_meal)
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Date-wise Food Report</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f0f2f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 15px; padding: 30px; box-shadow: 0 5px 20px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; margin-bottom: 30px; border-bottom: 3px solid #3498db; padding-bottom: 20px; }}
            h1 {{ color: #2c3e50; }}
            .date-range {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }}
            .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
            .card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center; }}
            .card h3 {{ margin: 0 0 8px 0; }}
            .card .number {{ font-size: 1.8em; font-weight: bold; margin: 0; }}
            .preference-card {{ background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); }}
            .preference-card-nonveg {{ background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
            th {{ background-color: #3498db; color: white; }}
            tr:nth-child(even) {{ background-color: #f8f9fa; }}
            .grand-total {{ font-size: 16px; font-weight: bold; margin-top: 20px; padding: 15px; background: #2ecc71; color: white; border-radius: 5px; text-align: center; }}
            @media print {{ body {{ margin: 0; padding: 10px; }} .no-print {{ display: none; }} }}
            .no-print {{ text-align: center; margin-bottom: 20px; }}
            button {{ padding: 10px 20px; margin: 0 5px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="no-print">
                <button onclick="window.print()">🖨️ Print</button>
                <button onclick="window.location.href='/api/date-wise-food-report'">📅 New Report</button>
                <button onclick="window.close()">❌ Close</button>
            </div>
            <div class="header"><h1>📊 Date-wise Food Requirement Report</h1></div>
            <div class="date-range"><strong>Period:</strong> {start_date} to {end_date} ({len(date_range)} days)</div>
            
            <div class="summary-cards">
                <div class="card preference-card">
                    <h3>🥬 Vegetarian</h3>
                    <p class="number">{total_veg}</p>
                </div>
                <div class="card preference-card-nonveg">
                    <h3>🍗 Non-Vegetarian</h3>
                    <p class="number">{total_nonveg}</p>
                </div>
            </div>
            
            <div class="summary-cards">
                <div class="card"><h3>🍳 Breakfast</h3><p class="number">{sum(total_by_meal['breakfast'].values())}</p></div>
                <div class="card"><h3>☕ Morning Tea</h3><p class="number">{sum(total_by_meal['morning_tea'].values())}</p></div>
                <div class="card"><h3>🍲 Lunch</h3><p class="number">{sum(total_by_meal['lunch'].values())}</p></div>
                <div class="card"><h3>🍪 Evening Tea</h3><p class="number">{sum(total_by_meal['evening_tea'].values())}</p></div>
                <div class="card"><h3>🍽️ Dinner</h3><p class="number">{sum(total_by_meal['dinner'].values())}</p></div>
            </div>
            
            <h3>Daily Breakdown with Food Preferences</h3>
            <table>
                <thead><tr><th>Date</th><th>Day</th><th colspan="2">🍳 Breakfast</th><th colspan="2">☕ Morning Tea</th><th colspan="2">🍲 Lunch</th><th colspan="2">🍪 Evening Tea</th><th colspan="2">🍽️ Dinner</th><th>Total</th></tr></thead>
                <thead><tr><th></th><th></th><th>🥬</th><th>🍗</th><th>🥬</th><th>🍗</th><th>🥬</th><th>🍗</th><th>🥬</th><th>🍗</th><th>🥬</th><th>🍗</th><th></th></tr></thead>
                <tbody>
    '''
    
    day_count = 1
    for date in date_range:
        data = date_wise_food[date]
        daily_total = 0
        html += f'<tr><td>{date}</td><td>Day {day_count}</td>'
        for meal in ['breakfast', 'morning_tea', 'lunch', 'evening_tea', 'dinner']:
            veg = data[meal]['Vegetarian']
            nonveg = data[meal]['Non-Vegetarian']
            meal_total = veg + nonveg
            daily_total += meal_total
            html += f'<td>{veg}</td><td>{nonveg}</td>'
        html += f'<td><strong>{daily_total}</strong></td></tr>'
        day_count += 1
    
    grand_total = total_veg + total_nonveg
    html += f'</tbody><tfoot><tr style="background:#ecf0f1;font-weight:bold"><td colspan="2">Total</td>'
    for meal in ['breakfast', 'morning_tea', 'lunch', 'evening_tea', 'dinner']:
        html += f'<td>{total_by_meal[meal]["Vegetarian"]}</td><td>{total_by_meal[meal]["Non-Vegetarian"]}</td>'
    html += f'<td><strong>{grand_total}</strong></td></tr></tfoot></table>'
    html += f'<div class="grand-total"><strong>Total Food Items Required: {grand_total}</strong><br>🥬 Vegetarian: {total_veg} | 🍗 Non-Vegetarian: {total_nonveg}</div>'
    html += '</div></body></html>'
    
    return html

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
