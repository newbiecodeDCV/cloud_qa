<<<<<<< HEAD
# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import numpy as np
import asyncio
import random
import sys
import re # Thư viện regex để tìm số segment
import os # Để tạo thư mục tạm
import tempfile # Để tạo file audio tạm
from pathlib import Path
from pydub import AudioSegment # Thư viện xử lý audio
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_EVALUATE_ENDPOINT = f"{API_BASE_URL}/api/v1/evaluate"
API_TASK_ENDPOINT = f"{API_BASE_URL}/api/v1/task"

async def get_communication_score_and_analysis(audio_bytes_or_path):
    """
    Gọi API để chấm tiêu chí "Kỹ năng Giao tiếp" VÀ trả về cả kết quả phân tích.
    Calls API for "Communication Skills" scoring AND returns the analysis result.
    
    Args:
        audio_bytes_or_path: Có thể là bytes hoặc đường dẫn file
    """
    print("Bắt đầu chấm điểm 'Kỹ năng Giao tiếp' (Gọi API)...")
    analysis_result = None
    evaluation_result = None
    
    try:
        if isinstance(audio_bytes_or_path, bytes):
            print("Nhận audio dạng bytes, tạo file tạm...")
            import tempfile
            fd, temp_audio_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_bytes_or_path)
            audio_file_path = temp_audio_path
            is_temp_file = True
        else:
            audio_file_path = audio_bytes_or_path
            is_temp_file = False
            
        
        if not audio_file_path or not os.path.exists(audio_file_path):
            error_msg = f"File không tồn tại: {audio_file_path}"
            print(f"Lỗi: {error_msg}")
            return {"error": error_msg}, {"segments": []}
        
        async with httpx.AsyncClient(timeout=300.0) as client:  
            print(f"Đang upload file: {audio_file_path}")
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')}
                
               
                response = await client.post(API_EVALUATE_ENDPOINT, files=files)
                
                if response.status_code != 200:
                    error_msg = f"API trả về lỗi {response.status_code}: {response.text}"
                    print(f"Lỗi API: {error_msg}")
                    return {"error": error_msg}, {"segments": []}
                
                task_data = response.json()
                task_id = task_data.get("task_id")
                
                if not task_id:
                    return {"error": "Không nhận được task_id từ API"}, {"segments": []}
                
                print(f"✓ Đã upload file. Task ID: {task_id}")
            
           
            max_polls = 120  
            poll_count = 0
            
            while poll_count < max_polls:
                await asyncio.sleep(1) 
                poll_count += 1
                
         
                result_response = await client.get(f"{API_TASK_ENDPOINT}/{task_id}")
                
                if result_response.status_code != 200:
                    print(f"Lỗi khi lấy kết quả: {result_response.status_code}")
                    continue
                
                result_data = result_response.json()
                status = result_data.get("status")
                
                print(f"Poll {poll_count}: Status = {status}")
                
                if status == "completed":
                    print("✓ API đã hoàn thành xử lý!")
                    
                    evaluation_result = {
                        "chao_xung_danh": result_data.get("chao_xung_danh", 0),
                        "ky_nang_noi": result_data.get("ky_nang_noi", 0),
                        "ky_nang_nghe": result_data.get("ky_nang_nghe", 0),
                        "thai_do": result_data.get("thai_do", 0),
                        "muc_loi": result_data.get("muc_loi", "Không"),
                        "ly_do": result_data.get("ly_do", "")
                    }
                    
                    # Tạo analysis_result từ metadata (để tương thích với code cũ)
                    metadata = result_data.get("metadata", {})
                    segments = result_data.get("segments",[] )
                    
                    analysis_result = {
                        "segments": segments,
                        "metadata": metadata
                    }
                    
                    return evaluation_result, analysis_result
                
                elif status == "failed":
                    error_msg = result_data.get("error_message", "Xử lý thất bại")
                    print(f"✗ API xử lý thất bại: {error_msg}")
                    return {"error": error_msg}, {"segments": []}
                
                elif status in ["pending", "processing"]:
                    continue
                else:
                    print(f"Trạng thái không xác định: {status}")
                    continue
            
            
            return {"error": "Timeout: API không phản hồi trong thời gian cho phép"}, {"segments": []}
    
    except httpx.RequestError as e:
        error_msg = f"Lỗi kết nối API: {str(e)}"
        print(f"Lỗi: {error_msg}")
        return {"error": error_msg}, {"segments": []}
    
    except Exception as e:
        error_msg = f"Lỗi hệ thống: {str(e)}"
        print(f"Lỗi: {error_msg}")
        return {"error": error_msg}, {"segments": []}



