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

Test admin (opsiyonel):
```powershell
flask create-test-admin
```
Kullanıcı: testadmin / Şifre: Test123!

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

## Notlar
- WhatsApp ayarları ENV üzerinden yönetilir.
- `absence_threshold_ratio` sistem ayarı ile devamsızlık eşiği belirlenir (varsayılan 0.2).
- Duyurular sadece Ataşe tarafından yayınlanır.
- Raporlarda zamanlar kullanıcı cihazının yerel saatine göre gösterilir.
