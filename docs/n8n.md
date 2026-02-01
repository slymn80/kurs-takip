# n8n Entegrasyonu

1. n8n'de `Webhook` node oluşturun.
2. URL'yi `N8N_WEBHOOK_URL` olarak ayarlayın.
3. Örnek akışta event_type'a göre switch yapabilirsiniz.

## Önerilen Event Tipleri
- course_created
- session_attendance_submitted
- absence_threshold_exceeded

## Örnek Workflow
- Webhook -> Switch(event_type) -> Slack/Email/CRM
