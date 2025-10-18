import numpy as np
import librosa
import re  
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
        self.original_speaker_id = str(segment_data.get('speaker', 'unknown'))
        self.speaker_label = 'Sales' if self.original_speaker_id == str(sales_speaker_id) else 'Customer'
        self.text = segment_data.get('text', '')
        self.duration = self.end_time - self.start_time
        # word_count này vẫn hữu ích cho hàm is_corrupted, nên ta giữ nguyên
        self.word_count = len(self.text.split()) if self.text else 0
        
    def is_corrupted(self) -> bool:
        """Kiểm tra segment có bị lỗi từ API hay không"""
        return (self.duration < MIN_DURATION_FOR_VALID_SEGMENT and 
                self.word_count > MAX_WORDS_IN_SHORT_SEGMENT)


class AcousticAnalyzer:
    """Phân tích các đặc điểm acoustic của segment"""
    
    # THÊM MỚI: Danh sách các từ đệm, ngập ngừng, lễ phép... 
    # cần lọc bỏ khi tính tốc độ nội dung
    FILLER_WORDS = {
        'à', 'ờ', 'ừ', 'ừm', 'hừm',  # Từ ngập ngừng
        'dạ', 'ạ', 'vâng', 'thưa',   # Từ lễ phép (làm tăng số "tiếng" nhưng không phải nội dung)
        'thì', 'là', 'mà', 'rằng'      # Từ đệm phổ biến
    }
    
    def __init__(self, audio_data: np.ndarray, sample_rate: int, non_silent_intervals: np.ndarray):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.non_silent_intervals = non_silent_intervals
        
    def analyze_segment(self, segment: AudioSegment) -> Dict:
        """Phân tích acoustic features cho một segment"""
        if segment.is_corrupted():
            return {
                'speed_spm': 0.0,  # <-- TỐI ƯU: Đổi tên key
                'volume_db': 0.0,
                'pitch_hz': 0.0,
                'silence_ratio': 0.0
            }
        
        speed_spm = self._calculate_spm(segment)  # <-- TỐI ƯU: Gọi hàm mới
        volume_db = self._calculate_volume(segment)
        pitch_hz = self._calculate_pitch(segment)  # <-- TỐI ƯU: Dùng hàm đã cập nhật
        silence_ratio = self._calculate_silence_ratio(segment)
        
        return {
            'speed_spm': float(speed_spm),  # <-- TỐI ƯU: Đổi tên key
            'volume_db': float(volume_db),
            'pitch_hz': float(pitch_hz),
            'silence_ratio': float(silence_ratio)
        }
    
    def _calculate_spm(self, segment: AudioSegment) -> float:
        """
        TỐI ƯU: Tính tốc độ nói (Syllables Per Minute - SPM) đã lọc từ đệm.
        Đây là tốc độ truyền tải nội dung thực tế.
        """
        if segment.duration <= 0.2:
            return 0.0

        text = segment.text
        if not text:
            return 0.0

        # 1. Tách "tiếng" (syllables/words) bằng regex
        all_syllables = re.findall(r'\b\w+\b', text.lower())
        
        # 2. Đếm "tiếng" chứa nội dung (lọc bỏ filler words)
        content_syllable_count = 0
        for syllable in all_syllables:
            if syllable not in self.FILLER_WORDS:
                content_syllable_count += 1
                
        # 3. Tính SPM dựa trên số "tiếng" có nội dung
        if content_syllable_count > 0:
            spm = (content_syllable_count / segment.duration) * 60
            return spm
            
        return 0.0
    
    def _calculate_volume(self, segment: AudioSegment) -> float:
        """Tính âm lượng (dB)"""
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample]
        
        if len(segment_audio) > 0:
            segment_audio_float = segment_audio.astype(np.float32)
            volume_rms = np.sqrt(np.mean(np.square(segment_audio_float)))
            return 20 * np.log10(volume_rms + 1e-10)
        return -100.0 
    
    def _calculate_pitch(self, segment: AudioSegment) -> float:
        """
        TỐI ƯU: Tính cao độ giọng nói (Hz) sử dụng thuật toán PYIN.
        Chính xác và ổn định hơn piptrack rất nhiều.
        """
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        # Cần chuyển sang float32 cho librosa.pyin
        segment_audio = self.audio_data[start_sample:end_sample].astype(np.float32)

        if len(segment_audio) == 0:
            return 0.0

        # fmin và fmax là giới hạn hợp lý cho giọng nói của con người
        # frame_length mặc định (2048) là đủ, không cần set cứng
        f0, voiced_flag, voiced_prob = librosa.pyin(
            segment_audio,
            fmin=librosa.note_to_hz('C2'), # ~65 Hz
            fmax=librosa.note_to_hz('C7'), # ~2093 Hz
            sr=self.sample_rate
        )
        

        # np.nanmean sẽ tự động tính trung bình và bỏ qua các giá trị nan
        average_pitch = np.nanmean(f0)

        # Nếu toàn bộ segment là unvoiced hoặc im lặng, f0 sẽ toàn nan
        if np.isnan(average_pitch):
            return 0.0
            
        return float(average_pitch)
    
    def _calculate_silence_ratio(self, segment: AudioSegment) -> float:
        """Tính tỷ lệ khoảng lặng trong segment (Giữ nguyên logic của bạn)"""
        if segment.duration == 0:
            return 0.0 # Tránh chia cho 0

        segment_speech_duration = 0.0
        for interval in self.non_silent_intervals:
            interval_start_time = interval[0] / self.sample_rate
            interval_end_time = interval[1] / self.sample_rate
            overlap = max(0, min(segment.end_time, interval_end_time) - 
                         max(segment.start_time, interval_start_time))
            segment_speech_duration += overlap
        
        # Đảm bảo thời gian nói không lớn hơn thời lượng segment
        segment_speech_duration = min(segment.duration, segment_speech_duration)

        silence_duration = segment.duration - segment_speech_duration
        return (silence_duration / segment.duration)


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
        # Đảm bảo segment cuối cùng được tính
        if not self.dialogue_segments:
            return 0.0
        last_seg = self.dialogue_segments[-1]
        return self._seg_end(last_seg)
    
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
                           if str(seg.get('speaker')) == str(self.sales_speaker_id))
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
    
    def _identify_sales_speaker(self, dialogue_segments: List[Dict]) -> str:
        """Xác định Sales speaker dựa trên tổng thời lượng nói"""
        speaker_durations = {}
        
        for seg in dialogue_segments:
            speaker_id = str(seg.get('speaker', 'unknown'))
            start = float(seg.get('start', 0.0))
            end = float(seg.get('end', start))
            duration = max(0.0, end - start)
            
            if speaker_id not in speaker_durations:
                speaker_durations[speaker_id] = 0.0
            speaker_durations[speaker_id] += duration
        
        # Sales thường nói nhiều hơn → chọn speaker có tổng thời lượng lớn nhất
        if speaker_durations:
            sales_speaker_id = max(speaker_durations, key=speaker_durations.get)
            return sales_speaker_id
        
        # Fallback: người nói đầu tiên
        return str(dialogue_segments[0].get('speaker', 'unknown'))
        
    async def extract(self) -> Dict:
        """Trích xuất các đặc điểm acoustic và metadata"""
        dialogue_result = await call_dialogue_api(self.audio_bytes, self.task_id)
        
        if dialogue_result['status'] != 1:
            return {'status': -1, 'message': dialogue_result['message']}
        
        dialogue_segments = dialogue_result.get('dialogue', [])
        if not dialogue_segments:
            return {'status': -1, 'message': 'API không trả về phân đoạn hội thoại nào.'}
        
        # Tự động xác định Sales dựa trên tổng thời lượng nói
        sales_speaker_id = self._identify_sales_speaker(dialogue_segments)
        self.sales_speaker_id = sales_speaker_id  # Lưu lại để debug
        print(f">>> Sales Speaker ID được xác định: {sales_speaker_id}")
        print(f">>> Tổng số segments: {len(dialogue_segments)}")
        
        # Load audio data
        # TỐI ƯU: Đảm bảo audio data là float
        audio_data, sample_rate = librosa.load(BytesIO(self.audio_bytes), sr=None, dtype=np.float32)
        
        
        # cho audio tổng đài có thể có nhiễu nền
        non_silent_intervals = librosa.effects.split(audio_data, top_db=40) 
        
        
        analyzer = AcousticAnalyzer(audio_data, sample_rate, non_silent_intervals)
        segment_analysis = self._analyze_segments(dialogue_segments, sales_speaker_id, analyzer)
        
      
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
            
            # Debug: In ra để kiểm tra
            # print(f"DEBUG - Original ID: {segment.original_speaker_id}, Sales ID: {sales_speaker_id}, Label: {segment.speaker_label}")
            
            segment_analysis.append({
                'speaker': segment.speaker_label,
                'start_time': segment.start_time,
                'end_time': segment.end_time,
                'text': segment.text,
                **acoustic_features # Tự động unpack {'speed_spm': ..., 'pitch_hz': ...}
            })
        
        return segment_analysis


async def extract_features(audio_bytes: bytes) -> Dict:
    """
    Trích xuất các đặc điểm acoustic và metadata, tự động xác định nhân viên Sales.
    """
    print("=== EXTRACT_FEATURES ĐƯỢC GỌI (OOP VERSION) ===")
    extractor = AudioFeatureExtractor(audio_bytes)
    result = await extractor.extract()
    print(f"=== Sales Speaker ID: {extractor.sales_speaker_id if hasattr(extractor, 'sales_speaker_id') else 'N/A'} ===")
    return result