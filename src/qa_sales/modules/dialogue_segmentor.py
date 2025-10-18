from typing import List, Dict, Any
from src.utils.utils import seconds_to_min_sec
from litellm import completion
from dotenv import load_dotenv
import os
import openai


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("BASE_URL")
print(f"Using OpenAI API key: {api_key}, Base URL: {base_url}")
openai.api_key = api_key
openai.base_url = base_url


class DialogueSegmentor:

    def make_text_dialogue(self, dialogue: List[Dict[str, Any]]) -> str:
        text_dialogue = ""
        for segment in dialogue:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            start = segment.get("start", 0)
            start = seconds_to_min_sec(start)
            end = segment.get("end", 0)
            end = seconds_to_min_sec(end)
            text_dialogue += f"Người nói {speaker}: {text} (Thời gian: {start} - {end})\n"
        return text_dialogue.strip()

    def extract_speaker_roles(self, dialogue: str):
        prompt = f"""[ROLE]: Bạn là một trợ lý AI có khả năng đọc hiểu và tìm kiếm thông tin trong các hội thoại đầy đủ và chính xác tuyệt đối.
                        [TASK]: Nhiệm vụ của bạn là:
                        - Đọc kỹ nội dung mô tả cấu trúc cuộc hội thoại được cung cấp ở mục [DESC]
                        - Đọc kỹ nội dung đoạn hội thoại được cung cấp trong mục [Hội thoại]
                        - Đọc kỹ các dấu hiệu nhận biết được cung cấp trong mục [CALLEE/CALLER RULES]
                        - Xác định vai trò của từng người nói trong đoạn hội thoại là "Khách hàng" hay "nhân viên Sale"
                        - Từ vai trò đã được xác định, thay thế vai trò đó vào lượt nói tương ứng.
                            * Ví dụ, ở đây người nói 0 là khách hàng, người nói 1 là nhân viên sale
                                Người nói 0: “Ờ em ơi, hôm trước anh có coi cái phần mềm quản lý kho bên mình… mà quên tên, có phải SmartInventory gì đó không em?”  
                                Người nói 1: “Dạ đúng rồi ạ, anh đang quan tâm SmartInventory. Anh cần quản lý kho cho bao nhiêu chi nhánh để em tư vấn đúng gói?” 
                            * Thay thế vai trò ta có hội thoại mới:
                                Khách hàng: “Ờ em ơi, hôm trước anh có coi cái phần mềm quản lý kho bên mình… mà quên tên, có phải SmartInventory gì đó không em?”  
                                Nhân viên sale: “Dạ đúng rồi ạ, anh đang quan tâm SmartInventory. Anh cần quản lý kho cho bao nhiêu chi nhánh để em tư vấn đúng gói?”  
                        - Trả về đoạn hội thoại đã được cập nhật vai trò cho từng lượt nói, nội dung các lượt nói giữ nguyên. Ngoài ra không trả về gì thêm.
                        [DESC]: Cuộc hội thoại là tập hợp của nhiều "lượt nói" giữa khách hàng và nhân viên sales. Mỗi lượt nói có dạng:  
                        "Người nói [số thứ tự người nói]: [nội dung lời nói] (Thời gian: [Thời điểm bắt đầu lượt nói] - [Thời điểm kết thúc lượt nói])"
                        [CALLEE/CALLER RULES]:
                            * Dấu hiệu nhận biết nhân viên Sale:
                            - Nhân viên Sale thường xưng em, gọi khách hàng là anh/chị
                            - Nhân viên Sale thường đưa ra các thông tin về tính năng sản phẩm, giá thành, ưu đãi ...
                            - Nhân viên Sale thường đưa ra các câu hỏi cho khách hàng để khảo sát về nhu cầu sử dụng sản phẩm và thuyết phục khách hàng mua / dùng thử
                            - Nhân viên sale thường đưa ra tư vấn dựa theo nhu cầu của khách hàng
                            * Dấu hiệu nhận biết khách hàng:
                            - Khách hàng thường xưng anh/chị
                            - Khách hàng thường đưa ra câu hỏi về sản phẩm xem có khớp với nhu cầu của mình không 
                            - Khi được hỏi, khách hàng trả lời về nhu cầu, quy mô sử dụng và có thể là cả ngân sách để mua và sử dụng sản phẩm
                        [Hội thoại]: {dialogue}
                    """

        message = [{"role": "user", "content": prompt}]
        response = completion(model="gpt-4.1-mini",
                              messages=message,
                              temperature=0.0,
                              base_url=base_url,
                              api_key=api_key)
        result = response.choices[0].message.content.strip()
        total_token = response.usage.total_tokens
        return result, total_token

    def pre_process_dialogue(self, dialogue: str) -> str:
        # You can add any pre-processing steps here if needed
        prompt = f"""[ROLE]: Bạn là một trợ lý AI có khả năng tiền xử lý văn bản hội thoại. Nhiệm vụ của bạn là tiền xử lý đoạn hội thoại được cung cấp ở mục [Hội thoại] thông qua việc thực hiện các bước
                    được định nghĩa trong mục [TASK].
                    [TASK]: Nhiệm vụ của bạn là:
                    - Đọc kỹ nội dung mô tả cấu trúc cuộc hội thoại được cung cấp ở mục [DESC]
                    - Trong mỗi lượt nói, loại bỏ các filler word lặp lại như à, ờ, ừ, ờm, vâng, dạ ...
                    - Loại bỏ các lượt nói quá ngắn chỉ gồm các filler word mà không có nội dung cụ thể  
                    - Trả về đoạn hội thoại sau khi đã được xử lý. Ngoài ra không trả về gì thêm.
                    [DESC]: Cuộc hội thoại là tập hợp của nhiều "lượt nói" giữa khách hàng và nhân viên sales. Mỗi lượt nói có dạng:  
                    "Người nói [số thứ tự người nói]: [nội dung lời nói] (Thời gian: [Thời điểm bắt đầu lượt nói] - [Thời điểm kết thúc lượt nói])"
                    [Hội thoại]: {dialogue}"""
        message = [{"role": "user", "content": prompt}]
        response = completion(model="gpt-4.1-mini",
                              messages=message,
                              temperature=0.0,
                              base_url=base_url,
                              api_key=api_key)
        result = response.choices[0].message.content.strip()
        total_token = response.usage.total_tokens
        return result, total_token

    def __call__(self, dialogue: List[Dict[str, Any]]):
        text_dialogue = self.make_text_dialogue(dialogue)
        pre_processed_dialogue, prep_token = self.pre_process_dialogue(text_dialogue)
        updated_dialogue, total_token = self.extract_speaker_roles(pre_processed_dialogue)
        return updated_dialogue, total_token + prep_token

