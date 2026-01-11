import time
from app import create_app
from flask_apscheduler import APScheduler
from app.checker import check_alerts

if __name__ == '__main__':
    app = create_app()
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    
    # Add Job
    # Check every configured minutes (default 5)
    with app.app_context():
        from app.models import SystemSetting
        interval_minutes = int(SystemSetting.get_value('SCAN_INTERVAL_MINUTES', '5'))
        print(f"DEBUG: Using Scan Interval: {interval_minutes} minutes")

    scheduler.add_job(id='scanner_task', func=check_alerts, args=[app], trigger='interval', minutes=interval_minutes)
    
    print("Worker started. Running scheduler...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Worker stopping...")
