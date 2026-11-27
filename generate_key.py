"""מייצר מפתח הצפנה ל-ENCRYPTION_KEY בקובץ .env"""
from cryptography.fernet import Fernet

print(Fernet.generate_key().decode())
