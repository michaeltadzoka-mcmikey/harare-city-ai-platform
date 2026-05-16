# dashboard/utils/encryption.py
from cryptography.fernet import Fernet
from flask import current_app
import os

def get_encryption_key():
    """Load or generate encryption key."""
    key_file = current_app.config['ENCRYPTION_KEY_FILE']
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def encrypt(text):
    """Encrypt text using Fernet."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(text.encode()).decode()

def decrypt(encrypted_text):
    """Decrypt text."""
    key = get_encryption_key()
    f = Fernet(key)
    return f.decrypt(encrypted_text.encode()).decode()