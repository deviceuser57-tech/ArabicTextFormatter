import sqlite3
import json
import os
from database import SessionLocal, engine, Base
from models import Workspace, Project, ProjectSetting, Document, DocumentVersion, KnowledgeItem, ProjectMemory

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dcos.db")

def migrate():
    print("Creating new tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Connecting to old raw SQLite database to fetch data...")
    # We will connect to the same file but using raw sqlite3 to bypass ORM temporarily
    # Actually, SQLAlchemy creates tables in the same DB if they don't exist.
    # Since we are reusing the same DB, the old tables already exist!
    # Wait, the old tables are:
    # workspaces, projects, project_rules, project_settings, documents, document_versions, knowledge_items, project_memory.
    # Our new models map directly to them EXCEPT for ProjectSetting which merges rules_json.
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if project_rules exists (indicates old schema)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_rules'")
    has_old_rules = cursor.fetchone() is not None
    
    if has_old_rules:
        print("Old schema detected. Migrating project_rules into project_settings...")
        
        # We also need to add rules_json column to project_settings if it doesn't exist
        try:
            cursor.execute("ALTER TABLE project_settings ADD COLUMN rules_json TEXT NOT NULL DEFAULT '{}'")
            conn.commit()
            print("Added rules_json to project_settings.")
        except sqlite3.OperationalError:
            pass # Column likely already exists
            
        db = SessionLocal()
        
        # Fetch all rules
        old_rules = cursor.execute("SELECT * FROM project_rules").fetchall()
        for rule in old_rules:
            proj_id = rule["project_id"]
            rules_json = rule["rules_json"]
            
            # Find the setting in ORM
            setting = db.query(ProjectSetting).filter(ProjectSetting.project_id == proj_id).first()
            if setting:
                setting.rules_json = rules_json
            else:
                # Create setting if it somehow didn't exist
                new_setting = ProjectSetting(
                    project_id=proj_id,
                    rules_json=rules_json
                )
                db.add(new_setting)
                
        db.commit()
        db.close()
        
        # We can drop the old table now
        print("Dropping old project_rules table...")
        cursor.execute("DROP TABLE project_rules")
        conn.commit()

            
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
