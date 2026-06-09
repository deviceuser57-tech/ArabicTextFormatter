# dcos_db.py - إدارة قاعدة بيانات DCOS
import sqlite3
import os
import json
import uuid
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dcos.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # تمكين دعم المفاتيح الخارجية
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول إذا لم تكن موجودة"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. مساحات العمل
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. المشاريع
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );
        """)
        
        # 3. دستور وقواعد المشروع
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_rules (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            rules_json TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
         # 3. إعدادات المشروع
        cursor.execute("""
         CREATE TABLE IF NOT EXISTS project_settings (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            knowledge_web_ratio REAL NOT NULL DEFAULT 0.7, -- 0.0‑1.0, 0.7 means 70% knowledge, 30% web
            document_type TEXT NOT NULL DEFAULT 'General',
            export_style_json TEXT, -- path to JSON file or raw JSON
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
        # 4. المستندات (بدون محتوى أو هيكل)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            current_version_id TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
        # 5. إصدارات المستندات (تخزن المحتوى والهيكل الفعلي)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            content TEXT NOT NULL,
            document_model TEXT NOT NULL, -- JSON
            version_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        """)
        
        # 6. مستودع المعرفة المعمم
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            type TEXT NOT NULL, -- Concept, Definition, Rule, StyleGuide, Reference, Citation, Note
            content TEXT NOT NULL,
            tags TEXT,
            references_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
        # 7. سجل ذاكرة المشروع
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_memory (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            type TEXT NOT NULL, -- Decision, Preference, WritingPattern, OpenQuestion
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)
        
        # إنشاء مساحة عمل افتراضية ومشروع افتراضي إذا كانت قاعدة البيانات فارغة
        cursor.execute("SELECT COUNT(*) FROM workspaces;")
        if cursor.fetchone()[0] == 0:
            ws_id = "default_workspace"
            proj_id = "default_project"
            
            cursor.execute("INSERT INTO workspaces (id, name) VALUES (?, ?);", (ws_id, "مساحة العمل الافتراضية"))
            cursor.execute("INSERT INTO projects (id, workspace_id, name) VALUES (?, ?, ?);", (proj_id, ws_id, "مشروعي الأول"))
            
            default_rules = {
                "language": "Arabic",
                "rtl": True,
                "style": "Formal",
                "citation_required": False,
                "numbering": "Legal",
                "heading_style": "Standard"
            }
            cursor.execute("INSERT INTO project_rules (id, project_id, rules_json) VALUES (?, ?, ?);", 
                           (str(uuid.uuid4()), proj_id, json.dumps(default_rules)))
            
        # Insert default settings for the initial project if not exists
        cursor.execute("SELECT COUNT(*) FROM project_settings WHERE project_id = ?;", (proj_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO project_settings (id, project_id, knowledge_web_ratio, document_type) VALUES (?, ?, ?, ?);",
                           (str(uuid.uuid4()), proj_id, 0.7, 'General'))

# ============================================================
# OPERATIONS: WORKSPACES
# ============================================================
def get_workspaces() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM workspaces ORDER BY created_at DESC;").fetchall()
        return [dict(r) for r in rows]

def create_workspace(name: str) -> Dict[str, Any]:
    ws_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO workspaces (id, name) VALUES (?, ?);", (ws_id, name))
        conn.commit()
    return {"id": ws_id, "name": name}

def delete_workspace(ws_id: str):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workspaces WHERE id = ?;", (ws_id,))
        conn.commit()

# ============================================================
# OPERATIONS: PROJECTS
# ============================================================
def get_projects(workspace_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM projects WHERE workspace_id = ? ORDER BY created_at DESC;", (workspace_id,)).fetchall()
        return [dict(r) for r in rows]

def create_project(workspace_id: str, name: str) -> Dict[str, Any]:
    proj_id = str(uuid.uuid4())
    default_rules = {
        "language": "Arabic",
        "rtl": True,
        "style": "Formal",
        "citation_required": False,
        "numbering": "Legal",
        "heading_style": "Standard"
    }
    with get_db_connection() as conn:
        conn.execute("INSERT INTO projects (id, workspace_id, name) VALUES (?, ?, ?);", (proj_id, workspace_id, name))
        conn.execute("INSERT INTO project_rules (id, project_id, rules_json) VALUES (?, ?, ?);", 
                     (str(uuid.uuid4()), proj_id, json.dumps(default_rules)))
        conn.commit()
    return {"id": proj_id, "workspace_id": workspace_id, "name": name, "rules": default_rules}

def delete_project(proj_id: str):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?;", (proj_id,))
        conn.commit()

# ============================================================
# OPERATIONS: PROJECT RULES (CONSTITUTION)
# ============================================================
def get_project_rules(project_id: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        row = conn.execute("SELECT rules_json FROM project_rules WHERE project_id = ?;", (project_id,)).fetchone()
        if row:
            return json.loads(row["rules_json"])
    return {}

def update_project_rules(project_id: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    with get_db_connection() as conn:
        # التحقق من الوجود أولاً
        row = conn.execute("SELECT id FROM project_rules WHERE project_id = ?;", (project_id,)).fetchone()
        if row:
            conn.execute("UPDATE project_rules SET rules_json = ? WHERE project_id = ?;", (json.dumps(rules), project_id))
        else:
            conn.execute("INSERT INTO project_rules (id, project_id, rules_json) VALUES (?, ?, ?);", 
                         (str(uuid.uuid4()), project_id, json.dumps(rules)))
        conn.commit()
    return rules

# ============================================================
# OPERATIONS: DOCUMENTS & VERSIONS
# ============================================================
def get_documents(project_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT d.*, v.content, v.document_model, v.version_note, v.created_at as version_created_at
            FROM documents d
            LEFT JOIN document_versions v ON d.current_version_id = v.id
            WHERE d.project_id = ?
            ORDER BY d.updated_at DESC;
        """, (project_id,)).fetchall()
        return [dict(r) for r in rows]

