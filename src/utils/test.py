import argparse
import asyncio
import sys
from pathlib import Path

from .utils import hash_str, create_task_id
from .dialogue_utils import call_dialogue_api
from .audio_analysis import extract_features


def read_file_bytes(file_path: str) -> bytes:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
    return path.read_bytes()


async def maybe_call_dialogue(audio_bytes: bytes, task_id: int, *, timeout: float, verbose: bool):
    try:
        result = await call_dialogue_api(
            audio_bytes=audio_bytes,
            task_id=task_id,
            max_poll_seconds=timeout,
            poll_interval_seconds=0.5,
            verbose=verbose,
        )
        print("Kết quả call_dialogue_api:")
        print(result)
    except Exception as exc:
        print(f"Lỗi khi gọi call_dialogue_api: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Kiểm thử utils, dialogue_utils và audio_analysis")
    parser.add_argument("--audio-file", type=str, default=None, help="Đường dẫn tới file WAV để test API")
    parser.add_argument("--audio-url", type=str, default=None, help="URL file audio để tạo task_id (không tải)")
    parser.add_argument("--analyze", action="store_true", help="Gọi extract_features để phân tích audio")
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout (giây) chờ kết quả API")
    parser.add_argument("--verbose", action="store_true", help="In log polling chi tiết")

    args = parser.parse_args()

    # Test hash_str
    sample_text = "xin chao cloud callcenter qa"
    h9 = hash_str(sample_text, 9)
    h6 = hash_str(sample_text, 6)
    print(f"hash_str('{sample_text}', 9) = {h9}")
    print(f"hash_str('{sample_text}', 6) = {h6}")

    # Chuẩn bị dữ liệu cho create_task_id
    audio_bytes = None
    if args.audio_file:
        try:
            audio_bytes = read_file_bytes(args.audio_file)
            print(f"Đã đọc {len(audio_bytes)} bytes từ '{args.audio_file}'")
        except Exception as e:
            print(f"Không đọc được file audio: {e}")

    # Test create_task_id
    try:
        task_id = create_task_id(audio_bytes=audio_bytes, url=args.audio_url)
        print(f"create_task_id(...) = {task_id}")
    except Exception as exc:
        print(f"Lỗi khi gọi create_task_id: {exc}")
        task_id = None

    # Gọi API nếu có audio_bytes và có task_id hợp lệ
    if audio_bytes is not None and isinstance(task_id, int):
        asyncio.run(maybe_call_dialogue(audio_bytes=audio_bytes, task_id=task_id, timeout=args.timeout, verbose=args.verbose))
    else:
        print("Bỏ qua gọi API (cần '--audio-file' và 'task_id' hợp lệ).")

    # Phân tích audio nếu có cờ --analyze và có audio_bytes
    if args.analyze and audio_bytes is not None:
        try:
            print("\nĐang chạy extract_features ...")
            result = asyncio.run(extract_features(audio_bytes))
            print("Kết quả extract_features:")
            print(result)
        except Exception as exc:
            print(f"Lỗi khi chạy extract_features: {exc}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

