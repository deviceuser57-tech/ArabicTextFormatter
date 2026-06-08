# main.py - بوابة FastAPI لـ DCOS v1.0
from fastapi import FastAPI, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import base64
import zipfile
import io

import dcos_db
import dcos_cognitive
import dcos_export
import dcos_ai

from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="Documents Cognitive Operating System (DCOS) API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error loading index.html: {str(e)}</h3>", status_code=500)

# ============================================================
# PYDANTIC SCHEMAS
# ============================================================
class WorkspaceCreate(BaseModel):
    name: str

class ProjectCreate(BaseModel):
    workspace_id: str
    name: str

class DocumentCreate(BaseModel):
    project_id: str
    title: str
    content: str = ""
    document_model: str = "[]"

class VersionCreate(BaseModel):
    content: str
    document_model: str
    version_note: str = ""

class KnowledgeCreate(BaseModel):
    project_id: str
    title: str
    type: str # Concept, Definition, Rule, StyleGuide, Reference, Citation, Note
    content: str
    tags: str = ""
    references_text: str = ""

class MemoryCreate(BaseModel):
    project_id: str
    type: str # Decision, Preference, WritingPattern, OpenQuestion
    content: str

class HeadingStyle(BaseModel):
    size: int
    color: str
    alignment: str
    weight: str
    underline: bool

class FormattingSettings(BaseModel):
    font_family: str = "Traditional Arabic"
    font_size: int = 14
    font_color: str = "#1a1a1a"
    alignment: str = "right"
    line_spacing: float = 1.5
    space_before: float = 0
    space_after: float = 10
    bullet_symbol: str = "•"
    number_style: str = "1."
    header_text: str = ""
    footer_text: str = ""
    page_numbers: bool = True
    start_from_second_page: bool = True
    
    heading1: Optional[HeadingStyle] = None
    heading2: Optional[HeadingStyle] = None
    heading3: Optional[HeadingStyle] = None
    heading4: Optional[HeadingStyle] = None
    heading5: Optional[HeadingStyle] = None
    heading6: Optional[HeadingStyle] = None

class ProcessRequest(BaseModel):
    content: str

# AI Request Models
class AIBaseRequest(BaseModel):
    api_key: Optional[str] = ""
    provider: Optional[str] = "local" # gemini, openai, local

class AIGenerateRequest(AIBaseRequest):
    prompt: str
    system_instruction: Optional[str] = None

class AIRewriteRequest(AIBaseRequest):
    text: str
    instruction: str # e.g. "اجعل الصياغة قانونية ورسمية أكثر"

class AIReviewRequest(AIBaseRequest):
    text: str
    project_id: str

class AIAnalyzeRequest(AIBaseRequest):
    text: str
    aspect: str # e.g. "concepts", "entities"

# Helper function to get AI Provider
def get_ai_provider(provider_name: str, api_key: str) -> dcos_ai.AIProvider:
    if not api_key or provider_name == "local":
        return dcos_ai.LocalProvider()
    if provider_name == "gemini":
        return dcos_ai.GeminiProvider(api_key=api_key)
    if provider_name == "openai":
        return dcos_ai.OpenAIProvider(api_key=api_key)
    return dcos_ai.LocalProvider()

# ============================================================
# API ENDPOINTS: WORKSPACES & PROJECTS
# ============================================================
@app.get("/workspaces")
def read_workspaces():
    return dcos_db.get_workspaces()

@app.post("/workspaces")
def add_workspace(data: WorkspaceCreate):
    return dcos_db.create_workspace(data.name)

@app.delete("/workspaces/{ws_id}")
def remove_workspace(ws_id: str):
    dcos_db.delete_workspace(ws_id)
    return {"success": True}

@app.get("/projects")
def read_projects(workspace_id: str):
    return dcos_db.get_projects(workspace_id)

@app.post("/projects")
def add_project(data: ProjectCreate):
    return dcos_db.create_project(data.workspace_id, data.name)

@app.delete("/projects/{proj_id}")
def remove_project(proj_id: str):
    dcos_db.delete_project(proj_id)
    return {"success": True}

