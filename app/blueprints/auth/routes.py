from datetime import datetime, timedelta
from collections import deque
import re
import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from ...utils import serialize_json
from ...extensions import db, bcrypt
from ...models import User, AuditLog, Course, Enrollment, Student, Teacher, Organization
from ...forms import LoginForm, ChangePasswordForm, PasswordUpdateForm
from ...services.settings import get_setting


auth_bp = Blueprint("auth", __name__)

_login_attempts = {}
MAX_ASSISTANT_MESSAGE_LENGTH = 1200
ALMATI_SITE_URL = "https://almati.meb.gov.tr/"

DEFAULT_LOGIN_ASSISTANT_PROMPT = (
    "Sen Almatı Eğitim Ataşeliği Kurs Takip Otomasyonu için YZ 7/24 asistansın.\n"
    "Sadece aşağıdaki tek bilgi kaynağına dayanarak cevap ver. Bilgi uydurma.\n"
    "Desteklenen diller: tr, kz, ru, en. Seçilen dilde yanıt ver.\n"
    "Kapsam: Türkçe kurslar, ön kayıt, seviye sınavı, kurs süreçleri, iletişim ve genel yönlendirme.\n"
    "Kişisel veri güvenliği: telefon, e-posta, T.C./IIN gibi hassas bilgileri paylaşma.\n"
    "Bilgi kaynağında olmayan bir konuda net şekilde 'Bu konuda güncel/ek bilgi yok' de.\n\n"
    "Yeni açılan/açılacak kurslar (kaynak: turkce_kurs_listesi.xlsx):\n"
    "- TR-A1-101 | Talgar Dil Akademisi | Günlük Türkçe Başlangıç | A1 | Pazartesi-Çarşamba | 18:30–20:00 | 10 Mart 2026 | 48 Saat | Elif Kaya | Yüz Yüze\n"
    "- TR-A2-204 | Astana Language Hub | Konuşma Odaklı Türkçe | A2 | Salı-Perşembe | 19:00–20:30 | 12 Mart 2026 | 60 Saat | Mehmet Arslan | Online\n"
    "- TR-B1-315 | Orta Asya Eğitim Merkezi | Akademik Türkçe | B1 | Cumartesi | 10:00–13:00 | 15 Mart 2026 | 36 Saat | Aigerim N. | Hibrit\n"
    "- TR-B2-402 | Global Edu Center | İş Türkçesi | B2 | Pazartesi | 20:00–22:00 | 17 Mart 2026 | 40 Saat | Serkan Demir | Online\n"
    "- TR-C1-550 | Türkçe Kültür Enstitüsü | İleri Seviye Tartışma | C1 | Pazar | 11:00–14:00 | 22 Mart 2026 | 30 Saat | Zeynep Yılmaz | Yüz Yüze\n"
    "- TR-A1-118 | Steppe Language School | Hızlandırılmış Türkçe | A1 | Pazartesi-Salı-Çarşamba | 09:00–11:00 | 25 Mart 2026 | 72 Saat | Daniyar K. | Yüz Yüze\n"
    "- TR-B1-377 | Nova Education | Üniversite Hazırlık Türkçesi | B1 | Cuma | 18:00–21:00 | 28 Mart 2026 | 45 Saat | Nazlı Çetin | Online\n"
    "- TR-A2-290 | SilkRoad Language Center | Günlük Diyalog Atölyesi | A2 | Çarşamba-Cuma | 17:30–19:00 | 30 Mart 2026 | 32 Saat | Murat Akın | Hibrit\n"
    "- TR-C1-600 | Eurasia Academy | Akademik Yazım Türkçesi | C1 | Cumartesi-Pazar | 14:00–16:00 | 5 Nisan 2026 | 50 Saat | Prof. Deniz Ö. | Online\n"
)

