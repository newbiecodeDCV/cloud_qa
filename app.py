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

# Thêm thư mục src vào Python path để import các module của bạn
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.audio_processing.analysis import extract_features
    from src.evaluation.evaluator import get_qa_evaluation
    # Tải .env ngay khi module được import (giả sử evaluator làm điều này)
except ImportError as e:
    print(f"Lỗi Import: Không thể tìm thấy các module trong 'src'. {e}")
    print("Hãy chắc chắn rằng file app.py này nằm ở thư mục gốc của dự án.")
    # Định nghĩa các hàm giả để app không bị crash hoàn toàn
    async def extract_features(audio_bytes): return {"status": -1, "message": "Lỗi import extract_features", "segments": []} # Thêm segments rỗng
    async def get_qa_evaluation(data): return {"error": "Lỗi import get_qa_evaluation", "ly_do": ""} # Thêm ly_do rỗng

# --- Các hàm xử lý ---

# HÀM 1: LOGIC THẬT (Của bạn)
async def get_communication_score_and_analysis(audio_bytes):
    """
    Chạy logic thật để chấm tiêu chí "Kỹ năng Giao tiếp" VÀ trả về cả kết quả phân tích.
    Runs real logic for "Communication Skills" AND returns the analysis result.
    """
    print("Bắt đầu chấm điểm 'Kỹ năng Giao tiếp' (Logic thật)...")
    analysis_result = None # Khởi tạo để đảm bảo luôn trả về
    evaluation_result = None # Khởi tạo
    try:
        # 2a. Phân tích âm học (Run audio analysis)
        analysis_result = await extract_features(audio_bytes)
        if analysis_result.get('status') != 1:
            print(f"Lỗi phân tích audio: {analysis_result.get('message')}")
            # Trả về lỗi nhưng vẫn kèm analysis_result nếu có
            return {"error": f"Lỗi phân tích: {analysis_result.get('message')}"}, analysis_result

        print("Phân tích audio thành công.")

        # 2b. Chấm điểm LLM (Score with LLM)
        data_for_llm = {
            'metadata': analysis_result.get('metadata'),
            'segments': analysis_result.get('segments')
        }
        evaluation_result = await get_qa_evaluation(data_for_llm)

        if "error" in evaluation_result:
            print(f"Lỗi LLM: {evaluation_result.get('error')}")
            # Trả về lỗi nhưng vẫn kèm analysis_result
            return {"error": f"Lỗi LLM: {evaluation_result.get('error')}"}, analysis_result

        print("Chấm điểm 'Kỹ năng Giao tiếp' thành công.")
        # Trả về kết quả thật VÀ kết quả phân tích (Return real score AND analysis result)
        return evaluation_result, analysis_result

    except Exception as e:
        print(f"Lỗi hệ thống khi chấm 'Kỹ năng Giao tiếp': {str(e)}")
        # Trả về lỗi nhưng vẫn kèm analysis_result nếu có thể
        error_result = {"error": f"Lỗi hệ thống (Giao tiếp): {str(e)}"}
        return error_result, analysis_result if analysis_result else {"segments": []} # Đảm bảo trả về dict có 'segments'


# HÀM 2 & 3: LOGIC GIẢ LẬP (Giữ nguyên)
async def get_business_score_mock():
    print("Bắt đầu giả lập điểm 'Nghiệp vụ Sản phẩm'...")
    await asyncio.sleep(random.uniform(1, 3))
    score = round(random.uniform(3.5, 5.0), 1)
    result = {"tieu_chi": "Nghiệp vụ Sản phẩm", "diem_so": score, "ly_do": f"- (Giả lập) Nắm rõ thông tin (Điểm: {score})."}
    print("Giả lập điểm 'Nghiệp vụ Sản phẩm' hoàn tất.")
    return result

async def get_compliance_score_mock():
    print("Bắt đầu giả lập điểm 'Tuân thủ'...")
    await asyncio.sleep(random.uniform(0.5, 2))
    score = 5.0 if random.random() > 0.1 else round(random.uniform(3.0, 4.9), 1)
    result = {"tieu_chi": "Tuân thủ", "diem_so": score, "ly_do": f"- (Giả lập) Chào hỏi đúng (Điểm: {score})."}
    print("Giả lập điểm 'Tuân thủ' hoàn tất.")
    return result

