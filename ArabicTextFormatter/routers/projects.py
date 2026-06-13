from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from schemas import ProjectCreate, KnowledgeCreate, MemoryCreate
import dcos_db

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("")
def read_projects(workspace_id: str):
    """الحصول على جميع Projects في Workspace معين"""
    return dcos_db.get_projects(workspace_id)

@router.post("")
def add_project(data: ProjectCreate):
    """إنشاء Project جديد مع القواعد الافتراضية"""
    return dcos_db.create_project(data.workspace_id, data.name)

@router.delete("/{proj_id}")
def remove_project(proj_id: str):
    """حذف Project"""
    dcos_db.delete_project(proj_id)
    return {"success": True}

@router.get("/{proj_id}/rules")
def read_project_rules(proj_id: str):
    """الحصول على قواعد المشروع (Constitution)"""
    return dcos_db.get_project_rules(proj_id)

@router.post("/{proj_id}/rules")
def save_project_rules(proj_id: str, rules: Dict[str, Any]):
    """حفظ قواعد المشروع"""
    return dcos_db.update_project_rules(proj_id, rules)

@router.get("/{proj_id}/knowledge")
def read_knowledge(proj_id: str, type: Optional[str] = None):
    """الحصول على عناصر المعرفة في المشروع"""
    return dcos_db.get_knowledge_items(proj_id, type)

@router.post("/{proj_id}/knowledge")
def add_knowledge(proj_id: str, data: KnowledgeCreate):
    """إضافة عنصر معرفة جديد"""
    return dcos_db.create_knowledge_item(proj_id, data.title, data.type, data.content, data.tags, data.references_text)

@router.get("/{proj_id}/memory")
def read_memory(proj_id: str, type: Optional[str] = None):
    """الحصول على عناصر الذاكرة في المشروع"""
    return dcos_db.get_project_memory(proj_id, type)

@router.post("/{proj_id}/memory")
def add_memory(proj_id: str, data: MemoryCreate):
    """إضافة عنصر ذاكرة جديد"""
    return dcos_db.create_memory_item(proj_id, data.type, data.content)
