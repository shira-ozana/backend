from cryptography.fernet import Fernet

from app.config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode())


def encrypt(value: str) -> str:
    """הצפנת ערך רגיש (סיסמה/טוקן) לפני שמירה ב-DB"""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """פענוח ערך מוצפן - לשימוש פנימי בלבד (למשל clone של הריפו)"""
    return _fernet().decrypt(value.encode()).decode()