def extract_and_save_segment(original_audio_path, start_sec, end_sec, output_dir):
    """
    Cắt một đoạn audio và lưu vào file tạm.
    Cuts an audio segment and saves it to a temporary file.
    """
    try:
        if not original_audio_path or not os.path.exists(original_audio_path):
             print(f"Lỗi: Không tìm thấy file audio gốc tại: {original_audio_path}")
             return None
        audio = AudioSegment.from_file(original_audio_path)

        
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)

       
        segment_audio = audio[start_ms:end_ms]

        
        fd, output_path = tempfile.mkstemp(suffix=".wav", dir=output_dir)
        os.close(fd) 

        segment_audio.export(output_path, format="wav")
        print(f"Đã lưu segment: {output_path} ({start_sec}s - {end_sec}s)")
        return output_path
    except Exception as e:
        print(f"Lỗi khi cắt audio segment ({start_sec}-{end_sec}): {e}")
        return None


async def run_full_demo_evaluation(audio_file_path,  progress=gr.Progress(track_tqdm=True)):
    
    report_str = "Chưa có báo cáo."
    segment_audio_outputs = []

    
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if os.path.isfile(item_path) and item.startswith("segment_") and item.endswith(".wav"):
                try: os.remove(item_path); print(f"Đã xóa file cũ: {item_path}")
                except OSError as e: print(f"Không thể xóa file cũ {item_path}: {e}")
    except Exception as e: print(f"Không thể tạo/dọn dẹp thư mục tạm {temp_dir}: {e}")

    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"Lỗi: File audio không hợp lệ: {audio_file_path}")
        return "Vui lòng tải lên một file âm thanh hợp lệ.", [] 

    progress(0, desc="Bắt đầu xử lý...")
    
    try:
        print(f"Sử dụng file audio: {audio_file_path}")
        with open(audio_file_path, 'rb') as f: audio_bytes_for_analysis = f.read()
        progress(0.1, desc="Đã đọc file audio...")
    except Exception as e:
        print(f"Lỗi đọc file: {str(e)}")
        return f"Lỗi đọc file: {str(e)}", [] 

    progress(0.2, desc="Đang chạy 3 tiêu chí song song...")
    (comm_result, analysis_result) = await get_communication_score_and_analysis(audio_bytes_for_analysis)


    if "error" in comm_result:
        return f"LỖI TỪ TIÊU CHÍ GIAO TIẾP: {comm_result['error']}", [] # 

    comm_score_raw = (  0.1  *  (comm_result.get('chao_xung_danh', 0) +
                      comm_result.get('ky_nang_noi', 0))    + 0.4 *(
                      comm_result.get('ky_nang_nghe', 0) +
                      comm_result.get('thai_do', 0)))
    comm_score_scaled = round(comm_score_raw * 2.0  ,1)

    
    llm_reason = comm_result.get('ly_do', '')
    referenced_segments_info = []
    if llm_reason and analysis_result and isinstance(analysis_result.get('segments'), list):
        found_indices = set()
        try:
             matches = re.findall(r'segment\s*(\d+)', llm_reason, re.IGNORECASE)
             found_indices = set(map(int, matches))
             print(f"Tìm thấy tham chiếu đến các segment index (từ 1): {found_indices}")
        except Exception as e: print(f"Lỗi khi parse segment indices: {e}")

        all_segments = analysis_result.get('segments', [])
        for index_from_1 in found_indices:
            index_from_0 = index_from_1 - 1
            if 0 <= index_from_0 < len(all_segments):
                segment_data = all_segments[index_from_0]
                start = segment_data.get('start_time')
                end = segment_data.get('end_time')
                text_preview = str(segment_data.get('text', ''))[:50] + ("..." if len(str(segment_data.get('text', ''))) > 50 else "")
                if start is not None and end is not None:
                    segment_audio_path = extract_and_save_segment(audio_file_path, start, end, temp_dir)
                    if segment_audio_path:
                        segment_description = f"**Segment {index_from_1} ({start:.2f}s - {end:.2f}s):** \"{text_preview}\""
                        referenced_segments_info.append((segment_description, segment_audio_path))
            else: print(f"Cảnh báo: Segment index {index_from_1} không hợp lệ.")

    try:
        referenced_segments_info.sort(key=lambda x: int(re.search(r'Segment (\d+)', x[0]).group(1)) if re.search(r'Segment (\d+)', x[0]) else 0)
    except Exception as e: print(f"Lỗi khi sắp xếp segments: {e}")
    segment_audio_outputs = referenced_segments_info
    # -----------------------

    # 4. Xây dựng Báo cáo Text (Build Text Report)
    report_str = f"""
    BÁO CÁO TỔNG HỢP 3 TIÊU CHÍ (DEMO)
    ======================================
    

     1. Kỹ năng Giao tiếp  ---
    Điểm : {comm_score_scaled}/2.0
    Điểm thành phần (0/1):
        - Chào/Xưng danh: {comm_result.get('chao_xung_danh', 'Lỗi')}
        - Kỹ năng nói: {comm_result.get('ky_nang_noi', 'Lỗi')}
        - Kỹ năng nghe: {comm_result.get('ky_nang_nghe', 'Lỗi')}
        - Thái độ: {comm_result.get('thai_do', 'Lỗi')}
    Mức lỗi: {comm_result.get('muc_loi', 'N/A')}
    Lý do chi tiết:
    {llm_reason}

    """

    print("Đã có kết quả tổng hợp và audio segments.")
    progress(1, desc="Hoàn thành!")

    return report_str, segment_audio_outputs





