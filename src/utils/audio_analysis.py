import numpy as np
import librosa
from typing import List, Dict
from .dialogue_utils import call_dialogue_api
from .utils import create_task_id
from io import BytesIO

# Ngưỡng để xác định một segment có thể bị lỗi từ API
MIN_DURATION_FOR_VALID_SEGMENT = 0.25
MAX_WORDS_IN_SHORT_SEGMENT = 3


class AudioSegment:
    """Đại diện cho một phân đoạn âm thanh trong cuộc hội thoại"""
    
    def __init__(self, segment_data: Dict, sales_speaker_id: str):
        self.start_time = float(segment_data.get('start', 0.0))
        self.end_time = float(segment_data.get('end', self.start_time))
        self.original_speaker_id = segment_data.get('speaker', 'unknown')
        self.speaker_label = 'Sales' if self.original_speaker_id == sales_speaker_id else 'Customer'
        self.text = segment_data.get('text', '')
        self.duration = self.end_time - self.start_time
        self.word_count = len(self.text.split()) if self.text else 0
        
    def is_corrupted(self) -> bool:
        """Kiểm tra segment có bị lỗi từ API hay không"""
        return (self.duration < MIN_DURATION_FOR_VALID_SEGMENT and 
                self.word_count > MAX_WORDS_IN_SHORT_SEGMENT)


class AcousticAnalyzer:
    """Phân tích các đặc điểm acoustic của segment"""
    
    def __init__(self, audio_data: np.ndarray, sample_rate: int, non_silent_intervals: np.ndarray):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.non_silent_intervals = non_silent_intervals
        
    def analyze_segment(self, segment: AudioSegment) -> Dict:
        """Phân tích acoustic features cho một segment"""
        if segment.is_corrupted():
            return {
                'speed_wpm': 0.0,
                'volume_db': 0.0,
                'pitch_hz': 0.0,
                'silence_ratio': 0.0
            }
        
        speed_wpm = self._calculate_speed(segment)
        volume_db = self._calculate_volume(segment)
        pitch_hz = self._calculate_pitch(segment)
        silence_ratio = self._calculate_silence_ratio(segment)
        
        return {
            'speed_wpm': float(speed_wpm),
            'volume_db': float(volume_db),
            'pitch_hz': float(pitch_hz),
            'silence_ratio': float(silence_ratio)
        }
    
    def _calculate_speed(self, segment: AudioSegment) -> float:
        """Tính tốc độ nói (words per minute)"""
        if segment.duration > 0.2 and segment.word_count > 0:
            return (segment.word_count / segment.duration) * 60
        return 0.0
    
    def _calculate_volume(self, segment: AudioSegment) -> float:
        """Tính âm lượng (dB)"""
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample]
        
        if len(segment_audio) > 0:
            volume_rms = np.sqrt(np.mean(np.square(segment_audio)))
            return 20 * np.log10(volume_rms + 1e-10)
        return 0.0
    
    def _calculate_pitch(self, segment: AudioSegment) -> float:
        """Tính cao độ giọng nói (Hz)"""
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample]
        
        if len(segment_audio) > 2048:
            pitches, magnitudes = librosa.piptrack(y=segment_audio, sr=self.sample_rate)
            valid_pitches = pitches[magnitudes > np.median(magnitudes)]
            return np.mean(valid_pitches) if len(valid_pitches) > 0 else 0.0
        return 0.0
    
    def _calculate_silence_ratio(self, segment: AudioSegment) -> float:
        """Tính tỷ lệ khoảng lặng trong segment"""
        segment_speech_duration = 0.0
        for interval in self.non_silent_intervals:
            interval_start_time = interval[0] / self.sample_rate
            interval_end_time = interval[1] / self.sample_rate
            overlap = max(0, min(segment.end_time, interval_end_time) - 
                         max(segment.start_time, interval_start_time))
            segment_speech_duration += overlap
        
        silence_duration = segment.duration - segment_speech_duration
        return (silence_duration / segment.duration) if segment.duration > 0 else 0.0


