from fastapi import APIRouter, HTTPException
from typing import Dict, List
import json
import io
import zipfile

from schemas import DocumentCreate, VersionCreate, ProcessRequest, FormattingSettings
import dcos_db
import dcos_cognitive
import dcos_export

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("")
def read_documents(project_id: str):
    return dcos_db.get_documents(project_id)

@router.get("/{doc_id}")
def read_document(doc_id: str):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    return doc

@router.post("")
def add_document(data: DocumentCreate):
    return dcos_db.create_document(data.project_id, data.title, data.content, data.document_model)

@router.post("/{doc_id}/versions")
def add_version(doc_id: str, data: VersionCreate):
    return dcos_db.add_document_version(doc_id, data.content, data.document_model, data.version_note)

@router.get("/{doc_id}/versions")
def read_document_versions(doc_id: str):
    return dcos_db.get_document_versions(doc_id)

@router.post("/{doc_id}/versions/{version_id}/restore")
def restore_version(doc_id: str, version_id: str):
    doc = dcos_db.restore_document_version(doc_id, version_id)
    if not doc:
        raise HTTPException(status_code=400, detail="فشلت عملية استعادة النسخة")
    return doc

@router.put("/{doc_id}/title")
def update_title(doc_id: str, payload: Dict[str, str]):
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="العنوان مطلوب")
    dcos_db.update_document_title(doc_id, title)
    return {"success": True}

@router.delete("/{doc_id}")
def remove_document(doc_id: str):
    dcos_db.delete_document(doc_id)
    return {"success": True}

@router.post("/{doc_id}/process")
def process_document(doc_id: str, request: ProcessRequest):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
        
    rules = dcos_db.get_project_rules(doc["project_id"])
    doc_model, stats = dcos_cognitive.build_document_model(request.content, rules)
    doc_model_str = json.dumps(doc_model, ensure_ascii=False)
    
    dcos_db.add_document_version(doc_id, request.content, doc_model_str, "معالجة وتحليل إدراكي تلقائي")
    
    return {
        "success": True,
        "stats": stats,
        "document_model": doc_model
    }

@router.post("/{doc_id}/export/docx")
def export_docx(doc_id: str, formatting: FormattingSettings):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
        
    model_str = doc.get("document_model", "[]")
    try:
        doc_model = json.loads(model_str)
    except:
        doc_model = []
        
    docx_bytes = dcos_export.export_to_docx(doc_model, formatting.dict())
    docx_hex = docx_bytes.hex()
    
    return {
        "success": True,
        "filename": f"{doc['title']}.docx",
        "document_base64": docx_hex
    }

@router.post("/{doc_id}/export/markdown")
def export_markdown(doc_id: str):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
        
    model_str = doc.get("document_model", "[]")
    try:
        doc_model = json.loads(model_str)
    except:
        doc_model = []
        
    md_content = dcos_export.export_to_markdown(doc_model)
    return {"success": True, "content": md_content}

@router.post("/{doc_id}/export/html")
def export_html(doc_id: str, formatting: FormattingSettings):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
        
    model_str = doc.get("document_model", "[]")
    try:
        doc_model = json.loads(model_str)
    except:
        doc_model = []
        
    html_content = dcos_export.export_to_html(doc_model, formatting.dict())
    return {"success": True, "content": html_content}