with gr.Blocks(title="Demo Hệ thống Chấm điểm QA", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# DEMO HỆ THỐNG CHẤM ĐIỂM QA ")
   
    segment_data_state = gr.State(value=[])

    with gr.Tabs():
        with gr.TabItem("📞 Đánh giá chất lượng cuộc gọi"):
            gr.Markdown("## Tải file âm thanh và xem kết quả chấm điểm")
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(label="🎙️ Tải lên file âm thanh (.wav, .mp3)", type="filepath")
                    evaluate_call_btn = gr.Button("⚡ Bắt đầu Chấm điểm", variant="primary", size="lg")

                with gr.Column(scale=2):
                    call_report_output = gr.Textbox(
                        label="📄 Báo cáo chi tiết ",
                        lines=25, 
                        interactive=False,
                        placeholder="Kết quả chấm điểm chi tiết sẽ hiển thị ở đây..."
                    )
                    
            gr.Markdown("---")
            gr.Markdown("### 🔊 Nghe lại các Audio Segment được tham chiếu (Tiêu chí Giao tiếp)")


            segment_outputs_components = []
            MAX_SEGMENTS_DISPLAY = 10
            with gr.Column(visible=False) as segment_display_area:
                for i in range(MAX_SEGMENTS_DISPLAY):
                    md = gr.Markdown(visible=False, elem_id=f"segment-md-{i}")
                    audio_player = gr.Audio(visible=False, label=f"Segment {i+1}", elem_id=f"segment-audio-{i}")
                    segment_outputs_components.extend([md, audio_player])

    
            def update_ui_with_segments(report, segment_data):
                """
                Cập nhật UI với báo cáo và các audio segment.
                Updates UI with report and audio segments.
                """
             
                updates = [report]

                num_segments_found = len(segment_data) if isinstance(segment_data, list) else 0
                print(f"update_ui_with_segments: Nhận được {num_segments_found} segments.")

                for i in range(MAX_SEGMENTS_DISPLAY):
                    md_update = gr.Markdown(visible=False, value="")
                    audio_update = gr.Audio(visible=False, value=None)
                    if i < num_segments_found:
                        try:
                            desc, audio_path = segment_data[i]
                            if audio_path and os.path.exists(audio_path):
                                md_update = gr.Markdown(value=desc, visible=True)
                                audio_update = gr.Audio(value=audio_path, visible=True)
                                print(f"  - Cập nhật UI cho segment {i+1}: {audio_path}")
                            else:
                                print(f"  - Lỗi: File audio cho segment {i+1} không tồn tại: {audio_path}")
                                md_update = gr.Markdown(value=f"{desc}\n\n_(Lỗi: Không tìm thấy file audio)_", visible=True)
                        except Exception as e:
                            print(f"  - Lỗi khi xử lý dữ liệu segment {i+1}: {e}")
                            md_update = gr.Markdown(value=f"**Segment {i+1}:** _Lỗi xử lý dữ liệu_", visible=True)
                    updates.extend([md_update, audio_update])

                area_update = gr.Column(visible=num_segments_found > 0)
                updates.append(area_update)

                print("update_ui_with_segments: Hoàn thành cập nhật UI.")
                return updates

            # Kết nối nút bấm (Connect button)
            evaluate_call_btn.click(
                fn=run_full_demo_evaluation,
                inputs=[audio_input],

                outputs=[call_report_output, segment_data_state] 
            ).then(
                fn=update_ui_with_segments,
            
                inputs=[call_report_output, segment_data_state], 
                outputs=[call_report_output] + segment_outputs_components + [segment_display_area]
            )

        
if __name__ == "__main__":
    print("Đang khởi chạy Gradio App...")
    print("Hãy đảm bảo file .env đã được cấu hình đúng.")
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"Thư mục tạm cho audio segments: {temp_dir}")
    demo.launch(share=True, debug=True) 

