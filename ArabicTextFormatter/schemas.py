from pydantic import BaseModel
from typing import Optional, List, Dict, Any

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
    type: str
    content: str
    tags: str = ""
    references_text: str = ""

class MemoryCreate(BaseModel):
    project_id: str
    type: str
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

class AIBaseRequest(BaseModel):
    api_key: Optional[str] = ""
    provider: Optional[str] = "local"

class AIGenerateRequest(AIBaseRequest):
    prompt: str
    system_instruction: Optional[str] = None

class AIRewriteRequest(AIBaseRequest):
    text: str
    instruction: str

class AIReviewRequest(AIBaseRequest):
    text: str
    project_id: str

class AIAnalyzeRequest(AIBaseRequest):
    text: str
    aspect: str

class AIDiacritizeRequest(BaseModel):
    text: str
    action: Optional[str] = "all"

class AIChatRequest(BaseModel):
    api_key: Optional[str] = ""
    provider: Optional[str] = "local"
    message: str
    context: str
    project_id: str