COURSE_SCOPE_KEYWORDS = [
    "kurs", "kursiyer", "ön kayıt", "kayit", "kayıt", "seviye", "sınav", "sinav", "öğretmen",
    "ogretmen", "ders", "başvuru", "basvuru", "iletişim", "iletisim", "ataşelik", "ataselik",
    "türkçe", "turkce", "program", "saat", "takvim", "sonuç", "sonuc", "sertifika",
    "almati", "almatı", "meb", "site", "web", "internet",
    "course", "registration", "pre-registration", "placement", "exam", "contact", "website",
    "курс", "регистрация", "экзамен", "сайт", "контакт",
    "курс", "тіркеу", "емтихан", "сайт", "байланыс"
]
ALLOWED_ASSISTANT_LANGS = {"tr", "kz", "ru", "en"}
LANG_DISPLAY = {
    "tr": "Türkçe",
    "kz": "Kazakça",
    "ru": "Rusça",
    "en": "İngilizce",
}
SCOPE_REFUSAL_BY_LANG = {
    "tr": "Bu asistan yalnızca Türkçe kurslar, ön kayıt, seviye sınavı, iletişim ve ilgili genel bilgiler hakkında yardımcı olur.",
    "kz": "Бұл көмекші тек түрік тілі курстары, алдын ала тіркеу, деңгейлік емтихан, байланыс және жалпы қатысты ақпарат бойынша көмектеседі.",
    "ru": "Этот ассистент помогает только по курсам турецкого языка, предрегистрации, уровневому экзамену, связи и общей релевантной информации.",
    "en": "This assistant only helps with Turkish language courses, pre-registration, placement exam, contact, and related general information.",
}
INTERNAL_INFO_REFUSAL_BY_LANG = {
    "tr": "Bu bilgiye erişmek için giriş yapmanız gerekir.",
    "kz": "Бұл ақпаратқа қол жеткізу үшін жүйеге кіру керек.",
    "ru": "Для доступа к этой информации необходимо войти в систему.",
    "en": "You need to sign in to access this information.",
}


def _rate_key(ip, username):
    normalized = (username or "").strip().lower()
    return f"{ip}:{normalized}"


def _get_bucket(key):
    entry = _login_attempts.get(key)
    if not entry:
        entry = {"attempts": deque(), "locked_until": None}
        _login_attempts[key] = entry
    return entry


def _prune_attempts(entry, window_seconds):
    now = datetime.utcnow()
    dq = entry["attempts"]
    while dq and (now - dq[0]).total_seconds() > window_seconds:
        dq.popleft()
    return dq


def _is_assistant_scope_question(text):
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    return any(keyword in lowered for keyword in COURSE_SCOPE_KEYWORDS)


def _fetch_almati_site_context():
    try:
        resp = requests.get(ALMATI_SITE_URL, timeout=8)
        if resp.status_code >= 400:
            return ""
        html = resp.text or ""
        html = re.sub(r"<script[\\s\\S]*?</script>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\\s\\S]*?</style>", " ", html, flags=re.IGNORECASE)

        title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""

        h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
        h1_text = " | ".join(re.sub(r"<[^>]+>", "", h).strip() for h in h1_matches[:3])

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\\s+", " ", text).strip()
        text = text[:1200]

        parts = []
        if title:
            parts.append(f"Başlık: {title}")
        if h1_text:
            parts.append(f"Öne çıkan başlıklar: {h1_text}")
        if text:
            parts.append(f"Sayfa özeti: {text}")
        return "\n".join(parts)
    except requests.RequestException:
        return ""


def _tokenize_query(text):
    raw = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]+", (text or "").lower())
    stop = {
        "ve", "ile", "için", "icin", "olan", "olarak", "hakkında", "hakkinda", "nedir", "nasıl", "nasil",
        "hangi", "kaç", "kac", "var", "mı", "mi", "mu", "mü", "the", "and", "for", "about", "what", "how"
    }
    return [w for w in raw if len(w) >= 3 and w not in stop]


def _knowledge_answer_from_markdown(question, knowledge_md, lang):
    if not knowledge_md:
        return None
    keywords = _tokenize_query(question)
    if not keywords:
        return None

    lines = [ln.strip() for ln in knowledge_md.splitlines() if ln.strip()]
    noise_patterns = [
        "buraya kurs içerikleri",
        "ön kayıt bağlantısı",
        "görsel:",
        "# asistan bilgi tabanı",
        "## örnek"
    ]
    scored = []
    for ln in lines:
        low = ln.lower()
        if any(n in low for n in noise_patterns):
            continue
        score = sum(1 for k in keywords if k in low)
        if score > 0:
            scored.append((score, ln))
    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    top_lines = []
    seen = set()
    for _, line in scored:
        if line in seen:
            continue
        seen.add(line)
        top_lines.append(line)
        if len(top_lines) >= 6:
            break

    if lang == "kz":
        title = "Bilgi kaynağındaki ilgili kayıtlar:"
    elif lang == "ru":
        title = "Подходящие записи из базы знаний:"
    elif lang == "en":
        title = "Relevant records from knowledge source:"
    else:
        title = "Bilgi kaynağındaki ilgili kayıtlar:"
    return title + "\n" + "\n".join(f"- {ln}" for ln in top_lines)


def _is_public_course_catalog_question(text):
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    patterns = [
        "aktif kurslar", "active courses", "hangi kurs", "hangi kurum", "kurslar nerede",
        "kurs seviyeleri", "günleri saatleri", "kurs programı", "course schedule",
        "where are the courses", "какие курсы", "қай курстар"
    ]
    return any(p in lowered for p in patterns)


