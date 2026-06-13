from fastapi import APIRouter, HTTPException
from schemas import WorkspaceCreate
import dcos_db

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.get("")
def read_workspaces():
    """الحصول على جميع Workspaces"""
    return dcos_db.get_workspaces()

@router.post("")
def add_workspace(data: WorkspaceCreate):
    """إنشاء Workspace جديد"""
    return dcos_db.create_workspace(data.name)

@router.delete("/{ws_id}")
def remove_workspace(ws_id: str):
    """حذف Workspace"""
    dcos_db.delete_workspace(ws_id)
    return {"success": True}
