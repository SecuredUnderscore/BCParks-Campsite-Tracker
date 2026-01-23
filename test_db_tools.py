
import os
import tempfile
import shutil
import unittest
from io import BytesIO
from app import create_app, db
from app.models import User, SystemSetting

class TestDBImportExport(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the instance path
        self.test_dir = tempfile.mkdtemp()
        
        # Configure app with this temp dir as instance path
        # We have to patch it or just set it after creation and hope routes usage respects it
        self.app = create_app()
        self.app.instance_path = self.test_dir
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(self.test_dir, 'db.sqlite3')}"
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing
        
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            # Create admin user
            admin = User(username='admin', is_admin=True)
            admin.set_password('original_pass')
            db.session.add(admin)
            db.session.commit()
            
            # Create a setting to track state
            SystemSetting.set_value('TEST_KEY', 'STATE_A')

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_export_import_preservation(self):
        # 1. Login as Admin
        self.login('admin', 'original_pass')
        
        # 2. Export DB (State A: TEST_KEY='STATE_A', password='original_pass')
        resp = self.client.get('/admin/export_db')
        self.assertEqual(resp.status_code, 200)
        exported_data = resp.data
        
        # 3. Change State (State B)
        # Change password
        with self.app.app_context():
            user = User.query.filter_by(username='admin').first()
            user.set_password('new_pass')
            SystemSetting.set_value('TEST_KEY', 'STATE_B')
            db.session.commit()
            
        # Verify State B
        with self.app.app_context():
            self.assertEqual(SystemSetting.get_value('TEST_KEY'), 'STATE_B')
            user = User.query.filter_by(username='admin').first()
            self.assertTrue(user.check_password('new_pass'))
            self.assertFalse(user.check_password('original_pass'))
            
        # 4. Import DB (Should revert to State A data, BUT preserve 'new_pass')
        # We must re-login? Session might still be valid, but let's assume we are "logged in" as per current_user
        # The import logic uses current_user to preserve credentials.
        
        # Since we modified the password in step 3, we technically are logged in with 'original_pass' session 
        # (Flask-Login doesn't auto-logout on DB change usually unless session token is validated against DB hash every request)
        # But wait, we changed the password in DB, but session cookie is arguably stale or valid depending on implementation.
        # Let's re-login with new pass to simulate "Current Admin State".
        self.client.get('/logout')
        self.login('admin', 'new_pass')
        
        data = {
            'db_file': (BytesIO(exported_data), 'backup.sqlite3')
        }
        resp = self.client.post('/admin/import_db', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        
        # 5. Verify Results
        with self.app.app_context():
            # Data should be State A
            self.assertEqual(SystemSetting.get_value('TEST_KEY'), 'STATE_A')
            
            # Password should be State B (Preserved)
            user = User.query.filter_by(username='admin').first()
            self.assertTrue(user.check_password('new_pass'))
            self.assertFalse(user.check_password('original_pass'))

if __name__ == '__main__':
    unittest.main()
