import openai
from dotenv import load_dotenv
import os
import json

# Tải các biến từ file .env vào môi trường
load_dotenv()

# Lấy thông tin cấu hình từ biến môi trường
API_KEY = os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

# Khởi tạo client OpenAI với cấu hình tùy chỉnh
if API_KEY and API_BASE_URL:
    client = openai.AsyncOpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL,
    )
else:
    client = None
    print("⚠️ CẢNH BÁO: Thiếu OPENAI_API_KEY hoặc OPENAI_API_BASE trong file .env")

def build_prompt(call_data: dict) -> str:
    """
    Xây dựng prompt chấm điểm nhóm Kỹ năng Giao tiếp - Cuộc gọi Bán hàng.
    Trọng số: 20% = 2.0 điểm
    """
    call_data_str = json.dumps(call_data, indent=2, ensure_ascii=False)

    prompt_template = f"""
# NHIỆM VỤ
Phân tích kỹ năng giao tiếp trong cuộc gọi bán hàng dựa trên dữ liệu âm học và transcript.
Điểm tối đa: 2.0 (20% tổng điểm).

# TIÊU CHÍ ĐÁNH GIÁ & DỮ LIỆU THAM CHIẾU

[
  {{
    "tieu_chi": "1. Chào/Xưng danh",
    "trong_so": 0.1,
    "tieu_chuan_dat": "Xưng danh đầy đủ (tên + công ty) trong 1-2 segment đầu.",
    "tieu_chuan_truot": "Không xưng danh, xưng danh sai/thiếu, .",
    "du_lieu_tham_chieu": "segments[0:2] của Sales: text, 
  }},
  {{
    "tieu_chi": "2. Kỹ năng nói",
    "trong_so": 0.1,
    "tieu_chuan_dat": "Tốc độ nói lý tưởng (speed_spm 120-180), rõ ràng (volume_db > -50dB), trôi chảy (disfluency_count thấp).",
    "tieu_chuan_truot": "Nói quá nhanh (>180) / chậm (<120), nói nhỏ, ngập ngừng, vấp (disfluency_count cao).",
    "du_lieu_tham_chieu": "Các segment của Sales: speed_spm, volume_db, disfluency_count"
  }},
  {{
    "tieu_chi": "3. Kỹ năng nghe & Xử lý",
    "trong_so": 0.4,
    "tieu_chuan_dat": " Tập trung thể hiện sự đồng cảm,lắng nghe những thông tin khách hàng chia sẻ,vấn an cảm thông với khách hàng chưa hài lòng",
    "tieu_chuan_truot": " bỏ qua thông tin/phàn nàn của KH, không có từ trấn an hay vấn an khi khách hàng không hài lòng.",
    "du_lieu_tham_chieu": " text "
  }},
  {{
    "tieu_chi": "4. Thái độ giao tiếp",
    "trong_so": 0.4,
    "tieu_chuan_dat": "Thân thiện, tôn trọng. Ngữ điệu linh hoạt (pitch_stddev > 20Hz), dùng nhiều từ lễ phép (politeness_count > 0).",
    "tieu_chuan_truot": "Cộc lốc, mỉa mai, thiếu lịch sự. Giọng cao bất thường, đều đều (pitch_stddev thấp), không có từ lễ phép (politeness_count = 0).",
    "du_lieu_tham_chieu": "Các segment của Sales: pitch_stddev, politeness_count, text (tìm từ tiêu cực)"
  }}
]
Lưu ý quan trọng:
    speed_spm là Số Tiếng (Syllables) trên phút, đã được lọc từ đệm.
    pitch_stddev là Độ lệch chuẩn của cao độ, đo lường ngữ điệu/cảm xúc.
    politeness_count và disfluency_count là số lượng từ lễ phép (dạ, ạ) và từ ngập ngừng (à, ờ).
    
# CÁCH TÍNH ĐIỂM
1.Đánh giá nhị phân: Với mỗi tiêu chí, gán giá trị 1 (Đạt) hoặc 0 (Trượt) vào các biến: chao_xung_danh, ky_nang_noi, ky_nang_nghe, thai_do.

## QUAN TRỌNG : PHẢI ÁP DỤNG CÔNG THỨC TÍNH ĐIỂM TỔNG KHÔNG ĐƯỢC PHÉP SAI 
diem_tong = ((chao_xung_danh * 0.1) + (ky_nang_noi * 0.1) + (ky_nang_nghe * 0.4) + (thai_do * 0.4)) * 2.0



# ĐỊNH NGHĨA MỨC LỖI
M1: Thực hiện đủ thông tin (chào, xưng danh) nhưng chưa trôi chảy (nhiều disfluency_count) hoặc thiếu nhiệt tình (giọng đều đều, pitch_stddev thấp).
      Nói nhỏ (volume_db thấp) hoặc nói nhanh (speed_spm cao).
      Câu từ thiếu chủ ngữ, vị ngữ, ngôn từ bình dân (phân tích text)
M2: Cao giọng, mỉa mai (phân tích text + pitch_stddev cao), thể hiện sự hiểu biết hơn KH, thiếu trách nhiệm.
      Không thực hiện quy định tiếp nhận cuộc gọi (không chào hỏi/ chào kết thúc khi KH đã chào sales) (phân tích text segments đầu/cuối).
      Cung cấp thông tin không quan tâm đến KH có hiểu hay không (ví dụ: ratio_sales quá cao, nói liên tục).
M3: Khai thác lại thông tin lần 2, kết thúc cuộc gọi vẫn không phát hiện vấn đề của KH (phân tích text).
      Có cử chỉ, thái độ, ngôn ngữ hoặc hành vi không lịch sự, thiếu văn hoá, thiếu tôn trọng KH (ví dụ: politeness_count == 0 và text cộc lốc).

# DỮ LIỆU CUỘC GỌI
```json
{call_data_str}
```

# OUTPUT FORMAT
```json
{{
  "diem_tong": <float: 0-2.0>,
  "chao_xung_danh": <int: 0/1>,
  "ky_nang_noi": <int: 0/1>,
  "ky_nang_nghe": <int: 0/1>,
  "thai_do": <int: 0/1>,
  "muc_loi": <string: "Không"|"M1"|"M2"|"M3">,
  "ly_do": <string: giải thích kĩ thành các gạch đầu dòng>
}}
```
"""
    return prompt_template


