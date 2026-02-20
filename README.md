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

## n8n Günlük Rapor Akışı (Aktif Kullanım)

Bu akış uygulamada hazır olan endpoint ile çalışır:
- `GET /api/reports/daily-course-sessions?date=YYYY-MM-DD`
- `GET /api/reports/monthly-course-sessions?month=YYYY-MM` (opsiyonel; verilmezse bir önceki ay)
- Kimlik doğrulama: `Authorization: Bearer <TOKEN>` (admin kullanıcıya ait aktif token)

### n8n tarafında sıralı yapılacaklar
1. `Cron` node: Her gün tetikleme zamanı belirle.
2. `Set` node: `report_date` üret (`YYYY-MM-DD` formatı).
3. `HTTP Request` node:
   - Method: `GET`
   - URL: `http://localhost:5000/api/reports/daily-course-sessions?date={{$json.report_date}}`
   - Header: `Authorization: Bearer <TOKEN>`
4. `IF` node:
   - Status code `200` ise devam et.
   - Hata durumunda ayrı hata bildirimi akışına yönlendir.
5. `Telegram` node (opsiyonel):
   - Günlük özet metni gönder.
6. `Google Drive` node (opsiyonel):
   - Dönen JSON’u dosya olarak sakla (`daily-{{$json.date}}.json`).

### Endpointte dönen ana alanlar
- Genel aktif toplamlar:
  - `total_courses_count`
  - `total_teachers_count`
  - `total_students_count`
  - `total_organizations_count`
- İlgili güne ait özet:
  - `courses_count`
  - `sessions_count`
  - `lesson_delivered_count`
  - `attendance_submitted_sessions_count`
  - `attendance_totals` (`present`, `absent`, `late`, `excused`)
- İlgili güne ait detay:
  - `courses[]`
  - `courses[].sessions[]`
  - `courses[].sessions[].attendance_counts`

### Not
- Rapor sadece `active` statüdeki kurs verilerini baz alır.
- Belirli bir tarihte oturum yoksa `courses: []` ve günlük sayaçlar `0` döner.
- Admin panelinde `API Tokenlar` ekranındaki satır bazlı `Test` butonu ile aynı JSON ayrı sekmede test edilebilir.

### Aylık Rapor (Ayın 1'i İçin)
- n8n zamanlamasını ayın 1'i çalışacak şekilde ayarlayın.
- Endpoint:
  - Otomatik geçen ay: `GET /api/reports/monthly-course-sessions`
  - Belirli ay: `GET /api/reports/monthly-course-sessions?month=2026-02`

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
