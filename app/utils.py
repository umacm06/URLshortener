# app/utils.py
import string
import secrets

ALPHABET = string.ascii_letters + string.digits

def generate_short_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
