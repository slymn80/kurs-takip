import json
import time
import random
import re
import requests
from flask import current_app

from ..extensions import db
from ..models import PlacementQuestion
from ..services.settings import get_setting


SKILL_LABELS = {
    "reading": "Okuma",
    "grammar": "Dilbilgisi",
    "vocab": "Kelime Bilgisi",
    "usage": "İletişim"
}

DIFFICULTY_WEIGHT = {
    "A1": 1.0,
    "A2": 1.2,
    "B1": 1.4,
    "B2": 1.6,
    "C1": 1.8,
}


DEFAULT_PLACEMENT_PROMPT = (
    "EK TALİMAT – TÜRKÇE SEVİYE BELİRLEME SINAVI (PLACEMENT MODE)\n\n"
    "Bu sınav TEK SEVİYE sınavı değildir.\n"
    "Model kesinlikle sadece A1 seviyesinde soru üretmeyecektir.\n\n"
    "ÖNEMLİ KURAL:\n"
    "Default sistemde yer alan \"A1\", \"başlangıç\", \"kolay\" gibi ifadeleri\n"
    "seviye kısıtı olarak yorumlama.\n"
    "Bu sınav bir SEVİYE BELİRLEME SINAVIDIR ve çok seviyeli olmak zorundadır.\n\n"
    "────────────────────\n\n"
    "Sınav Yapısı:\n\n"
    "Toplam 30 soru üret.\n\n"
    "Seviyeler zorunlu olarak şu sırada gelsin:\n\n"
    "1–6   → A1\n"
    "7–12  → A2\n"
    "13–18 → B1\n"
    "19–24 → B2\n"
    "25–30 → C1\n\n"
    "Seviyeler karışık üretilemez ve tek seviyeye düşürülemez.\n\n"
    "────────────────────\n\n"
    "Zorluk Kuralları:\n\n"
    "A1:\n"
    "- tek cümle\n"
    "- günlük kelimeler\n\n"
    "A2:\n"
    "- kısa paragraf\n"
    "- temel zamanlar\n\n"
    "B1:\n"
    "- bağlaçlar, neden-sonuç\n"
    "- kısa okuma parçaları\n\n"
    "B2:\n"
    "- çıkarım gerektiren sorular\n"
    "- daha uzun metin\n\n"
    "C1:\n"
    "- akademik veya yarı akademik dil\n"
    "- yorumlama ve anlam çıkarma\n\n"
    "────────────────────\n\n"
    "Format:\n\n"
    "ÇIKTI SADECE JSON olmalı ve aşağıdaki şemaya uymalıdır.\n"
    "Her soru şu alanları içermelidir: skill, difficulty, prompt, options, correct_index, explanation, audio_url, listening_text.\n\n"
    "────────────────────\n\n"
    "Ek Kurallar:\n\n"
    "- 4 şıklı olacak.\n"
    "- Şıklar rastgele dağılsın.\n"
    "- Her seviyede reading, grammar, vocab, usage dengeli olsun.\n"
    "- Sorular tekrar etmesin.\n"
    "- ÇIKTI SADECE JSON olmalı ve şemaya uymalıdır.\n"
    "- Her soru için kısa bir açıklama yaz (1-2 cümle).\n"
    "- SADECE sınavı üret.\n\n"
    "────────────────────\n\n"
    "KRİTİK TALİMAT:\n\n"
    "Eğer önceki sistem talimatları tek seviyeye yönlendiriyorsa,\n"
    "BU TALİMAT onları geçersiz kılar ve çok seviyeli üretim zorunludur.\n"
    "\n"
    "JSON formatı (şemaya uygun):\n"
    "{\n"
    "  \"questions\": [\n"
    "    {\n"
    "      \"skill\": \"reading|grammar|vocab|usage\",\n"
    "      \"difficulty\": \"A1|A2|B1|B2|C1\",\n"
    "      \"prompt\": \"...\",\n"
    "      \"options\": [\"A\", \"B\", \"C\", \"D\"],\n"
    "      \"correct_index\": 0,\n"
    "      \"explanation\": \"...\",\n"
    "      \"audio_url\": null,\n"
    "      \"listening_text\": null\n"
    "    }\n"
    "  ]\n"
    "}\n"
)


def _placement_prompt():
    override = (get_setting("placement_prompt_override") or "").strip()
    return override or DEFAULT_PLACEMENT_PROMPT


def _openai_headers():
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def _openai_model():
    return current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")


def _extract_json_array(text):
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]


def _normalize_questions(obj):
    if isinstance(obj, dict) and "questions" in obj:
        obj = obj["questions"]
    if not isinstance(obj, list):
        return None
    return obj


def _looks_turkish(text):
    if not text:
        return False
    lowered = text.lower()
    tr_chars = sum(lowered.count(ch) for ch in "çğıöşü")
    common_words = ["ve", "bir", "bu", "ile", "için", "de", "da", "ama", "çok", "şu", "şey", "olan", "olarak"]
    hits = sum(1 for w in common_words if w in lowered)
    return tr_chars >= 1 or hits >= 2


