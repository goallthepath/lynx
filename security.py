import os
import base58
import logging
from solana.publickey import PublicKey
from cryptography.fernet import Fernet

# ----------------------------------------------------------------
# KEY VALIDATION FUNCTIONS
# ----------------------------------------------------------------

def validate_private_key(key_str: str) -> bool:
    """
    Validate a Solana private key.
    
    This function attempts to decode a Base58-encoded key and checks if its length 
    matches the expected length (64 bytes for a full secret key).
    
    :param key_str: The Base58-encoded private key string.
    :return: True if valid, False otherwise.
    """
    try:
        decoded = base58.b58decode(key_str)
        if len(decoded) == 64:
            return True
        else:
            logging.error("Private key decoded length is not 64 bytes.")
            return False
    except Exception as e:
        logging.error(f"Failed to decode private key: {e}")
        return False

def validate_public_key(key_str: str) -> bool:
    """
    Validate a Solana public key.
    
    This function attempts to create a PublicKey object. If successful, the key is valid.
    
    :param key_str: The public key as a string.
    :return: True if valid, False otherwise.
    """
    try:
        PublicKey(key_str)
        return True
    except Exception as e:
        logging.error(f"Invalid public key: {e}")
        return False

# ----------------------------------------------------------------
# SENSITIVE DATA MASKING
# ----------------------------------------------------------------

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data by displaying only the first and last few characters.
    
    :param data: The sensitive data string.
    :param visible_chars: Number of characters to show at the start and end.
    :return: The masked string.
    """
    if len(data) <= 2 * visible_chars:
        return "*" * len(data)
    return data[:visible_chars] + "*" * (len(data) - 2 * visible_chars) + data[-visible_chars:]

def safe_log_sensitive(message: str, sensitive_data: str) -> None:
    """
    Log a message while masking the sensitive data.
    
    :param message: The log message.
    :param sensitive_data: The sensitive data to mask.
    """
    masked = mask_sensitive_data(sensitive_data)
    logging.info(f"{message}: {masked}")

# ----------------------------------------------------------------
# ENCRYPTION / DECRYPTION FUNCTIONS
# ----------------------------------------------------------------

def load_encryption_key() -> bytes:
    """
    Load an encryption key from a file, or generate one if not available.
    
    :return: The encryption key as bytes.
    """
    key_file = "encryption.key"
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    return key

def encrypt_data(plain_text: str) -> str:
    """
    Encrypt sensitive data using Fernet symmetric encryption.
    
    :param plain_text: The data to encrypt.
    :return: The encrypted data as a string.
    """
    key = load_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plain_text.encode())
    return encrypted.decode()

def decrypt_data(encrypted_text: str) -> str:
    """
    Decrypt data that was encrypted using the encrypt_data function.
    
    :param encrypted_text: The encrypted data as a string.
    :return: The decrypted plain text.
    """
    key = load_encryption_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_text.encode())
    return decrypted.decode()
