import hashlib


def md5_of_bytes(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def stable_id(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