@app.get("/projects/{proj_id}/rules")
def read_project_rules(proj_id: str):
    return dcos_db.get_project_rules(proj_id)

@app.post("/projects/{proj_id}/rules")
def save_project_rules(proj_id: str, rules: Dict[str, Any]):
    return dcos_db.update_project_rules(proj_id, rules)

# ============================================================
# API ENDPOINTS: DOCUMENTS & VERSIONS
# ============================================================
@app.get("/documents")
def read_documents(project_id: str):
    return dcos_db.get_documents(project_id)

@app.get("/documents/{doc_id}")
def read_document(doc_id: str):
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    return doc

@app.post("/documents")
def add_document(data: DocumentCreate):
    return dcos_db.create_document(data.project_id, data.title, data.content, data.document_model)

@app.post("/documents/{doc_id}/versions")
def add_version(doc_id: str, data: VersionCreate):
    return dcos_db.add_document_version(doc_id, data.content, data.document_model, data.version_note)

@app.get("/documents/{doc_id}/versions")
def read_document_versions(doc_id: str):
    return dcos_db.get_document_versions(doc_id)

@app.post("/documents/{doc_id}/versions/{version_id}/restore")
def restore_version(doc_id: str, version_id: str):
    doc = dcos_db.restore_document_version(doc_id, version_id)
    if not doc:
        raise HTTPException(status_code=400, detail="فشلت عملية استعادة النسخة")
    return doc

@app.put("/documents/{doc_id}/title")
def update_title(doc_id: str, payload: Dict[str, str]):
    title = payload.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="العنوان مطلوب")
    dcos_db.update_document_title(doc_id, title)
    return {"success": True}

@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    dcos_db.delete_document(doc_id)
    return {"success": True}

# ============================================================
# API ENDPOINTS: KNOWLEDGE ITEMS & MEMORY
# ============================================================
@app.get("/projects/{proj_id}/knowledge")
def read_knowledge(proj_id: str, type: Optional[str] = None):
    return dcos_db.get_knowledge_items(proj_id, type)

@app.post("/projects/{proj_id}/knowledge")
def add_knowledge(proj_id: str, data: KnowledgeCreate):
    return dcos_db.create_knowledge_item(proj_id, data.title, data.type, data.content, data.tags, data.references_text)

@app.delete("/knowledge/{item_id}")
def remove_knowledge_item(item_id: str):
    dcos_db.delete_knowledge_item(item_id)
    return {"success": True}

@app.get("/projects/{proj_id}/memory")
def read_memory(proj_id: str, type: Optional[str] = None):
    return dcos_db.get_project_memory(proj_id, type)

@app.post("/projects/{proj_id}/memory")
def add_memory(proj_id: str, data: MemoryCreate):
    return dcos_db.create_memory_item(proj_id, data.type, data.content)

@app.delete("/memory/{item_id}")
def remove_memory_item(item_id: str):
    dcos_db.delete_memory_item(item_id)
    return {"success": True}

# ============================================================
# API ENDPOINTS: COGNITIVE PROCESSING PIPELINE
# ============================================================
@app.post("/documents/{doc_id}/process")
def process_document(doc_id: str, request: ProcessRequest):
    """تشغيل محرك القواعد لتنظيف وهيكلة المستند وتحديث الإصدار تلقائياً"""
    doc = dcos_db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
        
    # جلب تفضيلات دستور المشروع
    rules = dcos_db.get_project_rules(doc["project_id"])
    
    # بناء نموذج المستند الموحد
    doc_model, stats = dcos_cognitive.build_document_model(request.content, rules)
    doc_model_str = json.dumps(doc_model, ensure_ascii=False)
    
    # إضافة إصدار جديد تلقائياً بالنتائج المنظفة والهيكل
    dcos_db.add_document_version(doc_id, request.content, doc_model_str, "معالجة وتحليل إدراكي تلقائي")
    
    return {
        "success": True,
        "stats": stats,
        "document_model": doc_model
    }

