# Eğitim Ataşeliği Kurs Takip

Flask + TailwindCSS tabanlı kurs takip uygulaması. Render.com için hazır.

## Özellikler
- RBAC: teacher, coordinator, principal, attache, admin
- Kurs oluşturma, kursiyer kayıt, oturum ve yoklama
- Tanımlamalar CRUD (kurum, yer, kurs tipi, öğretmen)
- İstatistikler (Chart.js)
- Raporlar (PDF + XLSX)
- İletişim panosu (öğretmen notları)
- Duyurular (yalnızca Ataşe yayınlar)
- Audit log ve sistem ayarları

## Kurulum (Local)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
npm install
npm run build:css
flask db upgrade
flask seed
flask run
```

Varsayılan kullanıcılar (seed):
- admin / Admin123!
- coordinator / Coordinator123!
- teacher / Teacher123!

Test kullanıcılar (opsiyonel):
```powershell
flask create-test-user
flask create-test-admin
```
- test / Test123!
- testadmin / Test123!

## Şifre Değiştirme
- Menüden **Şifre Değiştir** sayfasına gidin.
- Mevcut şifre + yeni şifre (2 kez) girilerek güncellenir.

## Render Deploy (PostgreSQL)
1) Render’da PostgreSQL DB oluşturun.
2) Web Service ekleyin.

Build:
```
pip install -r requirements.txt && npm ci && npm run build:css && flask db upgrade
```

Start:
```
gunicorn app.wsgi:app
```

ENV:
- DATABASE_URL (Internal Database URL)
- SECRET_KEY
- FLASK_APP=app.wsgi:app
- FLASK_ENV=production
- PYTHON_VERSION=3.11.8
- NODE_VERSION=20.11.1
- N8N_WEBHOOK_URL (opsiyonel)
- WHATSAPP_PROVIDER (varsayılan: disabled)

İlk deploy sonrası (opsiyonel):
```
flask seed
```

## n8n Webhook Payload
```json
{
  "event_type": "course_created",
  "timestamp": "2026-02-01T01:00:00Z",
  "actor_user_id": 1,
  "course_id": 10,
  "session_id": 55,
  "student_id": 12,
  "data": {
    "title": "Hazırlık Kursu"
  }
}
```

## Planlanan İş: Günlük/Aylık Rapor (n8n + Telegram + Google Drive)

Bu iş **şimdilik planlanan** bir geliştirmedir. Uygulama içinde yapılmayacak; n8n akışı ile çalışacaktır.

**Hedef**
- Ataşeye **günlük** ve **aylık** raporların Telegram üzerinden gönderilmesi
- Aynı raporların Google Drive’a **JSON dosyası** olarak yedeklenmesi
- Rapor dosya adları tarihli olacak:
  - Günlük: `daily-YYYY-MM-DD.json`
  - Aylık: `monthly-YYYY-MM.json`

**Günlük Rapor İçeriği (öneri)**
- Üst bilgi: `report_type`, `date`, `generated_at`, `timezone`
- Özet metrikler:
  - `courses_active_count`
  - `courses_started_today`
  - `sessions_today_count`
  - `attendance_submitted_today`
  - `students_new_count`
  - `pre_registrations_new`
  - `placement_tests_completed_today`
  - `certificates_issued_today`
- Detay listeleri:
  - `sessions_today`: `session_id`, `course_title`, `date`, `start_time`, `end_time`, `teacher_name`,
    `attendance_present`, `attendance_absent`, `attendance_late`, `attendance_excused`
  - `students_new`: `student_id`, `full_name`, `phone`, `email` (IIN/TC **opsiyonel**)
  - `pre_registrations_new`: `full_name`, `phone`, `email`, `course_level` (IIN/TC **opsiyonel**)
  - `placement_tests_completed`: `candidate_name`, `score_percent`, `level`, `group_name`, `completed_at`

**Aylık Rapor İçeriği (öneri)**
- Üst bilgi: `report_type`, `month`, `generated_at`, `timezone`
- Özet metrikler:
  - `courses_active_count`
  - `courses_started_month`
  - `courses_completed_month`
  - `sessions_total_month`
  - `attendance_present_total`
  - `attendance_absent_total`
  - `attendance_rate_avg`
  - `students_new_month`
  - `pre_registrations_new_month`
  - `placement_tests_completed_month`
  - `certificates_issued_month`
- Detay listeleri:
  - `courses_started`: `course_id`, `title`, `start_date`, `end_date`, `teacher_name`, `organization`
  - `attendance_summary_by_course`: `course_id`, `title`, `present`, `absent`, `late`, `excused`, `attendance_rate`
  - `placement_summary`: `avg_score`, `level_distribution`, `group_usage`

**Kişisel Veri Notu**
- IIN/TC bilgisi raporlarda **opsiyonel** tutulmalı.
- Gerekirse maskeleme (son 4 hane) uygulanabilir.

**Planlanan Akış (n8n)**
1. Cron (günlük/aylık) → uygulamadan rapor JSON çek
2. Telegram’a raporu gönder
3. Google Drive’a aynı JSON dosyasını yükle

## Notlar
- WhatsApp ayarları ENV üzerinden yönetilir.
- `absence_threshold_ratio` sistem ayarı ile devamsızlık eşiği belirlenir (varsayılan 0.2).
- Duyurular sadece Ataşe tarafından yayınlanır.
- Raporlarda zamanlar kullanıcı cihazının yerel saatine göre gösterilir.

## API Kimlik Doğrulama
API uçları artık Bearer token ile çalışır.

Token oluşturma:
```powershell
flask create-api-token --username admin --name "integration"
```

Kullanım:
```
Authorization: Bearer <TOKEN>
```
