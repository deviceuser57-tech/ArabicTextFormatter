# main.py - الخادم الكامل
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import re
import io
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class HeadingStyle(BaseModel):
    size: int
    color: str
    alignment: str
    weight: str  # bold, semi-bold, regular
    underline: bool

class FormatRequest(BaseModel):
    text: str
    font_family: str = "Arial"
    font_size: int = 14
    font_color: str = "#000000"
    text_direction: str = "rtl"
    alignment: str = "right"
    line_spacing: float = 1.5
    space_before: float = 0
    space_after: float = 6
    
    heading1: HeadingStyle
    heading2: HeadingStyle
    heading3: HeadingStyle
    heading4: HeadingStyle
    heading5: HeadingStyle
    heading6: HeadingStyle
    
    bullet_symbol: str = "•"
    number_style: str = "1."
    
    header_text: str = ""
    footer_text: str = ""
    page_numbers: bool = True
    start_from_second_page: bool = True

def clean_text(text: str) -> str:
    """تنظيف النص من علامات الاتجاه وإصلاح الأقواس"""
    direction_marks = '\u200E\u200F\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069'
    for mark in direction_marks:
        text = text.replace(mark, '')
    
    text = text.replace(' )', ')')
    text = text.replace('( ', '(')
    text = text.replace(' ]', ']')
    text = text.replace('[ ', '[')
    return text

def detect_line_type(line: str) -> dict:
    """تحليل ذكي للسطر لتحديد ما إذا كان عنواناً (وأي مستوى) أو قائمة أو فقرة عادية"""
    line = line.strip()
    if not line:
        return {"type": "empty"}
    
    # إذا كان السطر طويلاً جداً (أكثر من 150 حرف)، فهو بالتأكيد فقرة وليس عنواناً
    if len(line) > 150:
        return {"type": "paragraph", "text": line}
    
    # 1. كشف القوائم المنقطة والمرقمة
    if re.match(r'^[\-\•\*\◦\▪]\s+', line):
        return {"type": "bullet_list", "text": re.sub(r'^[\-\•\*\◦\▪]\s+', '', line)}
    
    # 2. كشف العناوين (6 مستويات)
    # Level 1: الباب، الفصل
    if re.match(r'^(الباب\s+|الفصل\s+|Part\s+|Chapter\s+)', line, re.IGNORECASE):
        return {"type": "heading", "level": 1, "text": line}
        
    # Level 2: المبحث، القسم
    if re.match(r'^(المبحث\s+|القسم\s+|Section\s+)', line, re.IGNORECASE):
        return {"type": "heading", "level": 2, "text": line}
        
    # Level 3: المطلب، المادة
    if re.match(r'^(المطلب\s+|المادة\s+|Article\s+)', line, re.IGNORECASE):
        return {"type": "heading", "level": 3, "text": line}
        
    # Level 4: الفرع، البند، أولاً، ثانياً...
    if re.match(r'^(الفرع\s+|البند\s+|أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)', line):
        return {"type": "heading", "level": 4, "text": line}
        
    # Level 5: الفقرة، ترقيم 1. 2. 3. (أرقام رئيسية كنصوص قصيرة)
    if re.match(r'^(الفقرة\s+|^\d+[\.\-]\s+)', line):
        # إذا كان ترقيماً رقمياً وهو قصير، نعتبره عنوان مستوى 5
        if len(line) < 80:
            return {"type": "heading", "level": 5, "text": line}
        else:
            return {"type": "number_list", "text": re.sub(r'^\d+[\.\-]\s+', '', line)}
            
    # Level 6: الترقيم الفرعي 1.1، أ- ب- ج-
    if re.match(r'^(\d+\.\d+[\.\-]\s+|[أبجدهوزحطيكل]\s*[\-\.]\s+)', line):
        if len(line) < 80:
            return {"type": "heading", "level": 6, "text": line}
        else:
            return {"type": "number_list", "text": re.sub(r'^(\d+\.\d+[\.\-]\s+|[أبجدهوزحطيكل]\s*[\-\.]\s+)', '', line)}
    
    # افتراضي: فقرة عادية
    return {"type": "paragraph", "text": line}

def add_page_number(run):
    """إضافة حقل رقم الصفحة في docx"""
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = "PAGE"
    
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    
    t = OxmlElement('w:t')
    t.text = "1"
    
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(t)
    run._r.append(fldChar3)

