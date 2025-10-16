import base64
import hashlib


def hash_str(string: str, n_hash: int = 9) -> int:
    return int(hashlib.sha256(string.encode("utf-8")).hexdigest(), 16) % 10 ** n_hash


def create_task_id(audio_bytes: bytes = None, url: str = None):
    if audio_bytes:
        # NOTE(by ducnt2): using base64 format to avoid errors when hassing
        audio_bytes = base64.b64encode(audio_bytes).decode("ascii")
        audio_id = str(audio_bytes)
        audio_id = hash_str(audio_id)
    elif url:
        audio_id = hash_str(url)

    task_id = f"{audio_id}"
    task_id = int(f"{hash_str(task_id, 6)}")


def seconds_to_min_sec(seconds):
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes}:{secs:02d}"
