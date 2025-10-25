import numpy as np
import librosa
<<<<<<< HEAD:src/utils/audio_analysis.py
from typing import List, Dict
from .dialogue_utils import call_dialogue_api
from .utils import create_task_id
=======
import re
from typing import List, Dict , Tuple 
from .dialogue import call_dialogue_api
from src.core.utils import create_task_id
>>>>>>> 2632b50 (Add Gradio interface for CRM compliance checking and call evaluation,, and set up project structure with necessary requirements and tests.):src/audio_processing/analysis.py
from io import BytesIO

# Ngưỡng để xác định một segment có thể bị lỗi từ API
MIN_DURATION_FOR_VALID_SEGMENT = 0.25
MAX_WORDS_IN_SHORT_SEGMENT = 3

async def extract_features(audio_bytes: bytes) -> Dict:
    """
    Trích xuất các đặc điểm acoustic và metadata từ các segment của cuộc gọi.
    """
    task_id = create_task_id(audio_bytes)
    dialogue_result = await call_dialogue_api(audio_bytes, task_id)
    if dialogue_result['status'] != 1:
        return {'status': -1, 'message': dialogue_result['message']}

    dialogue_segments = dialogue_result.get('dialogue', []) # Lấy dữ liệu một cách an toàn
    audio_data, sample_rate = librosa.load(BytesIO(audio_bytes), sr=None)
    non_silent_intervals = librosa.effects.split(audio_data, top_db=30)

    segment_analysis = []
    for seg in dialogue_segments:
        start_time = float(seg.get('start', 0.0))
        end_time = float(seg.get('end', start_time))
        
        speaker = seg.get('speaker', 'unknown')
        text = seg.get('text', '')
        
        duration = end_time - start_time
        word_count = len(text.split()) if text else 0

<<<<<<< HEAD:src/utils/audio_analysis.py
=======
class AcousticAnalyzer:
    """Phân tích các đặc điểm acoustic của segment"""
    FILLER_WORDS = {
    'à', 'ạ', 'dạ', 'vâng', 'ừ', 'ừm', 'ờ', 'ơi', 'ấy', 'nhá', 'nha',
    'hả', 'hử', 'ư', 'ê', 'ơ', 'chứ', 'thì', 'là', 'kiểu', 'dạng',
    'đấy', 'nhỉ', 'nhé', 'vậy', 'nên', 'rồi', 'cái', 'ấy là', 'với',
    'mình', 'bên', 'em', 'chị', 'anh', 'luôn', 'luôn ạ', 'dạ vâng', 'vầng'
}
    
    def __init__(self, audio_data: np.ndarray, sample_rate: int, non_silent_intervals: List[Tuple[int, int]]):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.non_silent_intervals = non_silent_intervals
>>>>>>> 2632b50 (Add Gradio interface for CRM compliance checking and call evaluation,, and set up project structure with necessary requirements and tests.):src/audio_processing/analysis.py
        
        is_corrupted_segment = (duration < MIN_DURATION_FOR_VALID_SEGMENT and word_count > MAX_WORDS_IN_SHORT_SEGMENT)

        if is_corrupted_segment:
            speed_wpm = 0.0
            volume_db = 0.0
            pitch_hz = 0.0
            silence_ratio = 0.0
        else:
            speed_wpm = (word_count / duration) * 60 if duration > 0.2 and word_count > 0 else 0.0

            start_sample = int(start_time * sample_rate)
            end_sample = int(end_time * sample_rate)
            segment_audio = audio_data[start_sample:end_sample]

            if len(segment_audio) > 0:
                volume_rms = np.sqrt(np.mean(np.square(segment_audio)))
                volume_db = 20 * np.log10(volume_rms + 1e-10)
            else:
                volume_db = 0.0

            if len(segment_audio) > 2048:
                pitches, magnitudes = librosa.piptrack(y=segment_audio, sr=sample_rate)
                valid_pitches = pitches[magnitudes > np.median(magnitudes)]
                pitch_hz = np.mean(valid_pitches) if len(valid_pitches) > 0 else 0.0
            else:
                pitch_hz = 0.0

            segment_speech_duration = 0.0
            for interval in non_silent_intervals:
                interval_start_time = interval[0] / sample_rate
                interval_end_time = interval[1] / sample_rate
                overlap = max(0, min(end_time, interval_end_time) - max(start_time, interval_start_time))
                segment_speech_duration += overlap
            
            silence_duration = duration - segment_speech_duration
            silence_ratio = (silence_duration / duration) if duration > 0 else 0.0

        segment_analysis.append({
            'speaker': speaker,
            'start_time': start_time,
            'end_time': end_time,
            'text': text,
            'speed_wpm': float(speed_wpm),
            'volume_db': float(volume_db),
            'pitch_hz': float(pitch_hz),
            'silence_ratio': float(silence_ratio)
        })

    # --- Metadata (giữ nguyên) ---
    def seg_start(seg): return float(seg.get('start', 0.0))
    def seg_end(seg): return float(seg.get('end', seg_start(seg)))
    def seg_speaker(seg): return seg.get('speaker', 'unknown')

    total_duration = sum(max(0.0, seg_end(seg) - seg_start(seg)) for seg in dialogue_segments)
    turns = 0
    if len(dialogue_segments) > 1:
        for i in range(1, len(dialogue_segments)):
            if seg_speaker(dialogue_segments[i]) != seg_speaker(dialogue_segments[i - 1]):
                turns += 1
                
    sales_duration = sum(max(0.0, seg_end(seg) - seg_start(seg)) for seg in dialogue_segments if seg_speaker(seg) == 'Sales') # Bạn có thể cần map '0' hoặc '1' thành 'Sales'
    ratio_sales = (sales_duration / total_duration) if total_duration > 0 else 0.0

    metadata = {
        'duration': float(total_duration),
        'turns': turns,
        'ratio_sales': float(ratio_sales)
    }

    return {
        'status': 1,
        'task_id': task_id,
        'segments': segment_analysis,
        'metadata': metadata,
        'message': 'Features and metadata extracted successfully'
    }