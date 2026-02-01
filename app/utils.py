import json
from datetime import date, timedelta


def serialize_json(data):
    return json.dumps(data, ensure_ascii=False)


def build_schedule_days(selected_days):
    return [day for day in selected_days if day]


def generate_sessions(start_date, end_date, days_of_week):
    if not days_of_week:
        return []
    days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    target_days = {days_map[day] for day in days_of_week if day in days_map}
    sessions = []
    current = start_date
    while current <= end_date:
        if current.weekday() in target_days:
            sessions.append(current)
        current += timedelta(days=1)
    return sessions


def absence_ratio(absent_count, total_sessions):
    if total_sessions == 0:
        return 0
    return absent_count / total_sessions