# ============================================================
# API ENDPOINTS: EXPORTS
# ============================================================
@app.post("/documents/{doc_id}/export/docx")
def export_docx(doc_id: str, formatting: FormattingSettings):
    """تصدير المستند كـ DOCX مع التنسيقات المحددة يدوياً أو الافتراضية"""
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

@app.post("/documents/{doc_id}/export/markdown")
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

@app.post("/documents/{doc_id}/export/html")
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

@app.post("/projects/{proj_id}/batch-export")
def batch_export_docx(proj_id: str, document_ids: List[str], formatting: FormattingSettings):
    """تصدير جماعي للمستندات كـ ZIP"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for doc_id in document_ids:
            doc = dcos_db.get_document(doc_id)
            if doc:
                model_str = doc.get("document_model", "[]")
                try:
                    doc_model = json.loads(model_str)
                except:
                    doc_model = []
                docx_bytes = dcos_export.export_to_docx(doc_model, formatting.dict())
                zip_file.writestr(f"{doc['title']}.docx", docx_bytes)
                
    zip_buffer.seek(0)
    zip_hex = zip_buffer.getvalue().hex()
    return {
        "success": True,
        "filename": "dcos_export.zip",
        "zip_base64": zip_hex
    }

# ============================================================
# API ENDPOINTS: INTELLIGENCE LAYER (AI / HYBRID)
# ============================================================
@app.post("/ai/generate")
def ai_generate(req: AIGenerateRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    try:
        resp_text = provider.generate(req.prompt, req.system_instruction)
        return {"success": True, "text": resp_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/rewrite")
def ai_rewrite(req: AIRewriteRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    prompt = f"Rewrite the following text based on this instruction: '{req.instruction}'. Keep the tone proper and output only the rewritten text.\nText:\n{req.text}"
    try:
        resp_text = provider.generate(prompt, "You are a senior document rewriting editor.")
        return {"success": True, "text": resp_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/review")
def ai_review(req: AIReviewRequest):
    """مراجعة جودة النص - هجينة (تستخدم القواعد محلياً دائماً وتدمج الذكاء الاصطناعي إن توفرت المفاتيح)"""
    # 1. المراجعة المبنية على القواعد (محلياً دائماً)
    local_provider = dcos_ai.LocalProvider()
    rules = dcos_db.get_project_rules(req.project_id)
    local_review = local_provider.review(req.text, rules)
    
    # 2. مراجعة الذكاء الاصطناعي (اختيارية إن توفرت المفاتيح)
    if req.api_key and req.provider != "local":
        ai_provider = get_ai_provider(req.provider, req.api_key)
        try:
            ai_review = ai_provider.review(req.text, rules)
            # دمج نتائج المراجعتين
            local_review["score"] = int((local_review["score"] + ai_review.get("score", 70)) / 2)
            local_review["issues"].extend(ai_review.get("issues", []))
            local_review["offline"] = False
        except Exception as e:
            local_review["issues"].append({
                "type": "system",
                "text": f"فشلت مراجعة الذكاء الاصطناعي المتقدمة: {str(e)}",
                "severity": "low"
            })
            
    return local_review

@app.post("/ai/analyze")
def ai_analyze(req: AIAnalyzeRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    try:
        resp_data = provider.analyze(req.text, req.aspect)
        return {"success": True, "analysis": resp_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# COMPATIBILITY: UPLOAD FILE
# ============================================================
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """قراءة محتوى ملف مرفوع لتحويله إلى نص في المحرر"""
    content = await file.read()
    if file.filename.endswith('.txt') or file.filename.endswith('.md'):
        text = content.decode('utf-8')
    elif file.filename.endswith('.docx'):
        from docx import Document
        doc = Document(io.BytesIO(content))
        text = '\n'.join([p.text for p in doc.paragraphs])
    elif file.filename.endswith('.pdf'):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = '\n'.join([page.extract_text() for page in reader.pages])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"فشل استخراج النص من ملف PDF: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")
    return {"success": True, "text": text, "filename": file.filename}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
