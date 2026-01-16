from app import create_app, db
import sqlalchemy
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Check if column exists
    inspector = sqlalchemy.inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('contact_method')]
    
    if 'sms_count' not in columns:
        print("Adding sms_count column to contact_method table...")
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE contact_method ADD COLUMN sms_count INTEGER DEFAULT 0"))
            conn.commit()
        print("Column added successfully.")
    else:
        print("Column sms_count already exists.")