=======
import gradio as gr
import pandas as pd
import numpy as np

# --- Các hàm giả lập (mock functions) ---
# Bạn sẽ thay thế các hàm này bằng lời gọi API thực tế của mình.

def mock_check_crm_api(data_file):
    """
    Hàm giả lập cho việc kiểm tra CRM.
    Thay thế nội dung hàm này bằng lời gọi API của bạn.
    API sẽ nhận file và trả về một chuỗi báo cáo.
    """
    if data_file is None:
        return "Vui lòng tải lên file dữ liệu CRM."
    
    # Đây là nơi bạn sẽ thêm code để gọi API
    # Ví dụ: response = requests.post("YOUR_API_ENDPOINT/crm-check", files={"file": data_file})
    # report = response.json()["report"]
    
    # Trả về một chuỗi báo cáo giả lập
    report = f"""
    BÁO CÁO KIỂM TRA DỮ LIỆU CRM (GỌI API THỰC TẾ)
    =================================================
    File đã tải: {data_file.name}
    
    KẾT QUẢ MẪU:
    - Phát hiện 3 lỗi:
      + Thiếu cột 'email' ở 5 bản ghi.
      + Số điện thoại không đúng định dạng ở 2 bản ghi.
    - Cảnh báo:
      + 10 bản ghi chưa được cập nhật trong 30 ngày.
    
    (API của bạn sẽ trả về nội dung chi tiết tại đây)
    """
    return report

def mock_evaluate_call_api(audio_file, customer_name, call_date, call_purpose):
    """
    Hàm giả lập cho việc đánh giá cuộc gọi.
    Thay thế nội dung hàm này bằng lời gọi API của bạn.
    API sẽ nhận các thông tin và trả về báo cáo + dữ liệu biểu đồ.
    """
    if audio_file is None:
        return "Vui lòng tải lên file âm thanh cuộc gọi.", None

    # Đây là nơi bạn sẽ thêm code để gọi API
    # Ví dụ: response = requests.post("YOUR_API_ENDPOINT/call-evaluate", files={"audio": audio_file}, data={"customer": customer_name, ...})
    # result = response.json()
    # report = result["report"]
    # chart_data = result["sentiment_chart"]

    # Trả về báo cáo và dữ liệu biểu đồ giả lập
    report = f"""
    BÁO CÁO ĐÁNH GIÁ CUỘC GỌI (GỌI API THỰC TẾ)
    =================================================
    Khách hàng: {customer_name}
    Ngày gọi: {call_date}
    Mục đích: {call_purpose}
    
    KẾT QUẢ MẪU:
    - Điểm trung bình: 4.2/5
    - Chào hỏi: 5/5
    - Hiểu vấn đề: 4/5
    - Cung cấp giải pháp: 4/5
    - Kết thúc: 4/5
    
    Đề xuất:
    - Nên nhấn mạnh hơn về lợi ích của sản phẩm A.
    
    (API của bạn sẽ trả về nội dung chi tiết tại đây)
    """
    
    # Dữ liệu giả lập cho biểu đồ
    chart_data = pd.DataFrame([
        {"Cảm xúc": "Tích cực", "Phần trăm": 65},
        {"Cảm xúc": "Trung tính", "Phần trăm": 25},
        {"Cảm xúc": "Tiêu cực", "Phần trăm": 10}
    ])
    
    return report, chart_data