class MetadataCalculator:
    """Tính toán metadata của cuộc hội thoại"""
    
    def __init__(self, dialogue_segments: List[Dict], sales_speaker_id: str):
        self.dialogue_segments = dialogue_segments
        self.sales_speaker_id = sales_speaker_id
        
    def calculate(self) -> Dict:
        """Tính toán tất cả metadata"""
        total_duration = self._calculate_total_duration()
        turns = self._calculate_turns()
        ratio_sales = self._calculate_sales_ratio(total_duration)
        
        return {
            'duration': float(total_duration),
            'turns': turns,
            'ratio_sales': float(ratio_sales)
        }
    
    def _calculate_total_duration(self) -> float:
        """Tính tổng thời lượng cuộc gọi"""
        return sum(max(0.0, self._seg_end(seg) - self._seg_start(seg)) 
                  for seg in self.dialogue_segments)
    
    def _calculate_turns(self) -> int:
        """Đếm số lần chuyển người nói"""
        turns = 0
        if len(self.dialogue_segments) > 1:
            for i in range(1, len(self.dialogue_segments)):
                if self.dialogue_segments[i].get('speaker') != self.dialogue_segments[i - 1].get('speaker'):
                    turns += 1
        return turns
    
    def _calculate_sales_ratio(self, total_duration: float) -> float:
        """Tính tỷ lệ thời gian nói của Sales"""
        sales_duration = sum(max(0.0, self._seg_end(seg) - self._seg_start(seg)) 
                           for seg in self.dialogue_segments 
                           if seg.get('speaker') == self.sales_speaker_id)
        return (sales_duration / total_duration) if total_duration > 0 else 0.0
    
    @staticmethod
    def _seg_start(seg: Dict) -> float:
        return float(seg.get('start', 0.0))
    
    @staticmethod
    def _seg_end(seg: Dict) -> float:
        return float(seg.get('end', MetadataCalculator._seg_start(seg)))


class AudioFeatureExtractor:
    """Class chính để trích xuất features từ audio"""
    
    def __init__(self, audio_bytes: bytes):
        self.audio_bytes = audio_bytes
        self.task_id = create_task_id(audio_bytes)
        
    async def extract(self) -> Dict:
        """Trích xuất các đặc điểm acoustic và metadata"""
        dialogue_result = await call_dialogue_api(self.audio_bytes, self.task_id)
        
        if dialogue_result['status'] != 1:
            return {'status': -1, 'message': dialogue_result['message']}
        
        dialogue_segments = dialogue_result.get('dialogue', [])
        if not dialogue_segments:
            return {'status': -1, 'message': 'API không trả về phân đoạn hội thoại nào.'}
        
        # Tự động xác định nhân viên Sales là người nói đầu tiên
        sales_speaker_id = dialogue_segments[0].get('speaker', 'unknown')
        
        # Load audio data
        audio_data, sample_rate = librosa.load(BytesIO(self.audio_bytes), sr=None)
        non_silent_intervals = librosa.effects.split(audio_data, top_db=30)
        
        # Phân tích từng segment
        analyzer = AcousticAnalyzer(audio_data, sample_rate, non_silent_intervals)
        segment_analysis = self._analyze_segments(dialogue_segments, sales_speaker_id, analyzer)
        
        # Tính toán metadata
        metadata_calculator = MetadataCalculator(dialogue_segments, sales_speaker_id)
        metadata = metadata_calculator.calculate()
        
        return {
            'status': 1,
            'task_id': self.task_id,
            'segments': segment_analysis,
            'metadata': metadata,
            'message': 'Features and metadata extracted successfully'
        }
    
    def _analyze_segments(self, dialogue_segments: List[Dict], 
                         sales_speaker_id: str, 
                         analyzer: AcousticAnalyzer) -> List[Dict]:
        """Phân tích tất cả segments"""
        segment_analysis = []
        
        for seg_data in dialogue_segments:
            segment = AudioSegment(seg_data, sales_speaker_id)
            acoustic_features = analyzer.analyze_segment(segment)
            
            segment_analysis.append({
                'speaker': segment.speaker_label,
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'text': segment.text,
                **acoustic_features
            })
        
        return segment_analysis


async def extract_features(audio_bytes: bytes) -> Dict:
    """
    Trích xuất các đặc điểm acoustic và metadata, tự động xác định nhân viên Sales.
    """
    extractor = AudioFeatureExtractor(audio_bytes)
    return await extractor.extract()