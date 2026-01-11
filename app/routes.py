
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from . import db
from .models import User
import requests
import json
import os
from datetime import datetime

main = Blueprint('main', __name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def get_all_campgrounds():
    # Attempt to read from local file first
    local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'resourceLocation')
    data = []
    if os.path.exists(local_path):
        with open(local_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Basic parsing if it contains the URL prefix
            if "https" in content[:10]:
                try:
                    json_text = content.split(': ', 1)[1]
                    data = json.loads(json_text)
                except:
                    pass
            else:
                try:
                    data = json.loads(content)
                except:
                    pass
    
    if not data:
        # Fallback to fetching live
        url = "https://camping.bcparks.ca/api/resourceLocation"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()
        except:
            data = []
    return data

@main.route('/api/proxy/campgrounds')
@login_required
def proxy_campgrounds():
    data = get_all_campgrounds()
    return jsonify(data)



@main.route('/api/proxy/park_data/<resource_location_id>')
@login_required
def proxy_park_data(resource_location_id):
    # Get all maps and resource details for a park
    try:
        # Cast to int for safety inside logic if needed, but URL is string
        # 1. Get Maps (Visuals + Coordinates)
        map_url = f"https://camping.bcparks.ca/api/maps?resourceLocationId={resource_location_id}"
        map_resp = requests.get(map_url, headers=HEADERS, timeout=10)
        
        # 2. Get Resources (Site names, attributes)
        # Note: This can be large, but necessary for tooltips/filtering
        res_url = f"https://camping.bcparks.ca/api/resourcelocation/resources?resourceLocationId={resource_location_id}"
        res_resp = requests.get(res_url, headers=HEADERS, timeout=15)
        
        return jsonify({
            "maps": map_resp.json(),
            "resources": res_resp.json()
        })
    except Exception as e:
         return jsonify({"error": str(e)}), 500



@main.route('/')
@login_required
def index():
    from .models import Alert
    alerts = Alert.query.filter_by(user_id=current_user.id).all()
    
    # Build campground name map
    campgrounds = get_all_campgrounds()
    campground_map = {}
    for cg in campgrounds:
        name = 'Unknown'
        if cg.get('localizedValues') and cg['localizedValues'][0].get('shortName'):
            name = cg['localizedValues'][0]['shortName']
        elif cg.get('shortName'):
            name = cg['shortName']
        elif cg.get('localizedValues') and cg['localizedValues'][0]:
            name = cg['localizedValues'][0]['fullName']
            
        campground_map[cg['resourceLocationId']] = name
        
    # Settings for UI
    from .models import SystemSetting
    scan_interval = int(SystemSetting.get_value('SCAN_INTERVAL_MINUTES', '5'))
    
    return render_template('alerts.html', 
                           alerts=alerts, 
                           campground_map=campground_map,
                           scan_interval=scan_interval,
                           now=datetime.utcnow())

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.index'))
        flash('Invalid credentials')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    if not current_user.is_admin:
        flash("Access Denied")
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            username = request.form.get('username')
            password = request.form.get('password')
            is_admin = request.form.get('is_admin') == 'on'
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists')
            else:
                new_user = User(username=username, is_admin=is_admin)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                db.session.commit()
                flash('User added successfully')
        elif action == 'reset_password':
            user_id = request.form.get('user_id')
            new_pass = request.form.get('new_password')
            user = User.query.get(user_id)
            if user:
                user.set_password(new_pass)
                db.session.commit()
                flash(f'Password updated for {user.username}')

        elif action == 'delete':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if user.id == current_user.id:
                    flash('Cannot delete yourself')
                else:
                    db.session.delete(user)
                    db.session.commit()
                    flash('User deleted')
            

    users = User.query.all()
    return render_template('admin_users.html', users=users)

from .models import User, SystemSetting

@main.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if not current_user.is_admin:
        flash("Access Denied")
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        keys = [
            'SCAN_INTERVAL_MINUTES',
            'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_VERIFY_SERVICE_SID', 'TWILIO_FROM_NUMBER',
            'EMAIL_PROVIDER', 'SENDGRID_API_KEY', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_USER', 'EMAIL_PASSWORD', 'EMAIL_FROM'
        ]
        
        for k in keys:
            val = request.form.get(k)
            # If empty string, decide whether to clear it or ignore.
            # User might want to clear it.
            SystemSetting.set_value(k, val)
            
        flash('Settings updated')
        return redirect(url_for('main.admin_settings'))
    
    # Load all settings
    settings_list = SystemSetting.query.all()
    settings = {s.key: s.value for s in settings_list}
    return render_template('admin_settings.html', settings=settings)

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    from .models import ContactMethod
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_contact':
            method_type = request.form.get('method_type')
            value = request.form.get('value')
            if value:
                contact = ContactMethod(user_id=current_user.id, method_type=method_type, value=value)
                db.session.add(contact)
                db.session.commit()
                flash('Contact method added')
        
        elif action == 'delete_contact':
            contact_id = request.form.get('contact_id')
            contact = ContactMethod.query.get(contact_id)
            if contact and contact.user_id == current_user.id:
                db.session.delete(contact)
                db.session.commit()
                flash('Contact method deleted')
        
        return redirect(url_for('main.settings'))


    contacts = ContactMethod.query.filter_by(user_id=current_user.id).all()
    return render_template('settings.html', contacts=contacts)

@main.route('/alerts/new', methods=['GET', 'POST'])
@main.route('/alerts/edit/<int:alert_id>', methods=['GET', 'POST'])
@login_required
def create_or_edit_alert(alert_id=None):
    from .models import Alert
    from datetime import datetime
    
    alert = None
    if alert_id:
        alert = Alert.query.get_or_404(alert_id)
        if alert.user_id != current_user.id:
            flash('Access denied', 'error')
            return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            camp_id = request.form.get('campground_id')
            sub_id = request.form.get('sub_campground_id')
            sub_name = request.form.get('sub_campground_name')
            
            start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

            min_nights = int(request.form.get('min_nights', 1))
            campsite_ids_raw = request.form.get('campsite_ids')
            
            campsite_ids = []
            if campsite_ids_raw:
                try:
                    campsite_ids = json.loads(campsite_ids_raw)
                except json.JSONDecodeError:
                    if ',' in campsite_ids_raw:
                        campsite_ids = [int(x) for x in campsite_ids_raw.split(',') if x.strip().isdigit()]
                    elif campsite_ids_raw.isdigit():
                         campsite_ids = [int(campsite_ids_raw)]

            if alert:
                # Update Existing
                alert.campground_id = int(camp_id)
                alert.sub_campground_id = int(sub_id) if sub_id else None
                alert.sub_campground_name = sub_name
                alert.start_date = start
                alert.end_date = end
                alert.min_nights = min_nights
                alert.campsite_ids = campsite_ids
                flash('Alert updated successfully!')
            else:
                # Create New
                alert = Alert(
                    user_id=current_user.id,
                    campground_id=int(camp_id),
                    sub_campground_id=int(sub_id) if sub_id else None,
                    sub_campground_name=sub_name,
                    start_date=start,
                    end_date=end,
                    min_nights=min_nights,
                    campsite_ids=campsite_ids
                )
                db.session.add(alert)
                flash('Alert created successfully!')
                
            db.session.commit()
            return redirect(url_for('main.index'))
        except Exception as e:
            flash(f'Error saving alert: {str(e)}')
            
    return render_template('create_alert.html', alert=alert)

@main.route('/alerts/delete', methods=['POST'])
@login_required
def delete_alert():
    from .models import Alert
    alert_id = request.form.get('alert_id')
    alert = Alert.query.get(alert_id)
    if alert and alert.user_id == current_user.id:
        db.session.delete(alert)
        db.session.commit()
        flash('Alert deleted')
    return redirect(url_for('main.index'))

@main.route('/api/verify_phone', methods=['POST'])
@login_required
def verify_phone():
    data = request.json
    action = data.get('action')
    phone = data.get('phone')
    code = data.get('code')
    
    from .models import ContactMethod
    from .twilio_helper import start_verification, check_verification

    contacts = ContactMethod.query.filter_by(user_id=current_user.id, value=phone, method_type='sms').all()
    print(f"DEBUG: Receiving Verification Request. Action={action}, Phone={phone}")
    
    if not contacts:
        print(f"DEBUG: Phone number {phone} not found for user {current_user.id}")
        return jsonify({'success': False, 'message': 'Phone number not found in profile.'}), 404
    
    print(f"DEBUG: Found {len(contacts)} contacts. Starting Twilio process...")
    
    if action == 'start':
        status = start_verification(phone)
        if status == 'Config Missing':
             return jsonify({'error': 'Server Twilio Config Missing'}), 500
        # success if status is pending or approved
        return jsonify({'success': True, 'status': status, 'message': f'Verification started.'})

    elif action == 'check':
        if check_verification(phone, code):
            # Update DB
            for c in contacts:
                c.is_verified = True
            db.session.commit()
            return jsonify({'success': True, 'message': 'Phone verified successfully!'})
        return jsonify({'success': False, 'message': 'Invalid code.'})

    return jsonify({'success': False, 'message': 'Invalid action'})


@main.route('/docs/<topic>')
@login_required
def docs(topic):
    if topic in ['smtp', 'twilio']:
        return render_template(f"help/{topic}.html", title=f"{topic.capitalize()} Setup")
    return "Doc not found", 404

@main.app_template_filter('time_ago')
def time_ago_filter(dt):
    if not dt:
        return "Never"
    
    now = datetime.utcnow()
    # Ensure dt is offset-naive or aware matching now. Assuming UTC naive in DB.
    diff = now - dt
    
    seconds = diff.total_seconds()
    minutes = int(seconds // 60)
    hours = int(minutes // 60)
    days = int(hours // 24)
    
    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if hours < 24:
        return f"{hours} hrs ago"
    return f"{days} days ago"