# HÀM 5: Helper để cắt và lưu segment audio
def extract_and_save_segment(original_audio_path, start_sec, end_sec, output_dir):
    """
    Cắt một đoạn audio và lưu vào file tạm.
    Cuts an audio segment and saves it to a temporary file.
    """
    try:
        # Load audio gốc (Load original audio)
        # Cần kiểm tra xem file có tồn tại không trước khi load
        if not original_audio_path or not os.path.exists(original_audio_path):
             print(f"Lỗi: Không tìm thấy file audio gốc tại: {original_audio_path}")
             return None
        audio = AudioSegment.from_file(original_audio_path)

        # Thời gian trong pydub là milliseconds (Time in pydub is in milliseconds)
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)

        # Cắt segment (Cut segment)
        segment_audio = audio[start_ms:end_ms]

        # Tạo tên file tạm duy nhất (Create unique temp filename)
        fd, output_path = tempfile.mkstemp(suffix=".wav", dir=output_dir)
        os.close(fd) # Đóng file descriptor ngay lập tức

        # Xuất file (Export file) - đảm bảo định dạng wav để Gradio dễ đọc
        segment_audio.export(output_path, format="wav")
        print(f"Đã lưu segment: {output_path} ({start_sec}s - {end_sec}s)")
        return output_path
    except Exception as e:
        print(f"Lỗi khi cắt audio segment ({start_sec}-{end_sec}): {e}")
        return None

