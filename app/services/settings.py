from ..models import SystemSetting


def get_setting(key, default=None):
    setting = SystemSetting.query.filter_by(key=key).first()
    return setting.value if setting else default
