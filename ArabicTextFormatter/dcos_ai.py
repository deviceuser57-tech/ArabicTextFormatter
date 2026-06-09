# dcos_ai.py - تجريد مزودي الذكاء الاصطناعي
from abc import ABC, abstractmethod
import urllib.request
import urllib.error
import json
from typing import Optional, Dict, Any, List

class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """توليد أو استكمال نص"""
        pass

    @abstractmethod
    def analyze(self, content: str, aspect: str) -> Dict[str, Any]:
        """تحليل دلالي للمحتوى"""
        pass

    @abstractmethod
    def review(self, content: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        """مراجعة النص بناءً على قواعد ودستور المشروع"""
        pass

# ============================================================
# 1. GEMINI PROVIDER (Google)
# ============================================================
class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model_name

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise Exception(f"Gemini API Error (HTTP {e.code}): {err_msg}")
        except Exception as e:
            raise Exception(f"Gemini Connection Error: {str(e)}")

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        contents = [{"parts": [{"text": prompt}]}]
        payload: Dict[str, Any] = {"contents": contents}
        
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
            
        res = self._call_api(payload)
        try:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise Exception("Invalid response structure from Gemini API")

    def analyze(self, content: str, aspect: str) -> Dict[str, Any]:
        prompt = f"Analyze the following text regarding: '{aspect}'. Provide your output STRICTLY as a valid JSON object. Text:\n{content}"
        system_instruction = "You are a professional document analysis agent. Always reply with a single JSON object."
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"responseMimeType": "application/json"}
        }
        res = self._call_api(payload)
        try:
            text_resp = res["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_resp)
        except Exception as e:
            return {"error": f"Failed to parse analysis JSON: {str(e)}", "raw_response": str(res)}

    def review(self, content: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        rules_str = json.dumps(rules, ensure_ascii=False)
        prompt = f"Review the following text based on these project constitution rules: {rules_str}.\nIdentify writing issues, styling errors, structure inconsistencies, and potential improvements.\nProvide the output strictly as a JSON object with: {{'score': 0-100, 'issues': [{{'type': 'style|grammar|structure', 'text': 'issue description', 'severity': 'high|medium|low'}}]}}.\nText:\n{content}"
        system_instruction = "You are a strict document quality review inspector. Output only the specified JSON format."
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"responseMimeType": "application/json"}
        }
        res = self._call_api(payload)
        try:
            text_resp = res["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_resp)
        except Exception as e:
            return {"score": 70, "issues": [{"type": "system", "text": "فشل تحليل الجودة الآلي.", "severity": "medium"}]}

# ============================================================
# 2. OPENAI PROVIDER
# ============================================================
class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name

    def _call_api(self, messages: List[Dict[str, str]], response_format: Optional[str] = None) -> Dict[str, Any]:
        url = "https://api.openai.com/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
            
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise Exception(f"OpenAI API Error (HTTP {e.code}): {err_msg}")
        except Exception as e:
            raise Exception(f"OpenAI Connection Error: {str(e)}")

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        res = self._call_api(messages)
        try:
            return res["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise Exception("Invalid response structure from OpenAI API")

    def analyze(self, content: str, aspect: str) -> Dict[str, Any]:
        prompt = f"Analyze the following text regarding: '{aspect}'. Provide your output STRICTLY as a valid JSON object. Text:\n{content}"
        messages = [
            {"role": "system", "content": "You are a professional document analysis agent. Always reply with a single JSON object."},
            {"role": "user", "content": prompt}
        ]
        res = self._call_api(messages, response_format="json")
        try:
            text_resp = res["choices"][0]["message"]["content"]
            return json.loads(text_resp)
        except Exception as e:
            return {"error": f"Failed to parse analysis JSON: {str(e)}"}

    def review(self, content: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        rules_str = json.dumps(rules, ensure_ascii=False)
        prompt = f"Review the following text based on these project constitution rules: {rules_str}.\nIdentify writing issues, styling errors, structure inconsistencies, and potential improvements.\nProvide the output strictly as a JSON object with: {{'score': 0-100, 'issues': [{{'type': 'style|grammar|structure', 'text': 'issue description', 'severity': 'high|medium|low'}}]}}.\nText:\n{content}"
        messages = [
            {"role": "system", "content": "You are a strict document quality review inspector. Output only the specified JSON format."},
            {"role": "user", "content": prompt}
        ]
        res = self._call_api(messages, response_format="json")
        try:
            text_resp = res["choices"][0]["message"]["content"]
            return json.loads(text_resp)
        except Exception as e:
            return {"score": 70, "issues": [{"type": "system", "text": "فشل تحليل الجودة الآلي.", "severity": "medium"}]}

# ============================================================
# 3. LOCAL PROVIDER (Fallback Offline Mockup)
# ============================================================
class LocalProvider(AIProvider):
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        return f"[وضع عدم الاتصال بالإنترنت - محاكاة محلية]\nالطلب الأصلي: {prompt[:100]}..."

    def analyze(self, content: str, aspect: str) -> Dict[str, Any]:
        return {
            "offline": True,
            "aspect": aspect,
            "concepts_detected": [],
            "message": "النظام يعمل محلياً بدون خادم ذكاء اصطناعي."
        }

    def review(self, content: str, rules: Dict[str, Any]) -> Dict[str, Any]:
        # مراجعة برمجية صلبة بسيطة جداً كبديل
        issues = []
        # كشف تماسك الأقواس
        open_b = content.count("(")
        close_b = content.count(")")
        if open_b != close_b:
            issues.append({
                "type": "structure",
                "text": "هناك عدم تماثل في الأقواس الدائرية بالمستند.",
                "severity": "medium"
            })
            
        # كشف وجود علامات اتجاه Unicode مشوهة
        direction_marks = ['\u200E', '\u200F', '\u202A', '\u202B', '\u202C', '\u202D', '\u202E']
        has_marks = any(m in content for m in direction_marks)
        if has_marks:
            issues.append({
                "type": "style",
                "text": "تم كشف علامات اتجاه نصوص مخفية (Unicode control characters).",
                "severity": "low"
            })

        score = max(50, 100 - len(issues) * 15)
        return {
            "score": score,
            "issues": issues,
            "offline": True
        }