# HÀM 4: HÀM ĐIỀU PHỐI (Cập nhật để KHÔNG trả về chart_data)
async def run_full_demo_evaluation(audio_file_path, customer_name, call_date, call_purpose, progress=gr.Progress(track_tqdm=True)):
    """
    Hàm điều phối: nhận file, chạy 3 tiêu chí, cắt audio segment và trả về báo cáo + segments.
    Orchestrator: receives file, runs 3 criteria, cuts audio segments, returns report + segments.
    """
    # Khởi tạo giá trị trả về mặc định
    report_str = "Chưa có báo cáo."
    # Bỏ chart_data = None
    segment_audio_outputs = []

    # Tạo thư mục tạm (Create temp dir)
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        # Dọn dẹp file cũ (Clean up old files)
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if os.path.isfile(item_path) and item.startswith("segment_") and item.endswith(".wav"):
                try: os.remove(item_path); print(f"Đã xóa file cũ: {item_path}")
                except OSError as e: print(f"Không thể xóa file cũ {item_path}: {e}")
    except Exception as e: print(f"Không thể tạo/dọn dẹp thư mục tạm {temp_dir}: {e}")

    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"Lỗi: File audio không hợp lệ: {audio_file_path}")
        return "Vui lòng tải lên một file âm thanh hợp lệ.", [] # <-- Trả về list rỗng

    progress(0, desc="Bắt đầu xử lý...")
    # 1. Đọc bytes (Read bytes)
    try:
        print(f"Sử dụng file audio: {audio_file_path}")
        with open(audio_file_path, 'rb') as f: audio_bytes_for_analysis = f.read()
        progress(0.1, desc="Đã đọc file audio...")
    except Exception as e:
        print(f"Lỗi đọc file: {str(e)}")
        return f"Lỗi đọc file: {str(e)}", [] # <-- Trả về list rỗng

    # 2. Chạy 3 tác vụ song song (Run 3 tasks in parallel)
    print("Đang chạy 3 tiêu chí chấm điểm song song...")
    progress(0.2, desc="Đang chạy 3 tiêu chí song song...")
    results = await asyncio.gather(
        get_communication_score_and_analysis(audio_bytes_for_analysis),
        get_business_score_mock(),
        get_compliance_score_mock()
    )

    (comm_result, analysis_result), biz_result, comp_result = results
    progress(0.8, desc="Đã có kết quả từ các tiêu chí...")

    # 3. Xử lý kết quả thật và cắt audio (Process real result and cut audio)
    if "error" in comm_result:
        return f"LỖI TỪ TIÊU CHÍ GIAO TIẾP: {comm_result['error']}", [] # <-- Trả về list rỗng

    comm_score_raw = (comm_result.get('chao_xung_danh', 0) +
                      comm_result.get('ky_nang_noi', 0) +
                      comm_result.get('ky_nang_nghe', 0) +
                      comm_result.get('thai_do', 0))
    comm_score_scaled = round(comm_score_raw * (5.0 / 4.0), 1)

    # --- Phần cắt Audio ---
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
    Khách hàng: {customer_name if customer_name else 'N/A'}
    Ngày gọi: {call_date if call_date else 'N/A'}
    Mục đích: {call_purpose if call_purpose else 'N/A'}

    --- 1. Kỹ năng Giao tiếp (Logic thật) ---
    Điểm (thang 5): {comm_score_scaled}/5.0
    Điểm thành phần (0/1):
        - Chào/Xưng danh: {comm_result.get('chao_xung_danh', 'Lỗi')}
        - Kỹ năng nói: {comm_result.get('ky_nang_noi', 'Lỗi')}
        - Kỹ năng nghe: {comm_result.get('ky_nang_nghe', 'Lỗi')}
        - Thái độ: {comm_result.get('thai_do', 'Lỗi')}
    Mức lỗi: {comm_result.get('muc_loi', 'N/A')}
    Lý do chi tiết:
    {llm_reason}

    --- 2. Nghiệp vụ Sản phẩm (Logic giả) ---
    Điểm (thang 5): {biz_result.get('diem_so', 'N/A')}/5.0
    Lý do chi tiết:
    {biz_result.get('ly_do', 'Không có')}

    --- 3. Tuân thủ (Logic giả) ---
    Điểm (thang 5): {comp_result.get('diem_so', 'N/A')}/5.0
    Lý do chi tiết:
    {comp_result.get('ly_do', 'Không có')}
    """

    # 5. BỎ PHẦN TẠO chart_data (REMOVE CHART DATA CREATION)
    # try:
    #     chart_data = pd.DataFrame(...) # <-- DÒNG NÀY ĐÃ BỊ XÓA
    # except Exception as e:
    #     print(f"Lỗi khi tạo DataFrame cho biểu đồ: {e}")
    #     chart_data = None

    print("Đã có kết quả tổng hợp và audio segments.")
    progress(1, desc="Hoàn thành!")

    # Trả về report và list audio segment (Return report and segment list)
    # KHÔNG TRẢ VỀ chart_data NỮA (NO LONGER RETURN chart_data)
    return report_str, segment_audio_outputs


# --- Hàm giả lập CRM (Giữ nguyên) ---
def mock_check_crm_api(data_file):
    if data_file is None: return "Vui lòng tải lên file dữ liệu CRM."
    report = f"BÁO CÁO KIỂM TRA DỮ LIỆU CRM (Mock)\n=====================================\nFile: {os.path.basename(data_file.name)}\n(Đây là dữ liệu giả lập)"
    return report

# --- Thiết kế giao diện Gradio ---
with gr.Blocks(title="Demo Hệ thống Chấm điểm QA", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# DEMO HỆ THỐNG CHẤM ĐIỂM QA (3 TIÊU CHÍ + AUDIO SEGMENTS)")
    gr.Markdown("Tải file âm thanh, xem điểm 3 tiêu chí, và nghe lại các đoạn audio được LLM tham chiếu trong phần 'Kỹ năng Giao tiếp'.")

    segment_data_state = gr.State(value=[])

    with gr.Tabs():
        # Tab 1: Đánh giá cuộc gọi
        with gr.TabItem("📞 Đánh giá chất lượng cuộc gọi"):
            gr.Markdown("## Tải file âm thanh và xem kết quả chấm điểm")
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(label="🎙️ Tải lên file âm thanh (.wav, .mp3)", type="filepath")
                    customer_name_input = gr.Textbox(label="👤 Tên khách hàng (Tùy chọn)")
                    call_date_input = gr.Textbox(label="📅 Ngày gọi (Tùy chọn, VD: 2025-10-27)")
                    call_purpose_input = gr.Dropdown(
                        choices=["Bán hàng", "Hỗ trợ kỹ thuật", "Khiếu nại", "Tư vấn sản phẩm", "Chăm sóc khách hàng", "Khác"],
                        label="🎯 Mục đích cuộc gọi (Tùy chọn)"
                    )
                    evaluate_call_btn = gr.Button("⚡ Bắt đầu Chấm điểm", variant="primary", size="lg")

                with gr.Column(scale=2):
                    call_report_output = gr.Textbox(
                        label="📄 Báo cáo chi tiết (3 Tiêu chí)",
                        lines=25, # Tăng số dòng lên vì không còn biểu đồ (Increase lines as chart is removed)
                        interactive=False,
                        placeholder="Kết quả chấm điểm chi tiết sẽ hiển thị ở đây..."
                    )
                    # --- XÓA BỎ score_chart_output ---
                    # score_chart_output = gr.BarPlot(...) # <-- DÒNG NÀY ĐÃ BỊ XÓA

            # --- Khu vực hiển thị Audio Segments (Giữ nguyên) ---
            gr.Markdown("---")
            gr.Markdown("### 🔊 Nghe lại các Audio Segment được tham chiếu (Tiêu chí Giao tiếp)")
            gr.Markdown("_Các đoạn audio liên quan đến phần 'Lý do chi tiết' của tiêu chí Giao tiếp sẽ xuất hiện ở đây sau khi chấm điểm xong._")

            segment_outputs_components = []
            MAX_SEGMENTS_DISPLAY = 10
            with gr.Column(visible=False) as segment_display_area:
                for i in range(MAX_SEGMENTS_DISPLAY):
                    md = gr.Markdown(visible=False, elem_id=f"segment-md-{i}")
                    audio_player = gr.Audio(visible=False, label=f"Segment {i+1}", elem_id=f"segment-audio-{i}")
                    segment_outputs_components.extend([md, audio_player])

            # --- Logic Cập nhật Giao diện ---
            # Hàm này giờ chỉ nhận report và segment_data (Function now only takes report and segment_data)
            def update_ui_with_segments(report, segment_data):
                """
                Cập nhật UI với báo cáo và các audio segment.
                Updates UI with report and audio segments.
                """
                # KHÔNG CẦN TRẢ VỀ chart NỮA (No need to return chart)
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
                inputs=[audio_input, customer_name_input, call_date_input, call_purpose_input],
                # Output giờ chỉ là report và state (Output is now just report and state)
                outputs=[call_report_output, segment_data_state] # <-- BỎ score_chart_output
            ).then(
                fn=update_ui_with_segments,
                # Input của hàm update giờ chỉ là report và state (Input for update is now report and state)
                inputs=[call_report_output, segment_data_state], # <-- BỎ score_chart_output
                # Output của hàm update giờ không còn chart (Output no longer includes chart)
                outputs=[call_report_output] + segment_outputs_components + [segment_display_area]
            )

        # Tab 2: Kiểm tra CRM (Giữ nguyên mock)
        with gr.TabItem("📊 Kiểm tra tuân thủ CRM (Mock)"):
             gr.Markdown("## KIỂM TRA TUÂN THỦ CẬP NHẬT CRM (Dữ liệu giả lập)")
             with gr.Row():
                with gr.Column(scale=1):
                    crm_file_input = gr.File(label="📁 Tải lên file dữ liệu CRM", file_types=[".csv", ".xlsx"])
                    check_crm_btn = gr.Button("🔍 Kiểm tra dữ liệu", variant="primary", size="lg")
                with gr.Column(scale=2):
                    crm_report_output = gr.Textbox(
                        label="📄 Báo cáo từ AI (Mock)", lines=18, interactive=False,
                        placeholder="Báo cáo kiểm tra (giả lập) sẽ hiển thị tại đây..."
                    )
             check_crm_btn.click(
                fn=mock_check_crm_api, inputs=crm_file_input, outputs=crm_report_output
             )

# Chạy ứng dụng và bật chia sẻ link (Run app with sharing)
if __name__ == "__main__":
    print("Đang khởi chạy Gradio App...")
    print("Hãy đảm bảo file .env đã được cấu hình đúng.")
    # Tạo thư mục tạm nếu chưa có
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"Thư mục tạm cho audio segments: {temp_dir}")

    # Chạy Gradio, bật share=True và debug=True để dễ theo dõi lỗi hơn
    demo.launch(share=True, debug=True) # <-- Bật chia sẻ link VÀ debug

