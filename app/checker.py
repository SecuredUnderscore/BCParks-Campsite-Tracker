import json
import logging
import requests
from datetime import datetime, timedelta
from . import db
from .models import Alert

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

FIRST_RUN = True

def check_alerts(app):
    global FIRST_RUN
    with app.app_context():
        alerts = Alert.query.filter_by(status='active').all()
        logger.info(f"Checking {len(alerts)} active alerts... (First Run: {FIRST_RUN})")
        
        for alert in alerts:
            check_alert(alert, is_first_run=FIRST_RUN)
        
        db.session.commit()
        if FIRST_RUN:
            FIRST_RUN = False

def check_alert(alert, is_first_run=False):
    # 5 Month Hard Limit Check
    now = datetime.now().date()
    limit = now + timedelta(days=150) # Approx 5 months
    
    # Adjust scan window to bounds
    scan_start = max(alert.start_date, now)
    scan_end = min(alert.end_date, limit)
    
    if scan_start > scan_end:
        return # Out of bounds or in past

    # API Request
    # Note: mapId is stored in sub_campground_id (from our recent fix)
    map_id = alert.sub_campground_id 
    if not map_id:
        return # Should not happen if correctly created

    url = "https://camping.bcparks.ca/api/availability/map"
    params = {
        'mapId': map_id,
        'startDate': scan_start.strftime('%Y-%m-%d'),
        'endDate': scan_end.strftime('%Y-%m-%d'),
        'getDailyAvailability': 'true'
    }
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch for alert {alert.id}: {resp.status_code}")
            return
            
        data = resp.json()
        res_avails = data.get('resourceAvailabilities', {})
        
        current_findings = {} # site_id -> [list of start_dates found]
        
        target_sites = alert.campsite_ids
        
        for res_id_str, daily_data in res_avails.items():
            res_id = int(res_id_str)
            
            # Filter by selected sites (if any)
            if target_sites and res_id not in target_sites:
                continue
                
            # Check for consecutive nights
            consecutive = 0
            run_start_idx = -1
            
            for i, day in enumerate(daily_data):
                # User indicated availability is 0 when available?
                # Using == 0 based on user request/speculation.
                val = day.get('availability', -1)
                is_avail = (val == 0) 
                
                if is_avail:
                    if run_start_idx == -1:
                        run_start_idx = i
                    consecutive += 1
                else:
                    # Check if run met criteria
                    if consecutive >= alert.min_nights:
                        add_finding(current_findings, res_id, scan_start, run_start_idx, consecutive)
                    # Reset
                    consecutive = 0
                    run_start_idx = -1
            
            # Check end of list
            if consecutive >= alert.min_nights:
                 add_finding(current_findings, res_id, scan_start, run_start_idx, consecutive)

        # Compare with previous
        previous_findings = {}
        has_previous_state = False
        if alert.last_found_availability:
            try:
                previous_findings = json.loads(alert.last_found_availability)
                has_previous_state = True
            except:
                pass
        
        # Detect NEW findings
        new_notifications = []
        
        for res_id, ranges in current_findings.items():
            prev_ranges = previous_findings.get(str(res_id), [])
            
            for r in ranges: # r is string "YYYY-MM-DD:Nights"
                if r not in prev_ranges:
                    # CHECK FOR SLIDING WINDOW ARTIFACT (Bug Fix)
                    is_shifted = False
                    try:
                        curr_date_str, curr_nights_str = r.split(':')
                        curr_date = datetime.strptime(curr_date_str, '%Y-%m-%d').date()
                        curr_nights = int(curr_nights_str)
                        
                        for pr in prev_ranges:
                            prev_date_str, prev_nights_str = pr.split(':')
                            prev_date = datetime.strptime(prev_date_str, '%Y-%m-%d').date()
                            prev_nights = int(prev_nights_str)
                            
                            # Logic: If Current is exactly Previous + 1 Day, and End Dates match
                            # Prev End = Prev Start + Prev Nights
                            # Curr End = Curr Start + Curr Nights
                            if (curr_date == prev_date + timedelta(days=1)) and \
                               ((curr_date + timedelta(days=curr_nights)) == (prev_date + timedelta(days=prev_nights))):
                                is_shifted = True
                                break
                    except:
                        pass
                    
                    if not is_shifted:
                        new_notifications.append((res_id, r))
        
        # Suppress notification if:
        # 1. No new notifications (obviously)
        # 2. It's the Global First Run (Application Startup)
        # 3. It's likely the First Scan for this alert (No previous state stored)
        should_notify = True
        
        if not new_notifications:
            should_notify = False
        elif is_first_run:
            logger.info(f"Alert {alert.id}: Suppressing notifications (Startup Scan). Found {len(new_notifications)} new slots.")
            should_notify = False
        elif not has_previous_state:
            logger.info(f"Alert {alert.id}: Suppressing notifications (First Alert Scan). Found {len(new_notifications)} new slots.")
            should_notify = False

        if should_notify:
            # Fetch names for better message
            site_names = get_site_names(alert.campground_id)
            camp_name = get_campground_name(alert.campground_id) or "Campground"
            
            # Send ONE notification for all findings to avoid spam, or Individual?
            # User request implies specific format for "Campsite Found!".
            # If we have multiple, let's send them individually to ensure the format matches exaclty what they want.
            # (Loop is already set up for individual processing in extract/format)
            # BUT we should probably reuse the connection?
            
            send_notifications(alert, new_notifications, site_names, camp_name)

        else:
            if new_notifications:
                logger.info(f"Alert {alert.id}: State updated silently (Sliding Window or First Run).")
            
        # Update State
        alert.last_found_availability = json.dumps(current_findings)
        alert.last_scanned_at = datetime.utcnow()
        
    except Exception as e:
        logger.error(f"Error checking alert {alert.id}: {e}")

