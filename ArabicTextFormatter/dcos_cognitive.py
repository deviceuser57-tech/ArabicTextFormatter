# dcos_cognitive.py - محرك المعالجة الإدراكية المبني على القواعد
import re
import json
from typing import List, Dict, Any, Tuple

# علامات Unicode المخفية الخاصة باتجاه النص
DIR_MARKS_REGEX = re.compile(r'[\u200E\u200F\u202A\u202B\u202C\u202D\u202E\u2066\u2067\u2068\u2069\uFEFF]')

def clean_unicode_and_bidi(raw_text: str) -> Tuple[str, int]:
    """تنظيف النص من علامات اتجاه Unicode الملعونة وإصلاح الأقواس والفراغات الزائدة"""
    if not raw_text:
        return "", 0
    
    orig_len = len(raw_text)
    # 1. حذف علامات الاتجاه
    cleaned = DIR_MARKS_REGEX.sub('', raw_text)
    removed_count = orig_len - len(cleaned)
    
    # 2. إصلاح المسافات للأقواس
    cleaned = cleaned.replace(' )', ')').replace('( ', '(')
    cleaned = cleaned.replace(' ]', ']').replace('[ ', '[')
    cleaned = cleaned.replace(' }', '}').replace('{ ', '{')
    
    # 3. توحيد الفراغات المتعددة في السطور (دون دمج السطور)
    lines = []
    for line in cleaned.splitlines():
        # استبدال المسافات المتعددة بمسافة واحدة
        normalized_line = re.sub(r'[ \t]+', ' ', line).strip()
        lines.append(normalized_line)
        
    return '\n'.join(lines), removed_count

def detect_line_structure(line: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    """تحليل سطر مفرد وتحديد نوعه الإنشائي"""
    line = line.strip()
    if not line:
        return {"type": "empty_line"}
        
    # إذا كان السطر طويلاً جداً، فهو بالتأكيد فقرة عادية وليس عنواناً أو قائمة
    if len(line) > 220:
        return {"type": "paragraph", "text": line}
        
    # 1. كشف القوائم النقطية
    if re.match(r'^[\-\–\•\*\◦\▪]\s+\S', line):
        clean_text = re.sub(r'^[\-\–\•\*\◦\▪]\s+', '', line)
        return {"type": "bullet_list_item", "text": clean_text, "level": 1}
        
    # 2. كشف القوائم الرقمية (الهرمية أو البسيطة)
    # مثال: 1. أو 1- أو (1) أو أ-
    num_match = re.match(r'^(\d+[\.\-\)]\s*|[أبجدهوزحطيكل]\s*[\-\.]\s+)\s*(\S.*)', line)
    if num_match:
        prefix = num_match.group(1).strip()
        clean_text = num_match.group(2).strip()
        # إذا كان السطر قصيراً، قد يكون عنواناً فرعياً أو بنداً مرقماً
        if len(line) < 100:
            return {"type": "heading", "level": 5, "text": line}
        else:
            return {"type": "numbered_list_item", "text": clean_text, "level": 1, "raw_prefix": prefix}

    # 3. كشف القوائم الرقمية الفرعية (مثل 1.1)
    subnum_match = re.match(r'^(\d+\.\d+[\.\-\)]?\s*)\s*(\S.*)', line)
    if subnum_match:
        prefix = subnum_match.group(1).strip()
        clean_text = subnum_match.group(2).strip()
        if len(line) < 100:
            return {"type": "heading", "level": 6, "text": line}
        else:
            return {"type": "numbered_list_item", "text": clean_text, "level": 2, "raw_prefix": prefix}

    # 4. كشف الاقتباسات (المستندة إلى علامة > أو الاقتباس الطويل الهامشي)
    if line.startswith(">"):
        return {"type": "quote", "text": line[1:].strip()}

    # 5. مستويات العناوين الدلالية
    # Level 1: الباب، الفصل
    if re.match(r'^(الباب\s+|الفصل\s+|Part\s+|Chapter\s+)', line, re.IGNORECASE) and len(line) < 130:
        return {"type": "heading", "level": 1, "text": line}
        
    # Level 2: المبحث، القسم
    if re.match(r'^(المبحث\s+|القسم\s+|Section\s+)', line, re.IGNORECASE) and len(line) < 130:
        return {"type": "heading", "level": 2, "text": line}
        
    # Level 3: المطلب، المادة
    if re.match(r'^(المطلب\s+|المادة\s+|Article\s+)', line, re.IGNORECASE) and len(line) < 130:
        return {"type": "heading", "level": 3, "text": line}
        
    # Level 4: الفرع، البند، أو الترقيم النصي (أولاً، ثانياً...)
    if re.match(r'^(الفرع\s+|البند\s+|أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)', line) and len(line) < 130:
        return {"type": "heading", "level": 4, "text": line}

    # افتراضي: فقرة عادية
    return {"type": "paragraph", "text": line}

def build_document_model(raw_content: str, rules: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """بناء نموذج المستند الموحد وإصلاح الترقيم تلقائياً (Numbering Engine)"""
    cleaned_text, removed_chars = clean_unicode_and_bidi(raw_content)
    lines = cleaned_text.split('\n')
    
    document_model = []
    stats = {
        "original_chars": len(raw_content),
        "removed_chars": removed_chars,
        "headings_count": 0,
        "paragraphs_count": 0,
        "lists_count": 0
    }
    
    numbered_item_counter = 0
    bullet_item_counter = 0
    
    for line in lines:
        analysis = detect_line_structure(line, rules)
        el_type = analysis["type"]
        
        # تصفير العدادات عند السطور الفارغة أو العناوين الكبيرة
        if el_type == "empty_line":
            document_model.append({"type": "empty_line"})
            numbered_item_counter = 0
            bullet_item_counter = 0
            continue
            
        if el_type == "heading":
            stats["headings_count"] += 1
            numbered_item_counter = 0
            bullet_item_counter = 0
            
            # استخراج النمط الخاص بالعناوين من قواعد الدستور
            h_style = rules.get("heading_style", "Standard")
            document_model.append({
                "type": "heading",
                "level": analysis["level"],
                "text": analysis["text"],
                "style": h_style
            })
            
        elif el_type == "bullet_list_item":
            stats["lists_count"] += 1
            bullet_item_counter += 1
            document_model.append({
                "type": "bullet_list_item",
                "text": analysis["text"],
                "level": analysis["level"]
            })
            
        elif el_type == "numbered_list_item":
            stats["lists_count"] += 1
            numbered_item_counter += 1
            
            # إصلاح وترقية الترقيم بناءً على خيارات الدستور
            num_style = rules.get("numbering", "Legal") # Legal means 1., 2. or (1)
            prefix = ""
            if num_style == "Legal":
                prefix = f"{numbered_item_counter}."
            elif num_style == "Parenthesis":
                prefix = f"({numbered_item_counter})"
            else:
                prefix = analysis.get("raw_prefix", f"{numbered_item_counter}.")
                
            document_model.append({
                "type": "numbered_list_item",
                "text": analysis["text"],
                "level": analysis["level"],
                "prefix": prefix
            })
            
        elif el_type == "quote":
            document_model.append({
                "type": "quote",
                "text": analysis["text"]
            })
            
        else: # paragraph
            stats["paragraphs_count"] += 1
            document_model.append({
                "type": "paragraph",
                "text": analysis["text"]
            })
            
    return document_model, stats
