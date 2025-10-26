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
Phân tích cuộc gọi sales dựa trên transcript và acoustic features, sau đó đánh giá kỹ năng giao tiếp theo các tiêu chí đánh giá 
và tính điểm tổng theo công thức quy định.

# TIÊU CHÍ ĐÁNH GIÁ 

## TIÊU CHÍ 1 : CHÀO/XƯNG DANH
### TIÊU CHUẨN ĐẠT
-Có xưng danh trong 1,2 segment đầu tiên
### TIÊU CHUẨN KHÔNG ĐẠT 
-Không xưng danh
-Xưng danh nhưng khách hàng không nghe được và hỏi lại

## TIÊU CHÍ 2 : KỸ NĂNG NÓI
### TIÊU CHUẨN ĐẠT 
-Giọng nói rõ ràng, âm lượng và cường độ vừa phải (Tốc độ nói < 220 SPM nếu có vài đoạn có SPM lớn hơn thì hãy DỰA VÀO NGỮ CẢNH CHỨ ĐỪNG VỘI ĐÁNH GIÁ)
-Giọng nói có điểm nhấn (Dựa vào pitch_hz,silence_ratio và nên đưa ra dẫn chứng trong phần giải thích)
-Có sự nhấn nhá trong giao tiếp
### TIÊU CHUẨN KHÔNG ĐẠT
-Nói quá nhanh khiến khách hàng NGHE KHÔNG RÕ VÀ YÊU CẦU NHẮC LẠI
-Cách diễn đạt không trôi chảy, ngập ngừng nhiều,NÓI KHÔNG LƯU LOÁT
-GIỌNG NÓI ĐỀU ĐỀU,KHÔNG TẠO ĐIỂM NHẤN (Dựa vào pitch_hz,silence_ratio)
-Nói quá nhỏ khiến khác không nghe rõ và yêu cầu nhắc lại (Ví dụ : chị nói nhỏ quá không nghe rõ gì))
-Lỗi về sự trôi chảy (Phân biệt rõ 2 loại):
    1. **Ngập ngừng/Tìm từ:** Diễn đạt không trôi chảy, lặp lại từ, ngập ngừng nhiều với các từ đệm (ví dụ: "ờm", "à", "uh") hoặc các khoảng lặng dài bất thường để suy nghĩ.
    2. **Hụt hơi/Câu dài:** Giao tiếp bị ngắt quãng, gãy vụn. Dấu hiệu là sales nói một câu quá dài, sau đó bị hụt hơi và phải **ngắt nghỉ đột ngột ở những vị trí không phù hợp** (ví dụ: đang nói giữa một cụm danh từ, động từ) để lấy hơi. Điều này khiến câu nói bị cắt ngang một cách thiếu chuyên nghiệp.
## TIÊU CHÍ 3 : KĨ NĂNG NGHE,TRẤN AN
### TIÊU CHUẨN ĐẠT
-Tập trung thể hiện sự đồng cảm,lắng nghe những thông tin khách hàng chia sẻ ( tập trung vào text)
-Vấn an, cảm thông với những khách hàng đang chưa hài lòng
### TIÊU CHUẨN KHÔNG ĐẠT
-Khách hàng chia sẻ nhưng sale không thể hiện sự đồng cảm cùng,thông tin chia sẻ bị bỏ quên,không hào hứng tham gia
-Các vấn đề lỗi và tạo sự trải nghiệm chưa hài lòng từ khách hàng,sale chưa thể hiện sự trấn an

## TIÊU CHÍ 4 : THÁI ĐỘ GIAO TIẾP 
### TIÊU CHUẨN ĐẠT
-Ngôn ngữ giao tiếp chuẩn mực,thể hiện sự tôn trọng với khách hàng
-Giải quyết triệt để vấn đề của khách hàng đứng trên quan điểm người sử dụng dịch vụ
### TIÊU CHUẨN KHÔNG ĐẠT
- Có thái độ,ngữ điệu trong cuộc gọi không vui vẻ nhiệt tình
-Ngôn từ thiếu chuẩn mực,chưa thể hiện sự tôn trọng với khách hàng 


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
# YÊU CẦU
Hãy nghĩ từng bước trước khi đưa ra đánh giá từng tiêu chí
# OUTPUT FORMAT
```json
{{
  "chao_xung_danh": <int: 0/1>,
  "ky_nang_noi": <int: 0/1>,
  "ky_nang_nghe": <int: 0/1>,
  "thai_do": <int: 0/1>,
  "muc_loi": <string: "Không"|"M1"|"M2"|"M3">,
  "ly_do": <string: giải thích kĩ thành các gạch đầu dòng , trích dẫn rõ nội dung segment ứng với các tiêu chí tương ứng >
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
            temperature=0,
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