"""
AES-GCM Token Encryption Module
FlyRank Capstone: Multi-Platform Social Campaign Publisher
Author: Deepak R

Ensures zero plaintext OAuth tokens are stored in the database or logs.
Uses AES-GCM (256-bit) with unique cryptographically random 96-bit initialization vectors (IV/nonce).
"""

import os
import binascii
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import ENCRYPTION_KEY_HEX

# Initialize key
_KEY = binascii.unhexlify(ENCRYPTION_KEY_HEX)
_AESGCM = AESGCM(_KEY)


def encrypt_token(plaintext: str) -> Tuple[str, str]:
    """
    Encrypts a plaintext token using AES-GCM with a fresh random 96-bit IV.
    Returns:
        (ciphertext_hex, nonce_hex)
    """
    nonce = os.urandom(12)  # 96-bit nonce
    data = plaintext.encode("utf-8")
    ciphertext = _AESGCM.encrypt(nonce, data, None)
    return binascii.hexlify(ciphertext).decode("utf-8"), binascii.hexlify(nonce).decode("utf-8")


def decrypt_token(ciphertext_hex: str, nonce_hex: str) -> str:
    """
    Decrypts a ciphertext with its corresponding nonce using AES-GCM.
    Returns plaintext string.
    """
    ciphertext = binascii.unhexlify(ciphertext_hex)
    nonce = binascii.unhexlify(nonce_hex)
    decrypted_bytes = _AESGCM.decrypt(nonce, ciphertext, None)
    return decrypted_bytes.decode("utf-8")