def _is_clean_text(text):
    if not text or len(text.strip()) < 6:
        return False
    banned = ["lorem", "ipsum", "option", "placeholder", "???", "n/a", "tbd"]
    lowered = text.lower()
    if any(b in lowered for b in banned):
        return False
    return _looks_turkish(text)


def _clean_questions(items, strict=True):
    if not items:
        return []
    cleaned = []
    common_stop = {
        "ve", "bir", "bu", "ile", "için", "de", "da", "ama", "çok", "şu", "şey",
        "olan", "olarak", "mi", "mı", "mu", "mü", "ne", "niçin", "neden", "nasıl",
        "ki", "ya", "veya", "ya da", "daha", "en", "gibi", "kadar", "ise", "ama",
        "fakat", "ancak", "çünkü", "bu yüzden", "dolayısıyla"
    }
    technical_banned = {
        "algoritma", "hipotez", "metodoloji", "paradigma", "nükleer", "biyokimya",
        "kuantum", "astronomi", "jeopolitik", "literatür", "statistik"
    }
    for q in items:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            continue
        if q.get("correct_index") not in [0, 1, 2, 3]:
            continue
        if not _is_clean_text(q.get("prompt")):
            continue
        if not _is_clean_text(q.get("explanation")):
            if strict:
                continue
        explanation = q.get("explanation") or ""
        if len(explanation.strip()) < (20 if strict else 8):
            if strict:
                continue
        # Prefer explicit reasoning markers but do not hard-reject if missing.
        if not _looks_turkish(" ".join(options)):
            continue
        if len(set(opt.strip() for opt in options)) != 4:
            continue
        prompt_text = q.get("prompt", "")
        if q.get("skill") == "reading":
            if len(prompt_text) < (100 if strict else 60):
                continue
            sentence_count = sum(1 for ch in prompt_text if ch in ".!?")
            if sentence_count < 2 and strict:
                continue
        if q.get("difficulty") in ["A1", "A2"]:
            lowered_text = (prompt_text + " " + " ".join(options)).lower()
            if any(t in lowered_text for t in technical_banned):
                continue
        if strict:
            # Reject options with too much shared non-stopword overlap.
            word_counts = {}
            for opt in options:
                for w in opt.lower().replace("'", " ").split():
                    if w in common_stop or len(w) < 3:
                        continue
                    word_counts[w] = word_counts.get(w, 0) + 1
            if word_counts and max(word_counts.values()) >= 4:
                continue
        if q.get("listening_text"):
            continue
        if q.get("audio_url"):
            continue
        cleaned.append(q)
    return cleaned


def _question_schema():
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "placement_questions",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": 30,
                        "maxItems": 30,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "skill": {
                                    "type": "string",
                                    "enum": ["reading", "grammar", "vocab", "usage"]
                                },
                                "difficulty": {
                                    "type": "string",
                                    "enum": ["A1", "A2", "B1", "B2", "C1"]
                                },
                                "prompt": {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "minItems": 4,
                                    "maxItems": 4,
                                    "items": {"type": "string"}
                                },
                                "correct_index": {"type": "integer", "enum": [0, 1, 2, 3]},
                                "explanation": {"type": "string"},
                                "audio_url": {"type": ["string", "null"]},
                                "listening_text": {"type": ["string", "null"]}
                            },
                            "required": [
                                "skill",
                                "difficulty",
                                "prompt",
                                "options",
                                "correct_index",
                                "explanation",
                                "audio_url",
                                "listening_text"
                            ]
                        }
                    }
                },
                "required": ["questions"]
            }
        }
    }


def _rebalance_correct_indices(questions):
    if not questions:
        return questions
    total = len(questions)
    base = total // 4
    remainder = total % 4
    targets = []
    for idx in range(4):
        targets.extend([idx] * base)
    if remainder:
        targets.extend(random.sample([0, 1, 2, 3], remainder))
    random.shuffle(targets)
    balanced = []
    for q, target in zip(questions, targets):
        options = q.get("options") or []
        correct_index = q.get("correct_index")
        if len(options) != 4 or correct_index not in [0, 1, 2, 3]:
            balanced.append(q)
            continue
        # Rotate options so the correct option lands at the target index.
        shift = (correct_index - target) % 4
        if shift:
            options = options[shift:] + options[:shift]
        q["options"] = options
        q["correct_index"] = target
        balanced.append(q)
    return balanced


