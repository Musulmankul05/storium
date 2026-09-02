from pwdlib import PasswordHash

hasher = PasswordHash.recommended()

def hash_pwd(plain):
    return hasher.hash(plain)

def verify_pwd(payload, hashed):
    return hasher.verify(payload, hashed)