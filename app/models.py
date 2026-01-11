from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    
    contacts = db.relationship('ContactMethod', backref='user', lazy=True, cascade="all, delete-orphan")
    alerts = db.relationship('Alert', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ContactMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    method_type = db.Column(db.String(20), nullable=False) # 'email' or 'sms'
    value = db.Column(db.String(120), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    campground_id = db.Column(db.Integer, nullable=False)
    sub_campground_id = db.Column(db.Integer, nullable=True)
    sub_campground_name = db.Column(db.String(100), nullable=True)
    
    # Stored as strings "YYYY-MM-DD" or Date objects
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    min_nights = db.Column(db.Integer, default=1)
    
    # Store list of site IDs as JSON string
    _campsite_ids = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default='active') # active, paused, triggered
    last_scanned_at = db.Column(db.DateTime, nullable=True)
    last_found_availability = db.Column(db.Text, nullable=True) # JSON of what we last notified about
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def campsite_ids(self):
        if self._campsite_ids:
            return json.loads(self._campsite_ids)
        return []
    
    @campsite_ids.setter
    def campsite_ids(self, value):
        self._campsite_ids = json.dumps(value)

class SystemSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get_value(key, default=None):
        setting = SystemSetting.query.get(key)
        return setting.value if setting else default
    
    @staticmethod
    def set_value(key, value):
        setting = SystemSetting.query.get(key)
        if not setting:
            setting = SystemSetting(key=key)
            db.session.add(setting)
        setting.value = value
        db.session.commit()
