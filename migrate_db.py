
import sqlite3

def migrate():
    try:
        conn = sqlite3.connect('instance/db.sqlite3')
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE alert ADD COLUMN sub_campground_name TEXT")
        conn.commit()
        conn.close()
        print("Migration successful")
    except Exception as e:
        print(f"Migration failed (maybe already exists): {e}")

if __name__ == "__main__":
    migrate()