@app.post("/process")
async def process_text(request: FormatRequest):
    """معالجة النص وتنسيقه وإرجاع معاينة JSON وملف Word"""
    
    cleaned = clean_text(request.text)
    lines = cleaned.split('\n')
    
    doc = Document()
    
    # إعدادات Document
    section = doc.sections[0]
    if request.start_from_second_page:
        section.different_first_page_header_footer = True
    
    # الترويسة والتذييل
    if request.header_text:
        header = section.header
        hp = header.paragraphs[0]
        hp.text = request.header_text
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
    if request.footer_text or request.page_numbers:
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if request.footer_text:
            fp.text = request.footer_text + " - "
        if request.page_numbers:
            run = fp.add_run()
            add_page_number(run)

    # إعدادات الخط الأساسي
    style = doc.styles['Normal']
    font = style.font
    font.name = request.font_family
    font.size = Pt(request.font_size)
    
    # دالة مساعدة لتطبيق المحاذاة
    def get_align(alignment_str):
        return {
            'right': WD_ALIGN_PARAGRAPH.RIGHT,
            'left': WD_ALIGN_PARAGRAPH.LEFT,
            'center': WD_ALIGN_PARAGRAPH.CENTER,
            'justify': WD_ALIGN_PARAGRAPH.JUSTIFY
        }.get(alignment_str, WD_ALIGN_PARAGRAPH.RIGHT)
        
    # قواميس التنسيقات للعناوين
    heading_styles = {
        1: request.heading1, 2: request.heading2, 3: request.heading3,
        4: request.heading4, 5: request.heading5, 6: request.heading6
    }
    
    preview_data = []
    heading_count = 0
    
    number_list_counter = 1
    
    for line in lines:
        analysis = detect_line_type(line)
        l_type = analysis["type"]
        
        if l_type == "empty":
            doc.add_paragraph("")
            preview_data.append({"type": "empty", "html": "<br>"})
            number_list_counter = 1 # تصفير العداد عند سطر فارغ
            continue
            
        text_val = analysis["text"]
        
        if l_type == "heading":
            level = analysis["level"]
            h_style = heading_styles[level]
            heading_count += 1
            
            p = doc.add_paragraph()
            p.alignment = get_align(h_style.alignment)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            
            run = p.add_run(text_val)
            run.font.name = request.font_family
            run.font.size = Pt(h_style.size)
            run.font.color.rgb = RGBColor.from_string(h_style.color.lstrip('#'))
            run.font.underline = h_style.underline
            
            if h_style.weight == 'bold':
                run.font.bold = True
            elif h_style.weight == 'semi-bold':
                # Word doesn't strictly have semi-bold via standard API, fallback to bold
                run.font.bold = True
            else:
                run.font.bold = False
                
            # للمعاينة في HTML
            fontWeight = "bold" if h_style.weight != "regular" else "normal"
            textDecoration = "underline" if h_style.underline else "none"
            html = f'<h{level} style="font-size:{h_style.size}px; color:{h_style.color}; text-align:{h_style.alignment}; font-weight:{fontWeight}; text-decoration:{textDecoration}; margin:10px 0;">{text_val}</h{level}>'
            preview_data.append({"type": "heading", "level": level, "html": html})
            number_list_counter = 1
            
        elif l_type == "bullet_list":
            p = doc.add_paragraph(style='List Bullet')
            p.alignment = get_align(request.alignment)
            p.paragraph_format.line_spacing = request.line_spacing
            
            # محاولة تغيير رمز القائمة (يتطلب تعديل خصائص النمط أو الرن)
            # للتبسيط، نضع الرمز يدوياً كنص مع فقرة بمسافة بادئة
            p.style = 'Normal'
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            
            run = p.add_run(f"{request.bullet_symbol} {text_val}")
            run.font.name = request.font_family
            run.font.size = Pt(request.font_size)
            run.font.color.rgb = RGBColor.from_string(request.font_color.lstrip('#'))
            
            html = f'<div style="text-align:{request.alignment}; margin-right: 20px;">{request.bullet_symbol} {text_val}</div>'
            preview_data.append({"type": "bullet", "html": html})
            number_list_counter = 1
            
        elif l_type == "number_list":
            p = doc.add_paragraph()
            p.alignment = get_align(request.alignment)
            p.paragraph_format.line_spacing = request.line_spacing
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.first_line_indent = Inches(-0.25)
            
            prefix = f"{number_list_counter}." if "1." in request.number_style else f"({number_list_counter})"
            run = p.add_run(f"{prefix} {text_val}")
            run.font.name = request.font_family
            run.font.size = Pt(request.font_size)
            run.font.color.rgb = RGBColor.from_string(request.font_color.lstrip('#'))
            
            html = f'<div style="text-align:{request.alignment}; margin-right: 20px;">{prefix} {text_val}</div>'
            preview_data.append({"type": "number", "html": html})
            number_list_counter += 1
            
        else:
            # Paragraph
            p = doc.add_paragraph()
            p.alignment = get_align(request.alignment)
            p.paragraph_format.space_before = Pt(request.space_before)
            p.paragraph_format.space_after = Pt(request.space_after)
            p.paragraph_format.line_spacing = request.line_spacing
            
            run = p.add_run(text_val)
            run.font.name = request.font_family
            run.font.size = Pt(request.font_size)
            run.font.color.rgb = RGBColor.from_string(request.font_color.lstrip('#'))
            
            html = f'<p style="text-align:{request.alignment}; margin-top:{request.space_before}px; margin-bottom:{request.space_after}px;">{text_val}</p>'
            preview_data.append({"type": "paragraph", "html": html})
            number_list_counter = 1
            
    # حفظ المستند
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    
    return {
        "success": True,
        "headings_detected": heading_count,
        "preview_html": "".join([item["html"] for item in preview_data]),
        "document_base64": output.getvalue().hex()
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """معالجة ملف مرفوع"""
    content = await file.read()
    if file.filename.endswith('.txt') or file.filename.endswith('.md'):
        text = content.decode('utf-8')
    elif file.filename.endswith('.docx'):
        doc = Document(io.BytesIO(content))
        text = '\n'.join([p.text for p in doc.paragraphs])
    else:
        return {"error": "نوع الملف غير مدعوم"}
    return {"success": True, "text": text, "filename": file.filename}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