def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute("""
            SELECT d.*, v.content, v.document_model, v.version_note, v.created_at as version_created_at
            FROM documents d
            LEFT JOIN document_versions v ON d.current_version_id = v.id
            WHERE d.id = ?;
        """, (doc_id,)).fetchone()
        return dict(row) if row else None

def create_document(project_id: str, title: str, content: str = "", document_model: str = "[]") -> Dict[str, Any]:
    doc_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        # 1. إنشاء الحاوية
        conn.execute("INSERT INTO documents (id, project_id, title, current_version_id) VALUES (?, ?, ?, ?);", 
                     (doc_id, project_id, title, version_id))
        # 2. إنشاء الإصدار الأول
        conn.execute("INSERT INTO document_versions (id, document_id, content, document_model, version_note) VALUES (?, ?, ?, ?, ?);",
                     (version_id, doc_id, content, document_model, "الإصدار الأول"))
        conn.commit()
    return get_document(doc_id)

def add_document_version(doc_id: str, content: str, document_model: str, version_note: str = "") -> Dict[str, Any]:
    version_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        # 1. إدراج الإصدار الجديد
        conn.execute("INSERT INTO document_versions (id, document_id, content, document_model, version_note) VALUES (?, ?, ?, ?, ?);",
                     (version_id, doc_id, content, document_model, version_note))
        # 2. تحديث الحاوية للإشارة إلى الإصدار الجديد
        conn.execute("UPDATE documents SET current_version_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", 
                     (version_id, doc_id))
        conn.commit()
    return get_document(doc_id)

def get_document_versions(doc_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM document_versions WHERE document_id = ? ORDER BY created_at DESC;", (doc_id,)).fetchall()
        return [dict(r) for r in rows]

def restore_document_version(doc_id: str, version_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        # التأكد من صحة وجود الإصدار لنفس المستند
        row = conn.execute("SELECT id FROM document_versions WHERE id = ? AND document_id = ?;", (version_id, doc_id)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE documents SET current_version_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", 
                     (version_id, doc_id))
        conn.commit()
    return get_document(doc_id)

def update_document_title(doc_id: str, title: str):
    with get_db_connection() as conn:
        conn.execute("UPDATE documents SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (title, doc_id))
        conn.commit()

def delete_document(doc_id: str):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?;", (doc_id,))
        conn.commit()

# ============================================================
# OPERATIONS: KNOWLEDGE ITEMS
# ============================================================
def get_knowledge_items(project_id: str, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        if item_type:
            rows = conn.execute("SELECT * FROM knowledge_items WHERE project_id = ? AND type = ? ORDER BY created_at DESC;", 
                                (project_id, item_type)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM knowledge_items WHERE project_id = ? ORDER BY created_at DESC;", 
                                (project_id,)).fetchall()
        return [dict(r) for r in rows]

def create_knowledge_item(project_id: str, title: str, item_type: str, content: str, tags: str = "", references_text: str = "") -> Dict[str, Any]:
    item_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO knowledge_items (id, project_id, title, type, content, tags, references_text)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (item_id, project_id, title, item_type, content, tags, references_text))
        conn.commit()
    return {"id": item_id, "project_id": project_id, "title": title, "type": item_type, "content": content, "tags": tags, "references_text": references_text}

def delete_knowledge_item(item_id: str):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM knowledge_items WHERE id = ?;", (item_id,))
        conn.commit()

# ============================================================
# OPERATIONS: PROJECT MEMORY
# ============================================================
def get_project_memory(project_id: str, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        if memory_type:
            rows = conn.execute("SELECT * FROM project_memory WHERE project_id = ? AND type = ? ORDER BY created_at DESC;", 
                                (project_id, memory_type)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM project_memory WHERE project_id = ? ORDER BY created_at DESC;", 
                                (project_id,)).fetchall()
        return [dict(r) for r in rows]

def create_memory_item(project_id: str, memory_type: str, content: str) -> Dict[str, Any]:
    item_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute("INSERT INTO project_memory (id, project_id, type, content) VALUES (?, ?, ?, ?);", 
                     (item_id, project_id, memory_type, content))
        conn.commit()
    return {"id": item_id, "project_id": project_id, "type": memory_type, "content": content}

def delete_memory_item(item_id: str):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM project_memory WHERE id = ?;", (item_id,))
        conn.commit()

# تهيئة قاعدة البيانات عند استيراد الملف
init_db()
