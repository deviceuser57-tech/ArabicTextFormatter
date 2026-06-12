from fastapi import APIRouter, HTTPException
from schemas import AIGenerateRequest, AIRewriteRequest, AIReviewRequest, AIAnalyzeRequest, AIDiacritizeRequest, AIChatRequest
import dcos_ai
import dcos_db
import mishkal.tashkeel as tashkeel
import json

router = APIRouter(prefix="/ai", tags=["ai"])
vocalizer = tashkeel.TashkeelClass()

def get_ai_provider(provider_name: str, api_key: str) -> dcos_ai.AIProvider:
    if not api_key or provider_name == "local":
        return dcos_ai.LocalProvider()
    if provider_name == "gemini":
        return dcos_ai.GeminiProvider(api_key=api_key)
    if provider_name == "openai":
        return dcos_ai.OpenAIProvider(api_key=api_key)
    return dcos_ai.LocalProvider()

@router.post("/generate")
def ai_generate(req: AIGenerateRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    try:
        resp_text = provider.generate(req.prompt, req.system_instruction)
        return {"success": True, "text": resp_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rewrite")
def ai_rewrite(req: AIRewriteRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    prompt = f"Rewrite the following text based on this instruction: '{req.instruction}'. Keep the tone proper and output only the rewritten text.\nText:\n{req.text}"
    try:
        resp_text = provider.generate(prompt, "You are a senior document rewriting editor.")
        return {"success": True, "text": resp_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/review")
def ai_review(req: AIReviewRequest):
    local_provider = dcos_ai.LocalProvider()
    rules = dcos_db.get_project_rules(req.project_id)
    local_review = local_provider.review(req.text, rules)
    
    if req.api_key and req.provider != "local":
        ai_provider = get_ai_provider(req.provider, req.api_key)
        try:
            ai_review = ai_provider.review(req.text, rules)
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

@router.post("/analyze")
def ai_analyze(req: AIAnalyzeRequest):
    provider = get_ai_provider(req.provider, req.api_key)
    try:
        resp_data = provider.analyze(req.text, req.aspect)
        return {"success": True, "analysis": resp_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/diacritize")
def ai_diacritize(req: AIDiacritizeRequest):
    try:
        # Action 'last' will be handled if Mishkal allows, otherwise full
        result = vocalizer.tashkeel(req.text)
        return {"success": True, "text": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
def ai_chat(req: AIChatRequest):
    try:
        rules = dcos_db.get_project_rules(req.project_id)
        provider = get_ai_provider(req.provider, req.api_key)
        
        system_instruction = (
            "أنت خبير محرر ومساعد لتدقيق النصوص والدردشة التفاعلية حول المستندات.\n"
            f"قواعد ودستور المشروع الحالي:\n{json.dumps(rules, ensure_ascii=False)}\n"
            "يرجى تقديم إجابات دقيقة واحترافية باللغة العربية بناءً على محتوى المستند المرفق والقواعد المحددة."
        )
        
        prompt = (
            f"محتوى المستند الحالي:\n\"\"\"\n{req.context}\n\"\"\"\n\n"
            f"رسالة المستخدم: {req.message}"
        )
        
        resp_text = provider.generate(prompt, system_instruction)
        return {"success": True, "text": resp_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