def get_campground_name(campground_id):
    # Attempt 1: Direct Resource Location API
    url = f"https://camping.bcparks.ca/api/resourcelocation/{campground_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            if 'localizedValues' in d and len(d['localizedValues']) > 0:
                return d['localizedValues'][0]['fullName']
    except:
        pass
        
    # Attempt 2: Fetch All (Fallback)
    try:
        resp = requests.get("https://camping.bcparks.ca/api/resourcelocation", headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            all_camps = resp.json()
            for c in all_camps:
                # String comparison to be safe
                if str(c.get('resourceLocationId')) == str(campground_id):
                    if 'localizedValues' in c and len(c['localizedValues']) > 0:
                        return c['localizedValues'][0]['fullName']
                    elif 'shortName' in c:
                        return c['shortName']
    except:
        pass
        
    return None

def get_site_names(campground_id):
    url = f"https://camping.bcparks.ca/api/resourcelocation/resources?resourceLocationId={campground_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        names = {}
        for r in data:
            if 'resourceId' in r and 'localizedValues' in r and len(r['localizedValues']) > 0:
                # Store as STRING to ensure lookup matches (API IDs can be quirky)
                names[str(r['resourceId'])] = r['localizedValues'][0]['name']
        return names
    except Exception as e:
        logger.warning(f"Failed to fetch site names: {e}")
        return {}

def add_finding(findings, res_id, base_date, idx, nights):
    # Calculate actual start date
    start_date = base_date + timedelta(days=idx)
    key = f"{start_date.strftime('%Y-%m-%d')}:{nights}"
    
    if res_id not in findings:
        findings[res_id] = []
    
    findings[res_id].append(key)

def send_notifications(alert, notifications, site_names, camp_name):
    # notifications: list of (res_id, "YYYY-MM-DD:Nights")
    
    logger.info(f"NOTIFICATION FOR ALERT {alert.id}: Found {len(notifications)} slots.")
    
    # Pre-fetch contacts
    user = alert.user
    contacts = user.contacts
    from .models import SystemSetting
    from .twilio_helper import send_sms
    
    for res_id, info in notifications:
        date_str, nights = info.split(':')
        dt = datetime.strptime(date_str, '%Y-%m-%d').date()
        end_dt = dt + timedelta(days=int(nights))
        
        # Resolve Name (Lookup using STRING key)
        site_label = site_names.get(str(res_id), str(res_id))
        
        url = (
            f"https://camping.bcparks.ca/create-booking/results?"
            f"resourceLocationId={alert.campground_id}&"
            f"mapId={alert.sub_campground_id}&"
            f"startDate={dt.strftime('%Y-%m-%d')}&"
            f"endDate={end_dt.strftime('%Y-%m-%d')}&"
            f"nights={nights}&"
            f"bookingCategoryId=0&equipmentId=-32768&subEquipmentId=-32768"
        )
        
        # EXACT Format requested:
        # Campsite Found! {Campground} site {Site #/Name}, {Day} {Start Month} {Start Day} - {End Month} {End Day} for {#} nights. {Link}
        msg = (
            f"Campsite Found! {camp_name} site {site_label}, "
            f"{dt.strftime('%a %b %d')} - {end_dt.strftime('%b %d')} "
            f"for {nights} nights. {url}"
        )
        
        print(f"SENDING: {msg}")
        
        subject = f"BC Parks: {camp_name} Available!"

        for contact in contacts:
            if contact.method_type == 'sms':
                if contact.is_verified:
                    # USE FULL MSG for SMS as requested
                    send_sms(contact.value, msg)
                else:
                    logger.warning(f"Skipping SMS to {contact.value} (Not Verified)")
            
            elif contact.method_type == 'email':
                send_email(contact.value, subject, msg)

def send_email(to_addr, subject, body):
    from .models import SystemSetting
    provider = SystemSetting.get_value('EMAIL_PROVIDER', 'smtp')
    from_addr = SystemSetting.get_value('EMAIL_FROM')
    
    try:
        if provider == 'sendgrid':
             api_key = SystemSetting.get_value('SENDGRID_API_KEY')
             if api_key and from_addr:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                message = Mail(from_email=from_addr, to_emails=to_addr, subject=subject, plain_text_content=body)
                sg = SendGridAPIClient(api_key)
                sg.send(message)
        else:
            # SMTP
            host = SystemSetting.get_value('EMAIL_HOST')
            port = SystemSetting.get_value('EMAIL_PORT')
            user_email = SystemSetting.get_value('EMAIL_USER')
            password = SystemSetting.get_value('EMAIL_PASSWORD')
            
            if host and port and user_email and password:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                email_msg = MIMEMultipart()
                email_msg['From'] = from_addr or user_email
                email_msg['To'] = to_addr
                email_msg['Subject'] = subject
                email_msg.attach(MIMEText(body, 'plain'))
                
                server = smtplib.SMTP(host, int(port))
                server.starttls()
                server.login(user_email, password)
                server.send_message(email_msg)
                server.quit()
    except Exception as e:
        logging.error(f"Email failed: {e}")
