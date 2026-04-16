"""AES-256-GCM 加密/解密测试"""
import pytest
from edu_cloud.modules.conduct.crypto import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "310101200001011234"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext():
    """每次加密产生不同密文（随机 nonce）"""
    plaintext = "hello"
    c1 = encrypt(plaintext)
    c2 = encrypt(plaintext)
    assert c1 != c2
    assert decrypt(c1) == decrypt(c2) == plaintext


def test_decrypt_invalid_returns_none():
    assert decrypt("not-valid-ciphertext") is None
    assert decrypt("") is None


def test_encrypt_none_returns_none():
    assert encrypt(None) is None
    assert encrypt("") is None
