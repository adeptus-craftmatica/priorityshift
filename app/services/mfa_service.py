"""TOTP-based two-factor auth (RFC 6238), optional per user. Uses pyotp
rather than hand-rolled crypto — this is security-sensitive code where a
well-tested library beats a bespoke implementation."""

import pyotp

ISSUER_NAME = "PriorityShift"


def generate_secret():
    return pyotp.random_base32()


def provisioning_uri(secret, email):
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER_NAME)


def verify_code(secret, code):
    if not secret or not code:
        return False
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)
