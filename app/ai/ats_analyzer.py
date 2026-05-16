# app/ai/ats_analyzer.py
import os, json, re
from groq import Groq
from dotenv import load_dotenv
load_dotenv()
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_resume_ats(resume_text: str) -> dict:
    prompt = f"""You are an ATS resume expert. Analyze this resume and return ONLY valid JSON (no markdown):

RESUME:
{resume_text[:4000]}

Return exactly:
{{
  "ats_score": <0-100>,
  "strengths": ["s1","s2","s3"],
  "improvements": ["i1","i2","i3","i4"],
  "missing_sections": ["m1","m2"],
  "keywords_found": ["k1","k2","k3","k4","k5"],
  "summary": "2 sentence summary"
}}
Scoring: 85-100 Excellent, 70-84 Good, 50-69 Average, below 50 Poor."""

    try:
        res = _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":"Return only valid JSON. No markdown."},
                      {"role":"user","content":prompt}],
            temperature=0.2, max_tokens=800)
        raw = re.sub(r"```json|```","",res.choices[0].message.content.strip()).strip()
        data = json.loads(raw)
        return {
            "ats_score":        min(100, max(0, int(data.get("ats_score",50)))),
            "strengths":        data.get("strengths",[]),
            "improvements":     data.get("improvements",[]),
            "missing_sections": data.get("missing_sections",[]),
            "keywords_found":   data.get("keywords_found",[]),
            "summary":          data.get("summary",""),
        }
    except Exception as e:
        return {"ats_score":0,"strengths":[],"improvements":[str(e)],"missing_sections":[],"keywords_found":[],"summary":"Failed."}