# --- Thiết kế giao diện Gradio ---

with gr.Blocks(title="Hệ thống AI hỗ trợ Sales và CSKH", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# HỆ THỐNG AI HỖ TRỢ SALES VÀ CSKH")
    
    with gr.Tabs():
        # Tab 1: Kiểm tra CRM
        with gr.TabItem("📊 Kiểm tra tuân thủ CRM"):
            gr.Markdown("## **KIỂM TRA TUẤN THỨ CẤP NHẤT CRM CỦA SALES/CSKH**")
            gr.Markdown("Tải lên file dữ liệu (CSV, Excel) để AI tự động phát hiện lỗi và cảnh báo.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    crm_file_input = gr.File(label="📁 Tải lên file dữ liệu CRM", file_types=[".csv", ".xlsx"])
                    check_crm_btn = gr.Button("🔍 Kiểm tra dữ liệu", variant="primary", size="lg")
                
                with gr.Column(scale=2):
                    crm_report_output = gr.Textbox(
                        label="📄 Báo cáo từ AI", 
                        lines=18, 
                        interactive=False,
                        placeholder="Báo cáo kiểm tra sẽ hiển thị tại đây sau khi bạn nhấn nút 'Kiểm tra dữ liệu'..."
                    )
            
            # Kết nối nút bấm với hàm giả lập
            check_crm_btn.click(
                fn=mock_check_crm_api, 
                inputs=crm_file_input, 
                outputs=crm_report_output
            )

        # Tab 2: Đánh giá cuộc gọi
        with gr.TabItem("📞 Đánh giá chất lượng cuộc gọi"):
            gr.Markdown("## **DÁNH GIÁ CHĂM SÓC CUỘC GỌI CỦA SALES TRAO ĐỔI VỚI KH**")
            gr.Markdown("Tải lên file âm thanh và cung cấp thông tin để AI phân tích và đánh giá chất lượng.")
            
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(label="🎙️ Tải lên file âm thanh cuộc gọi", type="filepath")
                    customer_name_input = gr.Textbox(label="👤 Tên khách hàng")
                    call_date_input = gr.Textbox(label="📅 Ngày gọi (VD: 2023-10-27)")
                    call_purpose_input = gr.Dropdown(
                        choices=["Bán hàng", "Hỗ trợ kỹ thuật", "Khiếu nại", "Tư vấn sản phẩm", "Chăm sóc khách hàng", "Khác"],
                        label="🎯 Mục đích cuộc gọi"
                    )
                    evaluate_call_btn = gr.Button("⚡ Đánh giá cuộc gọi", variant="primary", size="lg")
                
                with gr.Column(scale=2):
                    call_report_output = gr.Textbox(
                        label="📄 Báo cáo chi tiết từ AI", 
                        lines=12, 
                        interactive=False,
                        placeholder="Báo cáo đánh giá sẽ hiển thị tại đây..."
                    )
            
            with gr.Row():
                sentiment_chart_output = gr.BarPlot(
                    title="📈 Phân tích cảm xúc cuộc gọi",
                    x="Cảm xúc",
                    y="Phần trăm",
                    height=300,
                    width=600
                )

            # Kết nối nút bấm với hàm giả lập
            evaluate_call_btn.click(
                fn=mock_evaluate_call_api,
                inputs=[audio_input, customer_name_input, call_date_input, call_purpose_input],
                outputs=[call_report_output, sentiment_chart_output]
            )

# Chạy ứng dụng
if __name__ == "__main__":
    demo.launch()
>>>>>>> 2632b50 (Add Gradio interface for CRM compliance checking and call evaluation,, and set up project structure with necessary requirements and tests.)
