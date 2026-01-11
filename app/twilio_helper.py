from twilio.rest import Client
from .models import SystemSetting

def get_twilio_client():
    sid = SystemSetting.get_value('TWILIO_ACCOUNT_SID')
    token = SystemSetting.get_value('TWILIO_AUTH_TOKEN')
    
    if sid:
        print(f"DEBUG: Using Twilio SID: {sid.strip()[:6]}...{sid.strip()[-4:]}")
    else:
        print("DEBUG: Twilio SID is MISSING/None")

    if token:
         print(f"DEBUG: Twilio Token is present (len={len(token.strip())})")
    else:
         print("DEBUG: Twilio Token is MISSING/None")
         
    if sid and token:
        return Client(sid.strip(), token.strip())
    return None

def send_sms(to, body):
    client = get_twilio_client()
    from_num = SystemSetting.get_value('TWILIO_FROM_NUMBER')
    if client and from_num:
        try:
            client.messages.create(body=body, from_=from_num.strip(), to=to)
            return True
        except Exception as e:
            print(f"Twilio Error: {e}")
            return False
    return False

def start_verification(phone):
    client = get_twilio_client()
    service_sid = SystemSetting.get_value('TWILIO_VERIFY_SERVICE_SID')
    
    # Test Auth specifically
    try:
        client.api.v2010.accounts(client.username).fetch()
        print("DEBUG: Twilio Auth Successful")
    except Exception as e:
        print(f"DEBUG: Twilio Auth FAILED: {e}")
        return f"Auth Failed: {e}"

    if client and service_sid:
        # Basic Formatting for North America if missing
        clean_phone = phone.strip()
        if len(clean_phone) == 10 and clean_phone.isdigit():
             clean_phone = f"+1{clean_phone}"
             print(f"DEBUG: Auto-formatted phone to {clean_phone}")
        
        print(f"DEBUG: Starting Verification. To: {clean_phone}, Service: {service_sid.strip()[:2]}...{service_sid.strip()[-2:]}")
        
        try:
            verification = client.verify.v2.services(service_sid.strip()).verifications.create(to=clean_phone, channel='sms')
            return verification.status
        except Exception as e:
            print(f"Twilio Verify Start Error: {e}")
            return f"Error: {str(e)}"
    return "Config Missing"

def check_verification(phone, code):
    client = get_twilio_client()
    service_sid = SystemSetting.get_value('TWILIO_VERIFY_SERVICE_SID')
    if client and service_sid:
        # Consistency: Apply same formatting
        clean_phone = phone.strip()
        if len(clean_phone) == 10 and clean_phone.isdigit():
             clean_phone = f"+1{clean_phone}"
             
        try:
            verification_check = client.verify.v2.services(service_sid.strip()).verification_checks.create(to=clean_phone, code=code)
            return verification_check.status == 'approved'
        except Exception as e:
            print(f"Verify Check Error: {e}")
            return False
    return False
