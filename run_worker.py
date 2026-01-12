import time
from app import create_app
from flask_apscheduler import APScheduler
from app.checker import check_alerts

if __name__ == '__main__':
    
    app = create_app()

    # ... Original Scheduler Logic for Local Dev / VM ...
    
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    
    # Add Job
    # Check every configured minutes (default 5)
    # Initial Interval
    with app.app_context():
        from app.models import SystemSetting
        current_interval = int(SystemSetting.get_value('SCAN_INTERVAL_MINUTES', '5'))
        print(f"DEBUG: Using Scan Interval: {current_interval} minutes")

    scheduler.add_job(id='scanner_task', func=check_alerts, args=[app], trigger='interval', minutes=current_interval)
    
    # Config Watcher Job
    def check_config_update(app_instance):
        global current_interval
        with app_instance.app_context():
            try:
                from app.models import SystemSetting
                new_interval = int(SystemSetting.get_value('SCAN_INTERVAL_MINUTES', '5'))
                if new_interval != current_interval:
                    print(f"CONFIG CHANGE: Updating scan interval from {current_interval} to {new_interval} minutes.")
                    print(f"CONFIG CHANGE: Updating scan interval from {current_interval} to {new_interval} minutes.")
                    # scheduler.scheduler.reschedule_job(...) might be safer but delete/add is foolproof
                    scheduler.delete_job('scanner_task')
                    scheduler.add_job(id='scanner_task', func=check_alerts, args=[app_instance], trigger='interval', minutes=new_interval)
                    current_interval = new_interval
            except Exception as e:
                print(f"Error checking config: {e}")

    # Run watcher every 1 minute
    scheduler.add_job(id='config_watcher', func=check_config_update, args=[app], trigger='interval', minutes=1)

    print("Worker started. Running scheduler...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Worker stopping...")
