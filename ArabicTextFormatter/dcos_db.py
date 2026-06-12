# dcos_db.py - إدارة قاعدة بيانات DCOS (Refactored to use SQLAlchemy)
import json
import uuid
from typing import List, Dict, Any, Optional

from database import SessionLocal
from models import Workspace, Project, ProjectSetting, Document, DocumentVersion, KnowledgeItem, ProjectMemory

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass # We'll close manually in these helper functions to match old API

# ============================================================
# OPERATIONS: WORKSPACES
# ============================================================
def get_workspaces() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        workspaces = db.query(Workspace).order_by(Workspace.created_at.desc()).all()
        return [{"id": w.id, "name": w.name, "created_at": str(w.created_at)} for w in workspaces]
    finally:
        db.close()

def create_workspace(name: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        ws = Workspace(name=name)
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return {"id": ws.id, "name": ws.name}
    finally:
        db.close()

def delete_workspace(ws_id: str):
    db = SessionLocal()
    try:
        ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
        if ws:
            db.delete(ws)
            db.commit()
    finally:
        db.close()

# ============================================================
# OPERATIONS: PROJECTS
# ============================================================
def get_projects(workspace_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.workspace_id == workspace_id).order_by(Project.created_at.desc()).all()
        return [{"id": p.id, "workspace_id": p.workspace_id, "name": p.name, "created_at": str(p.created_at)} for p in projects]
    finally:
        db.close()

def create_project(workspace_id: str, name: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        proj = Project(workspace_id=workspace_id, name=name)
        db.add(proj)
        db.flush() # to get proj.id

        default_rules = {
            "language": "Arabic",
            "rtl": True,
            "style": "Formal",
            "citation_required": False,
            "numbering": "Legal",
            "heading_style": "Standard"
        }
        
        setting = ProjectSetting(
            project_id=proj.id,
            rules_json=json.dumps(default_rules)
        )
        db.add(setting)
        db.commit()
        return {"id": proj.id, "workspace_id": workspace_id, "name": name, "rules": default_rules}
    finally:
        db.close()

def delete_project(proj_id: str):
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.id == proj_id).first()
        if proj:
            db.delete(proj)
            db.commit()
    finally:
        db.close()

# ============================================================
# OPERATIONS: PROJECT RULES (CONSTITUTION)
# ============================================================
def get_project_rules(project_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        setting = db.query(ProjectSetting).filter(ProjectSetting.project_id == project_id).first()
        if setting and setting.rules_json:
            return json.loads(setting.rules_json)
        return {}
    finally:
        db.close()

def update_project_rules(project_id: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        setting = db.query(ProjectSetting).filter(ProjectSetting.project_id == project_id).first()
        if setting:
            setting.rules_json = json.dumps(rules)
        else:
            setting = ProjectSetting(project_id=project_id, rules_json=json.dumps(rules))
            db.add(setting)
        db.commit()
        return rules
    finally:
        db.close()

# ============================================================
# OPERATIONS: DOCUMENTS & VERSIONS
# ============================================================
def get_documents(project_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.updated_at.desc()).all()
        res = []
        for d in docs:
            doc_dict = {
                "id": d.id, "project_id": d.project_id, "title": d.title,
                "current_version_id": d.current_version_id, "metadata": d.metadata_json,
                "created_at": str(d.created_at), "updated_at": str(d.updated_at)
            }
            if d.current_version_id:
                v = db.query(DocumentVersion).filter(DocumentVersion.id == d.current_version_id).first()
                if v:
                    doc_dict.update({
                        "content": v.content,
                        "document_model": v.document_model,
                        "version_note": v.version_note,
                        "version_created_at": str(v.created_at)
                    })
            res.append(doc_dict)
        return res
    finally:
        db.close()

def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        d = db.query(Document).filter(Document.id == doc_id).first()
        if not d:
            return None
        doc_dict = {
            "id": d.id, "project_id": d.project_id, "title": d.title,
            "current_version_id": d.current_version_id, "metadata": d.metadata_json,
            "created_at": str(d.created_at), "updated_at": str(d.updated_at)
        }
        if d.current_version_id:
            v = db.query(DocumentVersion).filter(DocumentVersion.id == d.current_version_id).first()
            if v:
                doc_dict.update({
                    "content": v.content,
                    "document_model": v.document_model,
                    "version_note": v.version_note,
                    "version_created_at": str(v.created_at)
                })
        return doc_dict
    finally:
        db.close()

def create_document(project_id: str, title: str, content: str = "", document_model: str = "[]") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        doc = Document(project_id=project_id, title=title)
        db.add(doc)
        db.flush()
        
        ver = DocumentVersion(document_id=doc.id, content=content, document_model=document_model, version_note="الإصدار الأول")
        db.add(ver)
        db.flush()
        
        doc.current_version_id = ver.id
        db.commit()
        return get_document(doc.id)
    finally:
        db.close()

def add_document_version(doc_id: str, content: str, document_model: str, version_note: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        ver = DocumentVersion(document_id=doc_id, content=content, document_model=document_model, version_note=version_note)
        db.add(ver)
        db.flush()
        
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.current_version_id = ver.id
            db.commit()
        return get_document(doc_id)
    finally:
        db.close()

def get_document_versions(doc_id: str) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        vers = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).order_by(DocumentVersion.created_at.desc()).all()
        return [{"id": v.id, "document_id": v.document_id, "content": v.content, "document_model": v.document_model, "version_note": v.version_note, "created_at": str(v.created_at)} for v in vers]
    finally:
        db.close()

def restore_document_version(doc_id: str, version_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        ver = db.query(DocumentVersion).filter(DocumentVersion.id == version_id, DocumentVersion.document_id == doc_id).first()
        if not ver:
            return None
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.current_version_id = ver.id
            db.commit()
        return get_document(doc_id)
    finally:
        db.close()

def update_document_title(doc_id: str, title: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.title = title
            db.commit()
    finally:
        db.close()

def delete_document(doc_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            db.delete(doc)
            db.commit()
    finally:
        db.close()

# ============================================================
# OPERATIONS: KNOWLEDGE ITEMS
# ============================================================
def get_knowledge_items(project_id: str, item_type: Optional[str] = None) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        q = db.query(KnowledgeItem).filter(KnowledgeItem.project_id == project_id)
        if item_type:
            q = q.filter(KnowledgeItem.type == item_type)
        items = q.order_by(KnowledgeItem.created_at.desc()).all()
        return [{"id": i.id, "project_id": i.project_id, "title": i.title, "type": i.type, "content": i.content, "tags": i.tags, "references_text": i.references_text, "created_at": str(i.created_at)} for i in items]
    finally:
        db.close()

def create_knowledge_item(project_id: str, title: str, item_type: str, content: str, tags: str = "", references_text: str = "") -> Dict[str, Any]:
    db = SessionLocal()
    try:
        item = KnowledgeItem(project_id=project_id, title=title, type=item_type, content=content, tags=tags, references_text=references_text)
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"id": item.id, "project_id": item.project_id, "title": item.title, "type": item.type, "content": item.content, "tags": item.tags, "references_text": item.references_text}
    finally:
        db.close()

def delete_knowledge_item(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(KnowledgeItem).filter(KnowledgeItem.id == item_id).first()
        if item:
            db.delete(item)
            db.commit()
    finally:
        db.close()

# ============================================================
# OPERATIONS: PROJECT MEMORY
# ============================================================
def get_project_memory(project_id: str, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        q = db.query(ProjectMemory).filter(ProjectMemory.project_id == project_id)
        if memory_type:
            q = q.filter(ProjectMemory.type == memory_type)
        items = q.order_by(ProjectMemory.created_at.desc()).all()
        return [{"id": i.id, "project_id": i.project_id, "type": i.type, "content": i.content, "created_at": str(i.created_at)} for i in items]
    finally:
        db.close()

def create_memory_item(project_id: str, memory_type: str, content: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        item = ProjectMemory(project_id=project_id, type=memory_type, content=content)
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"id": item.id, "project_id": item.project_id, "type": item.type, "content": item.content}
    finally:
        db.close()

def delete_memory_item(item_id: str):
    db = SessionLocal()
    try:
        item = db.query(ProjectMemory).filter(ProjectMemory.id == item_id).first()
        if item:
            db.delete(item)
            db.commit()
    finally:
        db.close()