def _format_schedule(schedule_json):
    if not schedule_json:
        return "-"
    if isinstance(schedule_json, dict):
        schedule_json = [schedule_json]
    if not isinstance(schedule_json, list):
        return "-"

    parts = []
    for row in schedule_json:
        if not isinstance(row, dict):
            continue
        day = (
            row.get("day")
            or row.get("day_name")
            or row.get("weekday")
            or row.get("label")
            or ""
        )
        start = row.get("start_time") or row.get("start") or row.get("from") or ""
        end = row.get("end_time") or row.get("end") or row.get("to") or ""
        if day and start and end:
            parts.append(f"{day} {start}-{end}")
        elif day:
            parts.append(str(day))
    return ", ".join(parts) if parts else "-"


def _public_course_catalog_reply(lang):
    courses = (
        Course.query
        .filter(Course.status == "active")
        .order_by(Course.start_date.asc(), Course.title.asc())
        .limit(12)
        .all()
    )
    if not courses:
        if lang == "kz":
            return "Қазіргі уақытта белсенді курс табылмады."
        if lang == "ru":
            return "В данный момент активных курсов не найдено."
        if lang == "en":
            return "No active courses are currently available."
        return "Şu anda aktif kurs bulunmuyor."

    lines = []
    if lang == "kz":
        lines.append("Белсенді курстар (қоғамдық ақпарат):")
    elif lang == "ru":
        lines.append("Активные курсы (публичная информация):")
    elif lang == "en":
        lines.append("Active courses (public information):")
    else:
        lines.append("Aktif kurslar (kamuya açık bilgi):")

    for idx, c in enumerate(courses, start=1):
        kurum = c.organization.name if c.organization else (c.organization_name_cached or "-")
        yer = c.location.name if c.location else (c.location_name_cached or "-")
        seviye = c.course_type.name if c.course_type else (c.course_type_name_cached or "-")
        tarih = "-"
        if c.start_date and c.end_date:
            tarih = f"{c.start_date.strftime('%d.%m.%Y')} - {c.end_date.strftime('%d.%m.%Y')}"
        program = _format_schedule(c.schedule_json)
        lines.append(
            f"{idx}. {c.title} | Kurum: {kurum} | Yer: {yer} | Seviye: {seviye} | Tarih: {tarih} | Gün/Saat: {program}"
        )

    if lang == "kz":
        lines.append("Құпиялылық үшін мұғалімнің аты-жөні, телефон және e-mail бөлісілмейді.")
    elif lang == "ru":
        lines.append("В целях конфиденциальности ФИО преподавателя, телефон и e-mail не раскрываются.")
    elif lang == "en":
        lines.append("For privacy, teacher name, phone, and email are not shared.")
    else:
        lines.append("Gizlilik için öğretmen adı, telefon ve e-posta paylaşılmaz.")
    return "\n".join(lines)


def _is_internal_info_question(text):
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    internal_patterns = [
        "kaç aktif kurs", "kac aktif kurs", "aktif kurs say", "aktif kurs sayisi",
        "active course", "how many active course", "kaç kurs", "kac kurs", "kurs sayısı",
        "kurs sayisi", "internal", "sistemde kaç", "sistemde kac", "kaç öğretmen", "kac ogretmen",
        "kaç kursiyer", "kac kursiyer",
        "сколько активных курсов", "қанша белсенді курс"
    ]
    if ("aktif" in lowered and "kurs" in lowered and ("var" in lowered or "adet" in lowered or "sayi" in lowered or "sayı" in lowered)):
        return True
    if (("aktif" in lowered or "active" in lowered) and ("kurs" in lowered or "course" in lowered) and ("kaç" in lowered or "kac" in lowered or "say" in lowered or "how many" in lowered)):
        return True
    return any(p in lowered for p in internal_patterns)


