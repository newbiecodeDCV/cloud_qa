import numpy as np
import librosa
import re  
from typing import List, Dict, Tuple
from io import BytesIO

# ==================== CHUẨN HÓA THANG ĐO ====================

class VietnameseStandards:
    """Chuẩn hóa các ngưỡng cho tiếng Việt dựa trên nghiên cứu thực tế"""
    
    # Tốc độ nói (Syllables Per Minute)
    SPEED_SPM = {
        'very_slow': (0, 100),      # Quá chậm
        'slow': (100, 120),          # Chậm
        'normal': (120, 180),        # Bình thường (lý tưởng)
        'fast': (180, 220),          # Nhanh
        'very_fast': (220, 999)      # Quá nhanh
    }
    
    # Âm lượng (dB) - tương đối so với RMS
    VOLUME_DB = {
        'too_quiet': (-999, -50),    # Quá nhỏ, KH không nghe rõ
        'quiet': (-50, -35),         # Hơi nhỏ
        'normal': (-35, -20),        # Bình thường (lý tưởng)
        'loud': (-20, -10),          # Hơi to
        'too_loud': (-10, 999)       # Quá to
    }
    
    # Cao độ giọng nói (Hz) - Giọng người Việt
    PITCH_HZ = {
        'very_low': (0, 120),        # Quá thấp (không tự nhiên)
        'low': (120, 160),           # Thấp (nam giới)
        'normal_male': (160, 200),   # Nam bình thường
        'normal_female': (200, 280), # Nữ bình thường
        'high': (280, 350),          # Cao
        'very_high': (350, 999)      # Quá cao (căng thẳng, giận dữ)
    }
    
    # Độ dao động cao độ (Hz) - Đo ngữ điệu/cảm xúc
    PITCH_STDDEV = {
        'monotone': (0, 15),         # Giọng đều đều (không nhiệt tình)
        'low_variation': (15, 25),   # Ít dao động
        'normal': (25, 40),          # Bình thường (lý tưởng)
        'high_variation': (40, 60),  # Nhiều dao động (nhiệt tình)
        'excessive': (60, 999)       # Quá dao động (mất kiểm soát)
    }
    
    # Tỷ lệ im lặng
    SILENCE_RATIO = {
        'continuous': (0, 0.1),      # Nói liên tục (không cho KH nói)
        'low': (0.1, 0.2),           # Ít khoảng lặng
        'normal': (0.2, 0.4),        # Bình thường
        'high': (0.4, 0.6),          # Nhiều khoảng lặng (do dự)
        'excessive': (0.6, 1.0)      # Quá nhiều (mất tự tin)
    }
    
    @staticmethod
    def categorize(value: float, thresholds: Dict[str, Tuple[float, float]]) -> str:
        """
        Phân loại giá trị vào các ngưỡng đã định nghĩa.
        
        Tham số:
        - value: Giá trị cần phân loại (float)
        - thresholds: Dict chứa các ngưỡng với format {category: (min_val, max_val)}
        
        Trả về:
        - str: Tên category phù hợp hoặc 'unknown' nếu không khớp ngưỡng nào
        
        Ví dụ:
        >>> VietnameseStandards.categorize(150, VietnameseStandards.SPEED_SPM)
        'normal'
        """
        for category, (min_val, max_val) in thresholds.items():
            if min_val <= value < max_val:
                return category
        return 'unknown'


# ==================== ENHANCED ACOUSTIC ANALYZER ====================