def generate_questions(count=30):
    model = _openai_model()
    count = int(count or 30)
    base_messages = [
        {
            "role": "system",
            "content": (
                "You are a Turkish language assessment expert who designs CEFR-aligned placement tests (A1–C1). "
                "Write culturally neutral, realistic questions for adult learners. "
                "Avoid trick questions or ambiguous answers. "
                "Each question must have one clearly correct option and three plausible distractors. "
                "Use Turkish only. Avoid awkward or nonsensical prompts. Return ONLY valid JSON."
            )
        },
        {
            "role": "user",
            "content": _placement_prompt()
        },
        {
            "role": "user",
            "content": f"Return exactly {count} questions."
        }
    ]

    def _request(payload):
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=_openai_headers(),
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()

    last_error = None
    for _ in range(3):
        payload = {
            "model": model,
            "messages": base_messages,
            "temperature": 0.4,
            "response_format": _question_schema()
        }
        try:
            data = _request(payload)
        except requests.exceptions.ReadTimeout:
            last_error = "read_timeout"
            time.sleep(1.5)
            continue
        except requests.exceptions.RequestException as exc:
            last_error = f"request_error:{type(exc).__name__}"
            time.sleep(1.5)
            continue
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 400:
                payload.pop("response_format", None)
                data = _request(payload)
            else:
                raise
        message = data["choices"][0]["message"]
        if message.get("refusal"):
            last_error = "refusal"
            continue
        content = message.get("content") or ""
        if not content:
            last_error = "empty_content"
            continue
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            extracted = _extract_json_array(content)
            if not extracted:
                last_error = "invalid_json"
                continue
            raw = json.loads(extracted)
        items = _normalize_questions(raw)
        if not items:
            last_error = "invalid_format"
            continue
        cleaned = _clean_questions(items, strict=True)
        if not cleaned:
            cleaned = _clean_questions(items, strict=False)
        if cleaned:
            cleaned = _rebalance_correct_indices(cleaned)
            return cleaned, model
        last_error = "invalid_items"

    raise ValueError(f"LLM returned invalid question list ({last_error}).")


def _next_group_name():
    rows = db.session.query(PlacementQuestion.group_name).distinct().all()
    max_num = 0
    pattern = re.compile(r"grup\s*(\d+)", re.IGNORECASE)
    for (name,) in rows:
        if not name:
            continue
        match = pattern.search(name)
        if match:
            try:
                max_num = max(max_num, int(match.group(1)))
            except ValueError:
                continue
    return f"Grup {max_num + 1}" if max_num else "Grup 1"


def create_question_group(count=30, group_name=None):
    group_name = group_name or _next_group_name()
    count = int(count or 30)
    collected = []
    seen_prompts = set()
    attempts = 0
    while len(collected) < count and attempts < 5:
        attempts += 1
        batch_count = min(15, count - len(collected))
        questions, _ = generate_questions(count=batch_count)
        for q in questions:
            key = (q.get("prompt") or "").strip().lower()
            if not key or key in seen_prompts:
                continue
            seen_prompts.add(key)
            collected.append(q)
            if len(collected) >= count:
                break
    if len(collected) < count:
        raise ValueError("Yeterli kaliteli soru üretilemedi.")
    for q in collected[:count]:
        db.session.add(PlacementQuestion(
            skill=q["skill"],
            difficulty=q["difficulty"],
            prompt=q["prompt"],
            audio_url=None,
            listening_text=None,
            options_json=json.dumps(q["options"], ensure_ascii=False),
            correct_index=q["correct_index"],
            explanation=q.get("explanation") or "",
            is_active=True,
            is_approved=True,
            group_name=group_name
        ))
    db.session.commit()
    return group_name


def _difficulty_weight(question):
    return DIFFICULTY_WEIGHT.get(question.difficulty, 1.0)


def pick_questions(count=30):
    active_group = (get_setting("placement_active_group") or "").strip()
    query = PlacementQuestion.query.filter(PlacementQuestion.is_active.is_(True))
    if active_group:
        query = query.filter(PlacementQuestion.group_name == active_group)
    non_listening_qs = query.all()

    if not non_listening_qs:
        # Fallback: use latest group if active group is empty or invalid
        rows = db.session.query(PlacementQuestion.group_name).order_by(PlacementQuestion.created_at.desc()).all()
        latest_group = next((name for (name,) in rows if name), None)
        if latest_group:
            non_listening_qs = PlacementQuestion.query.filter(
                PlacementQuestion.is_active.is_(True),
                PlacementQuestion.group_name == latest_group
            ).all()
            active_group = latest_group

    if not non_listening_qs:
        raise RuntimeError("Soru grubu bulunamadı. Admin > Seviye Sınavı Yönetimi bölümünden yeni sınav üretin.")

    random.shuffle(non_listening_qs)

    selected_non_listening = non_listening_qs[:max(0, count)]
    selected_non_listening = sorted(selected_non_listening, key=_difficulty_weight)

    questions = selected_non_listening
    if len(questions) < count:
        remaining = [q for q in non_listening_qs if q not in selected_non_listening]
        questions += remaining[:(count - len(questions))]

    for idx, q in enumerate(questions, start=1):
        q._order = idx

    return questions


def score_to_level(score_percent):
    if score_percent >= 85:
        return "C1"
    if score_percent >= 75:
        return "B2"
    if score_percent >= 60:
        return "B1"
    if score_percent >= 45:
        return "A2"
    return "A1"
