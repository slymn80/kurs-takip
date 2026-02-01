# Almatı Eğitim Ataşeliği Kurs Takip

Flask + TailwindCSS tabanlı kurs takip uygulaması. Render.com için hazır.

## Özellikler
- RBAC: teacher, coordinator, principal, attache, admin
- Kurs oluşturma, kursiyer kayıt, oturum ve yoklama
- Tanımlamalar CRUD
- İstatistikler (Chart.js)
- WhatsApp ve n8n webhook entegrasyonu
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

Varsayılan kullanıcılar:
- admin / Admin123!
- coordinator / Coordinator123!
- teacher / Teacher123!

## Render Deploy
- Render'da PostgreSQL DB oluşturun.
- `render.yaml` ile deploy edin.
- ENV:
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `N8N_WEBHOOK_URL`
  - `WHATSAPP_PROVIDER`

Build: `pip install -r requirements.txt && npm ci && npm run build:css && flask db upgrade`

Start: `gunicorn app.wsgi:app`

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
- WhatsApp ayarları `ENV` üzerinden yönetilir.
- `absence_threshold_ratio` sistem ayarı ile devamsızlık eşiği belirlenir (varsayılan 0.2).
