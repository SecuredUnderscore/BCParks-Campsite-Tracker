from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import logging

db = SQLAlchemy()
login_manager = LoginManager()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
        
    # Use instance path for DB to simplify Docker volume persistence
    db_path = os.path.join(app.instance_path, 'db.sqlite3')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', f'sqlite:///{db_path}')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    from .routes import main
    app.register_blueprint(main)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # Scheduler logic moved to run_worker.py for container separation

    with app.app_context():
        db.create_all()
        # Create default admin if no users exist (configurable via env)
        skip_admin = os.environ.get('SKIP_DEFAULT_ADMIN', 'false').lower() == 'true'
        if not skip_admin and not User.query.first():
            admin_username = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
            admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin')
            logger.info(f"Creating default admin user: {admin_username}")
            admin = User(username=admin_username, is_admin=True)
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            logger.warning(f"Default admin created with username '{admin_username}' - CHANGE THE PASSWORD IMMEDIATELY!")

    return app