class EnhancedAcousticAnalyzer:
    """Phân tích acoustic với đầy đủ features theo tiêu chí"""
    
    # Từ ngập ngừng (disfluency)
    DISFLUENCY_WORDS = {
        'à', 'ờ', 'ử', 'ửm', 'hửm', 'ơ', 'ờm', 'hơm',
        'này', 'nọ', 'kia',  # Từ chỉ định không rõ ràng
    }
    
    # Từ lễ phép (politeness)
    POLITENESS_WORDS = {
        'dạ', 'ạ', 'vâng', 'thưa', 'kính', 'mong', 
        'xin', 'cảm ơn', 'cám ơn', 'thank', 'thanks',
        'xin lỗi', 'sorry', 'pardon'
    }
    
    # Từ tiêu cực (negative sentiment)
    NEGATIVE_WORDS = {
        'tệ', 'kém', 'dở', 'chán', 'tức', 'bực', 'mất',
        'không', 'chưa', 'sai', 'lỗi', 'hỏng', 'phiền'
    }
    
    # Từ tích cực (positive sentiment)
    POSITIVE_WORDS = {
        'tốt', 'hay', 'được', 'ok', 'oke', 'đồng ý',
        'vui', 'hài lòng', 'cảm ơn', 'tuyệt', 'tốt lắm'
    }
    
    # Từ đệm (filler) - đã có trong code cũ
    FILLER_WORDS = {
        'à', 'ờ', 'ử', 'ửm', 'hửm',
        'dạ', 'ạ', 'vâng', 'thưa',
        'thì', 'là', 'mà', 'rằng'
    }
    
    def __init__(self, audio_data: np.ndarray, sample_rate: int, 
                 non_silent_intervals: np.ndarray, segments: List):
        """
        Khởi tạo bộ phân tích acoustic nâng cao.
        
        Tham số:
        - audio_data: Dữ liệu âm thanh dạng numpy array
        - sample_rate: Tần số lấy mẫu (Hz)
        - non_silent_intervals: Các khoảng không im lặng dạng [[start, end], ...]
        - segments: Danh sách các segment đã được phân đoạn với thông tin speaker, text, thời gian
        """
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.non_silent_intervals = non_silent_intervals
        self.segments = segments 
        
    def analyze_segment(self, segment, segment_index: int) -> Dict:
        """
        Phân tích toàn bộ features acoustic cho một segment.
        
        Tham số:
        - segment: Object segment chứa thông tin text, start_time, end_time, speaker_label
        - segment_index: Vị trí của segment trong danh sách (để tính interruption)
        
        Trả về:
        - Dict chứa:
          * Raw values: speed_spm, volume_db, pitch_hz, pitch_stddev, silence_ratio
          * Counts: disfluency_count, politeness_count, negative_count, positive_count, is_interrupted
          * Categories: speed_category, volume_category, pitch_category, pitch_stddev_category
          * Issues: has_issues (danh sách các vấn đề phát hiện)
        
        Ví dụ:
        >>> result = analyzer.analyze_segment(segment, 0)
        >>> print(result['speed_category'])
        'normal'
        """
        
        speed_spm = self._calculate_spm(segment)
        volume_db = self._calculate_volume(segment)
        pitch_hz = self._calculate_pitch(segment)
        silence_ratio = self._calculate_silence_ratio(segment)
        
   
        pitch_stddev = self._calculate_pitch_stddev(segment)
        disfluency_count = self._count_disfluency(segment)
        politeness_count = self._count_politeness(segment)
        
 
        negative_count = self._count_negative_words(segment)
        positive_count = self._count_positive_words(segment)
        is_interrupted = self._detect_interruption(segment_index)
        
   
        speed_category = VietnameseStandards.categorize(
            speed_spm, VietnameseStandards.SPEED_SPM
        )
        volume_category = VietnameseStandards.categorize(
            volume_db, VietnameseStandards.VOLUME_DB
        )
        pitch_category = VietnameseStandards.categorize(
            pitch_hz, VietnameseStandards.PITCH_HZ
        )
        pitch_stddev_category = VietnameseStandards.categorize(
            pitch_stddev, VietnameseStandards.PITCH_STDDEV
        )
        
        return {
          
            'speed_spm': float(speed_spm),
            'volume_db': float(volume_db),
            'pitch_hz': float(pitch_hz),
            'pitch_stddev': float(pitch_stddev),
            'silence_ratio': float(silence_ratio),
            
          
            'disfluency_count': disfluency_count,
            'politeness_count': politeness_count,
            'negative_count': negative_count,
            'positive_count': positive_count,
            'is_interrupted': is_interrupted,
            
          
            'speed_category': speed_category,
            'volume_category': volume_category,
            'pitch_category': pitch_category,
            'pitch_stddev_category': pitch_stddev_category,
            
       
            'has_issues': self._flag_issues(
                speed_category, volume_category, pitch_stddev_category,
                disfluency_count, politeness_count
            )
        }
    
    def _calculate_spm(self, segment) -> float:
        """
        Tính tốc độ nói (Syllables Per Minute) cho segment.
        
        Tham số:
        - segment: Object segment chứa text và duration
        
        Trả về:
        - float: Số âm tiết có nghĩa trên phút (loại bỏ filler words)
        
        Lưu ý:
        - Chỉ tính âm tiết có nghĩa, bỏ qua từ đệm (à, ờ, thì, là...)
        - Trả về 0.0 nếu segment quá ngắn (<0.2s) hoặc không có text
        """
        if segment.duration <= 0.2:
            return 0.0
        text = segment.text
        if not text:
            return 0.0
        
        all_syllables = re.findall(r'\b\w+\b', text.lower())
        content_syllable_count = sum(
            1 for s in all_syllables if s not in self.FILLER_WORDS
        )
        
        if content_syllable_count > 0:
            return (content_syllable_count / segment.duration) * 60
        return 0.0
    
    def _calculate_volume(self, segment) -> float:
        """
        Tính âm lượng (volume) của segment theo dB.
        
        Tham số:
        - segment: Object segment chứa start_time, end_time
        
        Trả về:
        - float: Âm lượng RMS chuyển đổi sang dB (20*log10(RMS))
        - Trả về -100.0 nếu không có dữ liệu audio
        
        Lưu ý:
        - Sử dụng RMS (Root Mean Square) để tính âm lượng trung bình
        - Thêm 1e-10 để tránh log(0)
        """
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample]
        
        if len(segment_audio) > 0:
            segment_audio_float = segment_audio.astype(np.float32)
            volume_rms = np.sqrt(np.mean(np.square(segment_audio_float)))
            return 20 * np.log10(volume_rms + 1e-10)
        return -100.0
    
    def _calculate_pitch(self, segment) -> float:
        """
        Tính cao độ giọng nói (pitch) trung bình của segment.
        
        Tham số:
        - segment: Object segment chứa start_time, end_time
        
        Trả về:
        - float: Cao độ trung bình (Hz), 0.0 nếu không xác định được
        
        Lưu ý:
        - Sử dụng librosa.pyin để tìm fundamental frequency (F0)
        - Phạm vi tìm kiếm: C2 (65.4 Hz) đến C7 (2093 Hz)
        - Lọc bỏ các giá trị NaN trước khi tính trung bình
        """
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample].astype(np.float32)
        
        if len(segment_audio) == 0:
            return 0.0
        
        f0, voiced_flag, voiced_prob = librosa.pyin(
            segment_audio,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=self.sample_rate
        )
        
        average_pitch = np.nanmean(f0)
        return 0.0 if np.isnan(average_pitch) else float(average_pitch)
    
    def _calculate_pitch_stddev(self, segment) -> float:
        """
        Tính độ lệch chuẩn của pitch để đo ngữ điệu và cảm xúc.
        
        Tham số:
        - segment: Object segment chứa start_time, end_time
        
        Trả về:
        - float: Độ lệch chuẩn của pitch (Hz)
        - Cao = giọng linh hoạt, nhiệt tình, có ngữ điệu
        - Thấp = giọng đều đều, thiếu cảm xúc, đơn điệu
        
        Lưu ý:
        - Cần ít nhất 2 giá trị pitch hợp lệ để tính stddev
        - Trả về 0.0 nếu không đủ dữ liệu
        """
        start_sample = int(segment.start_time * self.sample_rate)
        end_sample = int(segment.end_time * self.sample_rate)
        segment_audio = self.audio_data[start_sample:end_sample].astype(np.float32)
        
        if len(segment_audio) == 0:
            return 0.0
        
        f0, voiced_flag, voiced_prob = librosa.pyin(
            segment_audio,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=self.sample_rate
        )
        
        # Lọc bỏ NaN
        f0_valid = f0[~np.isnan(f0)]
        
        if len(f0_valid) < 2:
            return 0.0
        
        stddev = np.std(f0_valid)
        return float(stddev)
    
    def _calculate_silence_ratio(self, segment) -> float:
        """
        Tính tỷ lệ im lặng trong segment.
        
        Tham số:
        - segment: Object segment chứa start_time, end_time, duration
        
        Trả về:
        - float: Tỷ lệ im lặng (0.0-1.0)
        - 0.0 = không có im lặng (nói liên tục)
        - 1.0 = toàn bộ là im lặng
        

        """
        if segment.duration == 0:
            return 0.0
        
        segment_speech_duration = 0.0
        for interval in self.non_silent_intervals:
            interval_start_time = interval[0] / self.sample_rate
            interval_end_time = interval[1] / self.sample_rate
            overlap = max(0, min(segment.end_time, interval_end_time) - 
                         max(segment.start_time, interval_start_time))
            segment_speech_duration += overlap
        
        segment_speech_duration = min(segment.duration, segment_speech_duration)
        silence_duration = segment.duration - segment_speech_duration
        return (silence_duration / segment.duration)
    
    def _count_disfluency(self, segment) -> int:
        """
        Đếm số từ ngập ngừng trong segment.
        
        Tham số:
        - segment: Object segment chứa text
        
        Trả về:
        - int: Số lượng từ ngập ngừng (à, ờ, ửm, hửm...)
        
        Lưu ý:
        - Nhiều từ ngập ngừng = nói không trôi chảy, thiếu tự tin
        - Chỉ đếm các từ đơn lẻ, không đếm cụm từ
        """
        if not segment.text:
            return 0
        
        words = re.findall(r'\b\w+\b', segment.text.lower())
        return sum(1 for word in words if word in self.DISFLUENCY_WORDS)
    
    def _count_politeness(self, segment) -> int:
        """
        Đếm số từ lễ phép trong segment.
        
        Tham số:
        - segment: Object segment chứa text
        
        Trả về:
        - int: Số lượng từ lễ phép (dạ, ạ, vâng, cảm ơn, xin lỗi...)
        
        Lưu ý:
        - Nhiều từ lễ phép = thái độ tốt, tôn trọng khách hàng
        - Đếm cả từ đơn và cụm từ (vd: "cảm ơn", "xin lỗi")
        """
        if not segment.text:
            return 0
        
        text_lower = segment.text.lower()
        count = 0
        
        for word in self.POLITENESS_WORDS:
            # Đếm cả cụm từ (vd: "cảm ơn", "xin lỗi")
            count += text_lower.count(word)
        
        return count
    
    def _count_negative_words(self, segment) -> int:
        """
        Đếm số từ tiêu cực trong segment.
        
        Tham số:
        - segment: Object segment chứa text
        
        Trả về:
        - int: Số lượng từ tiêu cực (tệ, kém, dở, chán, tức...)
        
        Lưu ý:
        - Dùng để đánh giá tông giọng và thái độ
        - Chỉ đếm từ đơn lẻ, không đếm cụm từ
        """
        if not segment.text:
            return 0
        words = re.findall(r'\b\w+\b', segment.text.lower())
        return sum(1 for word in words if word in self.NEGATIVE_WORDS)
    
    def _count_positive_words(self, segment) -> int:
        """
        Đếm số từ tích cực trong segment.
        
        Tham số:
        - segment: Object segment chứa text
        
        Trả về:
        - int: Số lượng từ tích cực (tốt, hay, được, vui, hài lòng...)
        
        Lưu ý:
        - Dùng để đánh giá tông giọng và thái độ
        - Chỉ đếm từ đơn lẻ, không đếm cụm từ
        """
        if not segment.text:
            return 0
        words = re.findall(r'\b\w+\b', segment.text.lower())
        return sum(1 for word in words if word in self.POSITIVE_WORDS)
    
    def _detect_interruption(self, segment_index: int) -> bool:
        """
        Phát hiện ngắt lời trong cuộc gọi.
        
        Tham số:
        - segment_index: Vị trí của segment hiện tại trong danh sách
        
        Trả về:
        - bool: True nếu phát hiện ngắt lời, False nếu không
        
        Lưu ý:
        - Chỉ kiểm tra khi Sales ngắt lời Customer (không ngược lại)
        - Ngưỡng: gap < 0.3 giây giữa segment trước và hiện tại
        - Cần có ít nhất 2 segment để so sánh
        """
        if segment_index == 0 or segment_index >= len(self.segments):
            return False
        
        current = self.segments[segment_index]
        previous = self.segments[segment_index - 1]
        
        # Chỉ tính khi Sales ngắt lời Customer
        if (current.speaker_label == 'Sales' and 
            previous.speaker_label == 'Customer'):
            gap = current.start_time - previous.end_time
            # Nếu gap < 0.3s = có thể là ngắt lời
            return gap < 0.3
        
        return False
    
    def _flag_issues(self, speed_cat: str, volume_cat: str, 
                     pitch_stddev_cat: str, disfluency: int, 
                     politeness: int) -> List[str]:
        """
        Đánh dấu các vấn đề phát hiện để LLM dễ nhận biết.
        
        Tham số:
        - speed_cat: Category tốc độ nói ('very_fast', 'normal', ...)
        - volume_cat: Category âm lượng ('too_quiet', 'normal', ...)
        - pitch_stddev_cat: Category độ dao động cao độ ('monotone', 'normal', ...)
        - disfluency: Số từ ngập ngừng
        - politeness: Số từ lễ phép
        
        Trả về:
        - List[str]: Danh sách các vấn đề phát hiện
        
        Các vấn đề có thể phát hiện:
        - 'nói_quá_nhanh', 'nói_quá_chậm'
        - 'nói_quá_nhỏ'
        - 'giọng_đều_đều_thiếu_nhiệt_tình'
        - 'nhiều_từ_ngập_ngừng'
        - 'không_có_từ_lễ_phép'
        """
        issues = []
        
        if speed_cat in ['very_fast', 'fast']:
            issues.append('nói_quá_nhanh')
        elif speed_cat in ['very_slow', 'slow']:
            issues.append('nói_quá_chậm')
        
        if volume_cat in ['too_quiet', 'quiet']:
            issues.append('nói_quá_nhỏ')
        
        if pitch_stddev_cat == 'monotone':
            issues.append('giọng_đều_đều_thiếu_nhiệt_tình')
        
        if disfluency > 3:  # Ngưỡng: >3 từ ngập ngừng = vấn đề
            issues.append('nhiều_từ_ngập_ngừng')
        
        if politeness == 0:
            issues.append('không_có_từ_lễ_phép')
        
        return issues


