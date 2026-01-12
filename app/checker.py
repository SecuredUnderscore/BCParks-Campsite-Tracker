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
            send_notification(alert, new_notifications, site_names, camp_name)
        else:
            if new_notifications:
                logger.info(f"Alert {alert.id}: State updated silently (Sliding Window or First Run).")
            
        # Update State
        alert.last_found_availability = json.dumps(current_findings)
        alert.last_scanned_at = datetime.utcnow()
        
    except Exception as e:
        logger.error(f"Error checking alert {alert.id}: {e}")

def get_campground_name(campground_id):
    # Try fetching details. Since specific API for checking exists, maybe this works?
    # Or just use the map? We don't have the map here easily without DB.
    # We'll try a quick generic fetch if possible, or fallback.
    # We can try fetching the campground details endpoint.
    url = f"https://camping.bcparks.ca/api/resourcelocation/{campground_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            # Try to find name in localized values
            if 'localizedValues' in d and len(d['localizedValues']) > 0:
                return d['localizedValues'][0]['fullName']
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
                names[r['resourceId']] = r['localizedValues'][0]['name']
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

def send_notification(alert, notifications, site_names, camp_name):
    # notifications: list of (res_id, "YYYY-MM-DD:Nights")
    
    logger.info(f"NOTIFICATION FOR ALERT {alert.id}: Found {len(notifications)} slots.")
    
    for res_id, info in notifications:
        date_str, nights = info.split(':')
        
        dt = datetime.strptime(date_str, '%Y-%m-%d').date()
        end_dt = dt + timedelta(days=int(nights))
        
        # Resolve Name
        site_label = site_names.get(res_id, f"Site {res_id}")
        
        url = (
            f"https://camping.bcparks.ca/create-booking/results?"
            f"resourceLocationId={alert.campground_id}&"
            f"mapId={alert.sub_campground_id}&"
            f"startDate={dt.strftime('%Y-%m-%d')}&"
            f"endDate={end_dt.strftime('%Y-%m-%d')}&"
            f"nights={nights}&"
            f"bookingCategoryId=0&equipmentId=-32768&subEquipmentId=-32768"
        )
        
        # Format: Campsite Found! {Campground} site {Site}, {Day} {Start Month} {Start Day} - {End Month} {End Day} for {#} nights. {Link}
        msg = (
            f"Campsite Found! {camp_name} site {site_label}, "
            f"{dt.strftime('%a %b %d')} - {end_dt.strftime('%b %d')} "
            f"for {nights} nights. {url}"
        )
        
        print("\n" + "="*50)
        print(msg)
        print("="*50 + "\n")
        
        
        # Integrate Email/SMS
        # Need to fetch user contacts
        user = alert.user
        contacts = user.contacts 
        
        # Prepare content
        subject = f"BC Parks Alert: Found {len(notifications)} slots!"
        
        # SMS Body (shorter)
        sms_body = f"Found {len(notifications)} slots for {alert.sub_campground_name or 'Map ' + str(alert.sub_campground_id)}. First: {notifications[0][1].split(':')[0]}. Check app!"
        
        from .models import SystemSetting
        from .twilio_helper import send_sms
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        for contact in contacts:
            if contact.method_type == 'sms':
                if contact.is_verified:
                    logger.info(f"Sending SMS to {contact.value}")
                    send_sms(contact.value, sms_body)
                else:
                    logger.warning(f"Skipping SMS to {contact.value} (Not Verified)")
            
            elif contact.method_type == 'email':
                # Email Logic
                provider = SystemSetting.get_value('EMAIL_PROVIDER', 'smtp')
                from_addr = SystemSetting.get_value('EMAIL_FROM')
                
                if provider == 'sendgrid':
                     api_key = SystemSetting.get_value('SENDGRID_API_KEY')
                     if api_key and from_addr:
                        try:
                            from sendgrid import SendGridAPIClient
                            from sendgrid.helpers.mail import Mail
                            
                            message = Mail(
                                from_email=from_addr,
                                to_emails=contact.value,
                                subject=subject,
                                plain_text_content=msg)
                            
                            sg = SendGridAPIClient(api_key)
                            response = sg.send(message)
                            logger.info(f"Sent email via SendGrid to {contact.value} (Status: {response.status_code})")
                        except Exception as e:
                            logger.error(f"SendGrid Email failed: {e}")
                else:
                    # SMTP (Default)
                    host = SystemSetting.get_value('EMAIL_HOST')
                    port = SystemSetting.get_value('EMAIL_PORT')
                    user_email = SystemSetting.get_value('EMAIL_USER')
                    password = SystemSetting.get_value('EMAIL_PASSWORD')
                    
                    if host and port and user_email and password:
                        try:
                            import smtplib
                            from email.mime.text import MIMEText
                            from email.mime.multipart import MIMEMultipart
                            
                            email_msg = MIMEMultipart()
                            email_msg['From'] = from_addr or user_email
                            email_msg['To'] = contact.value
                            email_msg['Subject'] = subject
                            
                            # msg IS the string content defined above
                            email_msg.attach(MIMEText(msg, 'plain'))
                            
                            server = smtplib.SMTP(host, int(port))
                            server.starttls()
                            server.login(user_email, password)
                            server.send_message(email_msg)
                            server.quit()
                            logger.info(f"Sent email via SMTP to {contact.value}")
                        except Exception as e:
                            logger.error(f"SMTP Email failed: {e}")
