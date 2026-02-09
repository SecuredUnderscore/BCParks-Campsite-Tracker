from twilio.rest import Client
from .models import SystemSetting
import logging

logger = logging.getLogger(__name__)

def get_twilio_client():
    sid = SystemSetting.get_value('TWILIO_ACCOUNT_SID')
    token = SystemSetting.get_value('TWILIO_AUTH_TOKEN')
    
    if not sid or not token:
        logger.error("Twilio credentials missing. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in admin settings.")
        return None
         
    logger.debug(f"Initializing Twilio client with SID: {sid.strip()[:6]}...")
    return Client(sid.strip(), token.strip())

def send_sms(to, body):
    client = get_twilio_client()
    from_num = SystemSetting.get_value('TWILIO_FROM_NUMBER')
    if client and from_num:
        try:
            client.messages.create(body=body, from_=from_num.strip(), to=to)
            logger.info(f"SMS sent to {to[-4:]}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False
    logger.warning("Twilio client or from number not configured")
    return False

def start_verification(phone):
    client = get_twilio_client()
    service_sid = SystemSetting.get_value('TWILIO_VERIFY_SERVICE_SID')
    
    if not client:
        return "Config Missing"
    
    # Test Auth
    try:
        client.api.v2010.accounts(client.username).fetch()
        logger.debug("Twilio authentication successful")
    except Exception as e:
        logger.error(f"Twilio authentication failed: {e}")
        return f"Auth Failed: {e}"

    if service_sid:
        # Basic Formatting for North America if missing
        clean_phone = phone.strip()
        if len(clean_phone) == 10 and clean_phone.isdigit():
             clean_phone = f"+1{clean_phone}"
             logger.debug(f"Auto-formatted phone to {clean_phone}")
        
        logger.info(f"Starting verification for phone ending in {clean_phone[-4:]}")
        
        try:
            verification = client.verify.v2.services(service_sid.strip()).verifications.create(to=clean_phone, channel='sms')
            return verification.status
        except Exception as e:
            logger.error(f"Twilio verification start failed: {e}")
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
            logger.info(f"Verification check for {clean_phone[-4:]}: {verification_check.status}")
            return verification_check.status == 'approved'
        except Exception as e:
            logger.error(f"Verification check failed: {e}")
            return False
    logger.warning("Twilio client or service SID not configured for verification")
    return False
