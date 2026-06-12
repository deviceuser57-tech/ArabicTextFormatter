from fastapi import FastAPI, HTTPException, status, File, UploadFile, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import os
import io
import traceback

from routers import workspaces, projects, documents, ai
import dcos_db

app = FastAPI(title="Documents Cognitive Operating System (DCOS) API", version="1.0")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the full traceback for debugging
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "حدث خطأ غير متوقع في الخادم", "error": str(exc)},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(ai.router)

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error loading index.html: {str(e)}</h3>", status_code=500)

@app.delete("/knowledge/{item_id}")
def remove_knowledge_item(item_id: str):
    dcos_db.delete_knowledge_item(item_id)
    return {"success": True}

@app.delete("/memory/{item_id}")
def remove_memory_item(item_id: str):
    dcos_db.delete_memory_item(item_id)
    return {"success": True}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    provider: str = Form(None),
    api_key: str = Form(None)
):
    content = await file.read()
    if file.filename.endswith('.txt') or file.filename.endswith('.md'):
        text = content.decode('utf-8')
    elif file.filename.endswith('.docx'):
        from docx import Document
        doc = Document(io.BytesIO(content))
        text = '\n'.join([p.text for p in doc.paragraphs])
    elif file.filename.endswith('.pdf'):
        if provider == "gemini" and api_key:
            try:
                import base64
                pdf_base64 = base64.b64encode(content).decode('utf-8')
                import urllib.request
                import json
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "application/pdf",
                                    "data": pdf_base64
                                }
                            },
                            {
                                "text": "Extract all text and tabular information from this document. Format tables cleanly and return the text in Arabic."
                            }
                        ]
                    }]
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req) as response:
                    res = json.loads(response.read().decode("utf-8"))
                    text = res["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                # Fallback to local OCR/text extraction
                try:
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(content))
                    text = '\n'.join([page.extract_text() for page in reader.pages])
                except Exception as ex:
                    raise HTTPException(status_code=400, detail=f"فشل استخراج النص: {str(e)} / {str(ex)}")
        else:
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