# ==================== CHUẨN HÓA DỮ LIỆU CHO LLM ====================

class LLMDataFormatter:
    """
    Format dữ liệu theo cách LLM dễ hiểu:
    - Có cả raw values VÀ giải thích
    - Highlight các vấn đề
    - Cung cấp context
    """
    
    @staticmethod
    def format_for_llm(segments: List[Dict], metadata: Dict) -> Dict:
        """
        Chuyển đổi dữ liệu kỹ thuật thành format dễ hiểu cho LLM.
        
        Tham số:
        - segments: Danh sách các segment đã được phân tích
        - metadata: Thông tin tổng quan về cuộc gọi
        
        Trả về:
        - Dict chứa:
          * metadata: Thông tin tổng quan
          * sales_statistics: Thống kê trung bình của Sales
          * greeting_analysis: Phân tích phần chào hỏi
          * closing_analysis: Phân tích phần kết thúc
          * issues_summary: Tổng hợp các vấn đề
          * all_segments: Tất cả segments (để LLM xem chi tiết)
          * standards_reference: Ngưỡng chuẩn để so sánh
        
        Lưu ý:
        - Tách riêng segments của Sales và Customer
        - Cung cấp context và ngưỡng chuẩn để LLM đánh giá
        """
        
        # Tách segments theo speaker
        sales_segments = [s for s in segments if s['speaker'] == 'Sales']
        customer_segments = [s for s in segments if s['speaker'] == 'Customer']
        
        # Tính thống kê tổng hợp cho Sales
        sales_stats = LLMDataFormatter._calculate_speaker_stats(sales_segments)
        
        # Phân tích các segment đầu (chào hỏi)
        greeting_analysis = LLMDataFormatter._analyze_greeting(sales_segments[:2])
        
        # Phân tích các segment cuối (kết thúc)
        closing_analysis = LLMDataFormatter._analyze_closing(sales_segments[-2:])
        
        # Tổng hợp vấn đề
        issues_summary = LLMDataFormatter._summarize_issues(sales_segments)
        
        return {
            'metadata': metadata,
            'sales_statistics': sales_stats,
            'greeting_analysis': greeting_analysis,
            'closing_analysis': closing_analysis,
            'issues_summary': issues_summary,
            'all_segments': segments,  # Giữ nguyên để LLM có thể xem chi tiết
            
            # Context để LLM hiểu
            'standards_reference': {
                'speed_spm_ideal': '120-180 SPM',
                'volume_db_ideal': '-35 đến -20 dB',
                'pitch_stddev_ideal': '>25 Hz (linh hoạt)',
                'disfluency_acceptable': '≤3 từ/segment',
                'politeness_minimum': '≥1 từ/segment'
            }
        }
    
    @staticmethod
    def _calculate_speaker_stats(segments: List[Dict]) -> Dict:
        """
        Tính thống kê trung bình cho một speaker.
        
        Tham số:
        - segments: Danh sách segments của một speaker
        
        Trả về:
        - Dict chứa các giá trị trung bình:
          * avg_speed_spm: Tốc độ nói trung bình
          * avg_volume_db: Âm lượng trung bình
          * avg_pitch_hz: Cao độ trung bình
          * avg_pitch_stddev: Độ dao động cao độ trung bình
          * total_disfluency_count: Tổng từ ngập ngừng
          * total_politeness_count: Tổng từ lễ phép
          * segment_count: Số lượng segments
        
        Lưu ý:
        - Trả về Dict rỗng nếu không có segments
        - Làm tròn các giá trị số đến 1 chữ số thập phân
        """
        if not segments:
            return {}
        
        total_speed = sum(s.get('speed_spm', 0) for s in segments)
        total_volume = sum(s.get('volume_db', -100) for s in segments)
        total_pitch = sum(s.get('pitch_hz', 0) for s in segments)
        total_pitch_stddev = sum(s.get('pitch_stddev', 0) for s in segments)
        
        total_disfluency = sum(s.get('disfluency_count', 0) for s in segments)
        total_politeness = sum(s.get('politeness_count', 0) for s in segments)
        
        n = len(segments)
                                                                                                                                                                                                                                                                                                                                                                                                
        return {
            'avg_speed_spm': round(total_speed / n, 1),
            'avg_volume_db': round(total_volume / n, 1),
            'avg_pitch_hz': round(total_pitch / n, 1),
            'avg_pitch_stddev': round(total_pitch_stddev / n, 1),
            'total_disfluency_count': total_disfluency,
            'total_politeness_count': total_politeness,
            'segment_count': n
        }
    
    @staticmethod
    def _analyze_greeting(first_segments: List[Dict]) -> Dict:
        """
        Phân tích phần chào hỏi và xưng danh trong các segment đầu.
        
        Tham số:
        - first_segments: 2 segment đầu tiên của Sales
        
        Trả về:
        - Dict chứa:
          * has_greeting: Có chào hỏi không (xin chào, chào, dạ)
          * has_name: Có xưng danh không (em là, em tên, tôi là)
          * has_company: Có giới thiệu công ty không (                                                                                                                                                                                                                                                                               công ty, bên)
          * full_greeting: Có đầy đủ chào + tên + công ty không
          * text_preview: 200 ký tự đầu để xem nội dung
        
        Lưu ý:
        - Chỉ kiểm tra 2 segment đầu tiên
        - Trả về {'has_greeting': False} nếu không có segments
        """
        if not first_segments:
            return {'has_greeting': False}
        
        first_text = ' '.join([s.get('text', '') for s in first_segments]).lower()
        
        # Kiểm tra xưng danh
        has_name = any(word in first_text for word in ['em là', 'em tên', 'tôi là'])
        has_company = any(word in first_text for word in ['viettel', 'công ty', 'bên'])
        has_greeting = any(word in first_text for word in ['xin chào', 'chào', 'dạ'])
        
        return {
            'has_greeting': has_greeting,
            'has_name': has_name,
            'has_company': has_company,
            'full_greeting': has_greeting and has_name and has_company,
            'text_preview': first_text[:200]  # 200 ký tự đầu
        }
    
    @staticmethod
    def _analyze_closing(last_segments: List[Dict]) -> Dict:
        """
        Phân tích phần kết thúc cuộc gọi.
        
        Tham số:
        - last_segments: 2 segment cuối cùng của Sales
        
        Trả về:
        - Dict chứa:
          * has_thanks: Có cảm ơn không (cảm ơn, cám ơn, thank)
          * has_goodbye: Có chào tạm biệt không (tạm biệt, chào, bye)
          * proper_closing: Có kết thúc lịch sự không (cảm ơn HOẶC tạm biệt)
          * text_preview: 200 ký tự cuối để xem nội dung
        
        Lưu ý:
        - Chỉ kiểm tra 2 segment cuối cùng
        - Trả về {'has_closing': False} nếu không có segments
        """
        if not last_segments:
            return {'has_closing': False}
        
        last_text = ' '.join([s.get('text', '') for s in last_segments]).lower()
        
        has_thanks = any(word in last_text for word in ['cảm ơn', 'cám ơn', 'thank'])
        has_goodbye = any(word in last_text for word in ['tạm biệt', 'chào', 'bye'])
        
        return {
            'has_thanks': has_thanks,
            'has_goodbye': has_goodbye,
            'proper_closing': has_thanks or has_goodbye,
            'text_preview': last_text[:200]
        }
    
    @staticmethod
    def _summarize_issues(segments: List[Dict]) -> Dict:
        """
        Tổng hợp các vấn đề phát hiện trong tất cả segments.
        
        Tham số:
        - segments: Danh sách tất cả segments đã phân tích
        
        Trả về:
        - Dict chứa:
          * total_segments_with_issues: Số segments có vấn đề
          * issue_breakdown: Dict đếm tần suất từng loại vấn đề
          * has_critical_issues: Có vấn đề nghiêm trọng không
        
        Các vấn đề nghiêm trọng:
        - 'không_có_từ_lễ_phép'
        - 'nói_quá_nhỏ'
        - 'giọng_đều_đều_thiếu_nhiệt_tình'
        
        Lưu ý:
        - Thu thập tất cả issues từ field 'has_issues' của mỗi segment
        - Đếm tần suất xuất hiện của từng loại vấn đề
        """
        all_issues = []
        for s in segments:
            if 'has_issues' in s and s['has_issues']:
                all_issues.extend(s['has_issues'])
        
        # Đếm tần suất từng loại vấn đề
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        return {
            'total_segments_with_issues': len([s for s in segments if s.get('has_issues')]),
            'issue_breakdown': issue_counts,
            'has_critical_issues': any(
                issue in issue_counts for issue in [
                    'không_có_từ_lễ_phép',
                    'nói_quá_nhỏ',
                    'giọng_đều_đều_thiếu_nhiệt_tình'
                ]
            )
        }