async def get_qa_evaluation(call_data: dict) -> dict:
    """
    Gửi prompt đến LLM và nhận kết quả đánh giá QA.
    """
    print(f"DEBUG - API_KEY exists: {bool(API_KEY)}")
    print(f"DEBUG - API_BASE_URL: {API_BASE_URL}")
    print(f"DEBUG - MODEL_NAME: {MODEL_NAME}")
    prompt = build_prompt(call_data)

    try:
        if client is None:
            return {"error": "Thiếu cấu hình OPENAI_API_KEY/OPENAI_API_BASE"}
        if not MODEL_NAME:
            return {"error": "Thiếu MODEL_NAME"}

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia phân tích chất lượng cuộc gọi. Đánh giá chính xác dựa trên dữ liệu âm học và transcript. Trả về JSON theo format đã cho."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        result_content = response.choices[0].message.content.strip()

        # Xử lý markdown block
        if result_content.startswith("```json"):
            result_content = result_content[7:]
        if result_content.endswith("```"):
            result_content = result_content[:-3]
        
        result_content = result_content.strip()

        return json.loads(result_content)

    except json.JSONDecodeError as json_err:
        print(f"Lỗi parse JSON: {json_err}")
        print(f"Nội dung từ model: {result_content}")
        return {
            "error": "Lỗi phân tích JSON từ model",
            "raw_response": result_content
        }
    except Exception as e:
        print(f"Lỗi khi gọi LLM API: {e}")
        return {"error": str(e)}