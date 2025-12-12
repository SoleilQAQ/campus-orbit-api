import base64


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def encode(username: str, password: str) -> str:
    return f"{_b64(username)}%%%{_b64(password)}"
