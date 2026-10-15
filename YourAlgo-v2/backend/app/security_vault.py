import base64
import hashlib
from cryptography.fernet import Fernet
from .config import settings

def _get_fernet_key() -> bytes:
    # Derive deterministic 32-byte key from secret_key
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        fernet = Fernet(_get_fernet_key())
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""

def mask_account_id(account_id: str) -> str:
    if not account_id:
        return "XXXX1234"
    if len(account_id) <= 4:
        return f"XXXX{account_id}"
    return f"XXXX{account_id[-4:]}"