def _direct_internal_answer(text, lang):
    lowered = (text or "").strip().lower()
    if any(p in lowered for p in ["kaç aktif kurs", "aktif kurs say", "active course", "how many active course", "сколько активных курсов", "қанша белсенді курс"]):
        active_courses = Course.query.filter(Course.status == "active").count()
        if lang == "kz":
            return f"Қазір жүйеде белсенді курс саны: {active_courses}."
        if lang == "ru":
            return f"Текущее количество активных курсов в системе: {active_courses}."
        if lang == "en":
            return f"Current number of active courses in the system: {active_courses}."
        return f"Sistemdeki aktif kurs sayısı: {active_courses}."
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        ip = request.remote_addr or "unknown"
        window = current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"]
        max_attempts = current_app.config["LOGIN_RATE_LIMIT_MAX"]
        base_lock_seconds = current_app.config["LOGIN_LOCKOUT_BASE_SECONDS"]
        key = _rate_key(ip, form.username.data)
        entry = _get_bucket(key)
        now = datetime.utcnow()
        if entry["locked_until"] and now < entry["locked_until"]:
            flash("Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.", "error")
            return render_template("auth/login.html", form=form)
        dq = _prune_attempts(entry, window)
        if len(dq) >= max_attempts:
            lock_seconds = min(900, base_lock_seconds * (2 ** max(0, len(dq) - max_attempts)))
            entry["locked_until"] = now + timedelta(seconds=lock_seconds)
            flash("Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.", "error")
            return render_template("auth/login.html", form=form)

        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active and bcrypt.check_password_hash(user.password_hash, form.password.data):
            session.pop("_flashes", None)
            login_user(user)
            _login_attempts.pop(key, None)
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("dashboard.index"))
        dq.append(now)
        if len(dq) >= max_attempts:
            lock_seconds = min(900, base_lock_seconds * (2 ** max(0, len(dq) - max_attempts)))
            entry["locked_until"] = now + timedelta(seconds=lock_seconds)
        remaining = max_attempts - len(dq)
        if not user:
            flash("Kullanıcı adı hatalı.", "error")
        elif not user.is_active:
            flash("Kullanıcı pasif.", "error")
        else:
            if remaining > 0:
                flash(f"Şifre hatalı. Kalan deneme: {remaining}.", "error")
            else:
                flash("Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.", "error")
    elif request.method == "POST":
        if "csrf_token" in form.errors:
            flash("Oturum süresi doldu. Lütfen sayfayı yenileyin.", "error")
        elif form.username.errors or form.password.errors:
            flash("Kullanıcı adı ve şifre zorunlu.", "error")
        else:
            flash("Giriş başarısız. Lütfen tekrar deneyin.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/login-assistant/chat", methods=["POST"])
def login_assistant_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    lang = (data.get("lang") or "tr").strip().lower()
    if not message:
        return jsonify({"error": "missing_message"}), 400
    if len(message) > MAX_ASSISTANT_MESSAGE_LENGTH:
        return jsonify({"error": "message_too_long"}), 400
    if lang not in ALLOWED_ASSISTANT_LANGS:
        return jsonify({"error": "unsupported_language"}), 400

    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "assistant_unavailable"}), 503

    base_prompt = (get_setting("login_assistant_prompt", DEFAULT_LOGIN_ASSISTANT_PROMPT) or "").strip()
    if not base_prompt:
        base_prompt = DEFAULT_LOGIN_ASSISTANT_PROMPT
    system_prompt = (
        "Kurallar:\n"
        f"- Yalnızca seçili dilde yanıt ver: {LANG_DISPLAY.get(lang, 'Türkçe')} ({lang}).\n"
        "- Bu dil kuralı, önceki tüm dil talimatlarını geçersiz kılar.\n"
        "- Yalnızca şu diller desteklenir: tr, kz, ru, en. Bunun dışındaki dil taleplerini nazikçe reddet.\n"
        "Sadece aşağıdaki TEK PROMPT KAYNAĞINA dayanarak cevap ver.\n"
        "Prompt dışında ek veri kaynağı kullanma.\n\n"
        "Tek Prompt Kaynağı:\n"
        f"{base_prompt}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    if isinstance(history, list):
        for item in history[-6:]:
            if not isinstance(item, dict):
                continue
            role = (item.get("role") or "").strip()
            content = (item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[:MAX_ASSISTANT_MESSAGE_LENGTH]})
    messages.append({"role": "user", "content": message})

    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "max_tokens": 400,
                "messages": messages,
            },
            timeout=25
        )
        if response.status_code >= 400:
            return jsonify({"error": "assistant_upstream_error"}), 502
        payload = response.json() or {}
        reply = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not reply:
            return jsonify({"error": "empty_reply"}), 502
        return jsonify({"reply": reply})
    except requests.RequestException:
        return jsonify({"error": "assistant_request_failed"}), 502


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.password_hash = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        current_user.must_change_password = False
        db.session.add(current_user)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="password_changed",
            entity_type="user",
            entity_id=current_user.id,
            after_json=serialize_json({"user_id": current_user.id})
        ))
        db.session.commit()
        flash("Şifre güncellendi.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/profile/password", methods=["GET", "POST"])
@login_required
def update_password():
    form = PasswordUpdateForm()
    if form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, form.current_password.data):
            flash("Mevcut şifre hatalı.", "error")
            return render_template("auth/update_password.html", form=form)
        if form.new_password.data != form.confirm_password.data:
            flash("Yeni şifreler eşleşmiyor.", "error")
            return render_template("auth/update_password.html", form=form)
        current_user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode("utf-8")
        current_user.must_change_password = False
        db.session.add(current_user)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="password_changed",
            entity_type="user",
            entity_id=current_user.id,
            after_json=serialize_json({"user_id": current_user.id})
        ))
        db.session.commit()
        flash("Şifre güncellendi.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/update_password.html", form=form)

