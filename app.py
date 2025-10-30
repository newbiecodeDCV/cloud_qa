# -*- coding: utf-8 -*-
import gradio as gr
import asyncio
import os
import re
import tempfile
from pydub import AudioSegment
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_EVALUATE_FULL_ENDPOINT = f"{API_BASE_URL}/api/v1/evaluate/full"  # Endpoint mới
API_TASK_FULL_ENDPOINT = f"{API_BASE_URL}/api/v1/task/full"  # Endpoint lấy kết quả mới


async def get_full_evaluation_and_analysis(audio_bytes_or_path):
    """
    Gọi API để chấm CẢ 2 TIÊU CHÍ: Giao tiếp + Bán hàng
    
    Args:
        audio_bytes_or_path: Có thể là bytes hoặc đường dẫn file
    
    Returns:
        (evaluation_result, analysis_result)
    """
    print("Bắt đầu chấm điểm TOÀN DIỆN (2 tiêu chí)...")
    
    try:
        if isinstance(audio_bytes_or_path, bytes):
            print("Nhận audio dạng bytes, tạo file tạm...")
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
        
        async with httpx.AsyncClient(timeout=600.0) as client:  # Tăng timeout vì chấm 2 tiêu chí
            print(f"Đang upload file: {audio_file_path}")
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')}
                
                # Gọi API đánh giá toàn diện
                response = await client.post(API_EVALUATE_FULL_ENDPOINT, files=files)
                
                if response.status_code != 200:
                    error_msg = f"API trả về lỗi {response.status_code}: {response.text}"
                    print(f"Lỗi API: {error_msg}")
                    return {"error": error_msg}, {"segments": []}
                
                task_data = response.json()
                task_id = task_data.get("task_id")
                
                if not task_id:
                    return {"error": "Không nhận được task_id từ API"}, {"segments": []}
                
                print(f"✓ Đã upload file. Task ID: {task_id}")
            
            # Poll kết quả
            max_polls = 240  # Tăng lên vì xử lý 2 tiêu chí
            poll_count = 0
            
            while poll_count < max_polls:
                await asyncio.sleep(2)  # Poll mỗi 2s
                poll_count += 1
                
                result_response = await client.get(f"{API_TASK_FULL_ENDPOINT}/{task_id}")
                
                if result_response.status_code != 200:
                    print(f"Lỗi khi lấy kết quả: {result_response.status_code}")
                    continue
                
                result_data = result_response.json()
                status = result_data.get("status")
                
                print(f"Poll {poll_count}: Status = {status}")
                
                if status == "completed":
                    print("✓ API đã hoàn thành xử lý!")
                    
                    evaluation_result = {
                        # Kỹ năng Giao tiếp
                        "chao_xung_danh": result_data.get("chao_xung_danh", 0),
                        "ky_nang_noi": result_data.get("ky_nang_noi", 0),
                        "ky_nang_nghe": result_data.get("ky_nang_nghe", 0),
                        "thai_do": result_data.get("thai_do", 0),
                        "communication_score": result_data.get("communication_score", 0),
                        "muc_loi": result_data.get("muc_loi", "Không"),
                        "ly_do_giao_tiep": result_data.get("ly_do_giao_tiep", ""),
                        
                        # Kỹ năng Bán hàng
                        "sales_score": result_data.get("sales_score", 0),
                        "sales_criteria_details": result_data.get("sales_criteria_details", []),
                        
                        # Tổng hợp
                        "total_score": result_data.get("total_score", 0),
                    }
                    
                    analysis_result = {
                        "segments": result_data.get("segments", []),
                        "metadata": result_data.get("metadata", {})
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
    """Cắt một đoạn audio và lưu vào file tạm"""
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


async def run_full_evaluation(audio_file_path, progress=gr.Progress(track_tqdm=True)):
    """Chạy đánh giá toàn diện cả 2 tiêu chí"""
    
    report_str = "Chưa có báo cáo."
    segment_audio_outputs = []
    
    # Tạo và dọn dẹp thư mục tạm
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if os.path.isfile(item_path) and item.startswith("segment_") and item.endswith(".wav"):
                try: 
                    os.remove(item_path)
                    print(f"Đã xóa file cũ: {item_path}")
                except OSError as e: 
                    print(f"Không thể xóa file cũ {item_path}: {e}")
    except Exception as e: 
        print(f"Không thể tạo/dọn dẹp thư mục tạm {temp_dir}: {e}")
    
    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"Lỗi: File audio không hợp lệ: {audio_file_path}")
        return "Vui lòng tải lên một file âm thanh hợp lệ.", []
    
    progress(0, desc="Bắt đầu xử lý...")
    
    try:
        print(f"Sử dụng file audio: {audio_file_path}")
        with open(audio_file_path, 'rb') as f: 
            audio_bytes_for_analysis = f.read()
        progress(0.1, desc="Đã đọc file audio...")
    except Exception as e:
        print(f"Lỗi đọc file: {str(e)}")
        return f"Lỗi đọc file: {str(e)}", []
    
    progress(0.2, desc="Đang chạy đánh giá toàn diện (2 tiêu chí)...")
    (eval_result, analysis_result) = await get_full_evaluation_and_analysis(audio_bytes_for_analysis)
    
    if "error" in eval_result:
        return f"LỖI: {eval_result['error']}", []
    
    # Lấy điểm số
    comm_score = eval_result.get('communication_score', 0)
    sales_score = eval_result.get('sales_score', 0)
    total_score = eval_result.get('total_score', 0)
    
    # Xử lý segments được tham chiếu
    llm_reason = eval_result.get('ly_do_giao_tiep', '')
    referenced_segments_info = []
    
    if llm_reason and analysis_result and isinstance(analysis_result.get('segments'), list):
        found_indices = set()
        try:
             matches = re.findall(r'segment\s*(\d+)', llm_reason, re.IGNORECASE)
             found_indices = set(map(int, matches))
             print(f"Tìm thấy tham chiếu đến các segment index: {found_indices}")
        except Exception as e: 
            print(f"Lỗi khi parse segment indices: {e}")
        
        all_segments = analysis_result.get('segments', [])
        for index_from_1 in found_indices:
            index_from_0 = index_from_1 - 1
            if 0 <= index_from_0 < len(all_segments):
                segment_data = all_segments[index_from_0]
                start = segment_data.get('start_time')
                end = segment_data.get('end_time')
                text_preview = str(segment_data.get('text', ''))[:50]
                if len(str(segment_data.get('text', ''))) > 50:
                    text_preview += "..."
                    
                if start is not None and end is not None:
                    segment_audio_path = extract_and_save_segment(audio_file_path, start, end, temp_dir)
                    if segment_audio_path:
                        segment_description = f"**Segment {index_from_1} ({start:.2f}s - {end:.2f}s):** \"{text_preview}\""
                        referenced_segments_info.append((segment_description, segment_audio_path))
    
    try:
        referenced_segments_info.sort(key=lambda x: int(re.search(r'Segment (\d+)', x[0]).group(1)) if re.search(r'Segment (\d+)', x[0]) else 0)
    except Exception as e: 
        print(f"Lỗi khi sắp xếp segments: {e}")
    
    segment_audio_outputs = referenced_segments_info
    
    # Xây dựng báo cáo
    report_str = f"""
╔════════════════════════════════════════════════════════════════╗
║          BÁO CÁO ĐÁNH GIÁ TOÀN DIỆN - 2 TIÊU CHÍ              ║
╚════════════════════════════════════════════════════════════════╝

📊 TỔNG QUAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎯 TỔNG ĐIỂM CUỐI CÙNG: {total_score:.2f} điểm
    
    
═══════════════════════════════════════════════════════════════

 1️⃣  TIÊU CHÍ 1: KỸ NĂNG GIAO TIẾP
─────────────────────────────────────────────────────────────────
    💯 Điểm: {comm_score:.2f}/2.0
    
    📋 Điểm thành phần (0/1):
        • Chào/Xưng danh:  {eval_result.get('chao_xung_danh', 'N/A')}/1
        • Kỹ năng nói:     {eval_result.get('ky_nang_noi', 'N/A')}/1
        • Kỹ năng nghe:    {eval_result.get('ky_nang_nghe', 'N/A')}/1
        • Thái độ:         {eval_result.get('thai_do', 'N/A')}/1
    
    ⚠️  Mức lỗi: {eval_result.get('muc_loi', 'N/A')}
    
    📝 Lý do chi tiết:
    {llm_reason}


═══════════════════════════════════════════════════════════════

 2️⃣  TIÊU CHÍ 2: KỸ NĂNG BÁN HÀNG
─────────────────────────────────────────────────────────────────
    💯 Điểm: {sales_score if sales_score is not None else 'Đang xử lý...'}
    
    📋 Chi tiết các tiêu chí bán hàng:
"""
    
    # Thêm chi tiết bán hàng nếu có
    sales_details = eval_result.get('sales_criteria_details', [])
    if sales_details:
        for detail in sales_details:
            report_str += f"        • {detail.get('criteria_name', 'N/A')}: "
            report_str += f"{'✅ Đạt' if detail.get('status') == 1 else '❌ Chưa đạt'} "
            report_str += f"({detail.get('score', 0)} điểm)\n"
            if detail.get('Note'):
                report_str += f"          └─ {detail.get('Note')}\n"
    else:
        report_str += "        (Đang xử lý hoặc chưa có dữ liệu)\n"
    
    report_str += "\n═══════════════════════════════════════════════════════════════\n"
    
    print("Đã có kết quả tổng hợp và audio segments.")
    progress(1, desc="Hoàn thành!")
    
    return report_str, segment_audio_outputs


# ============================================================
#                    GIAO DIỆN GRADIO
# ============================================================

with gr.Blocks(title="Demo Hệ thống Chấm điểm QA - Full", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎯 DEMO HỆ THỐNG CHẤM ĐIỂM QA - ĐÁNH GIÁ TOÀN DIỆN")
    gr.Markdown("### Đánh giá cả 2 tiêu chí: **Kỹ năng Giao tiếp** + **Kỹ năng Bán hàng**")
   
    segment_data_state = gr.State(value=[])

    with gr.Tabs():
        with gr.TabItem("📞 Đánh giá Toàn diện (2 Tiêu chí)"):
            gr.Markdown("## Tải file âm thanh và xem kết quả chấm điểm chi tiết")
            
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(
                        label="🎙️ Tải lên file âm thanh (.wav, .mp3)", 
                        type="filepath"
                    )
                    evaluate_btn = gr.Button(
                        "⚡ Bắt đầu Đánh giá Toàn diện", 
                        variant="primary", 
                        size="lg"
                    )
                    
                    gr.Markdown("""
                    ---
                    **Lưu ý:**
                    - Quá trình đánh giá có thể mất 2-5 phút
                    - Hệ thống sẽ tự động phân tích cả 2 tiêu chí
                    - Kết quả bao gồm điểm chi tiết và giải thích
                    """)

                with gr.Column(scale=2):
                    report_output = gr.Textbox(
                        label="📄 Báo cáo Đánh giá Toàn diện",
                        lines=35,
                        interactive=False,
                        placeholder="Kết quả đánh giá chi tiết sẽ hiển thị ở đây...\n\nBao gồm:\n- Kỹ năng Giao tiếp (2 điểm)\n- Kỹ năng Bán hàng (điểm tùy tiêu chí)\n- Tổng điểm cuối cùng"
                    )
                    
            gr.Markdown("---")
            gr.Markdown("### 🔊 Nghe lại các Audio Segment được tham chiếu")
            gr.Markdown("_Các đoạn audio được AI phân tích và đề cập trong báo cáo_")

            segment_outputs_components = []
            MAX_SEGMENTS_DISPLAY = 10
            
            with gr.Column(visible=False) as segment_display_area:
                for i in range(MAX_SEGMENTS_DISPLAY):
                    md = gr.Markdown(visible=False, elem_id=f"segment-md-{i}")
                    audio_player = gr.Audio(
                        visible=False, 
                        label=f"Segment {i+1}", 
                        elem_id=f"segment-audio-{i}"
                    )
                    segment_outputs_components.extend([md, audio_player])

            def update_ui_with_segments(report, segment_data):
                """Cập nhật UI với báo cáo và các audio segment"""
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
                                print(f"  - Lỗi: File audio cho segment {i+1} không tồn tại")
                                md_update = gr.Markdown(
                                    value=f"{desc}\n\n_(Lỗi: Không tìm thấy file audio)_", 
                                    visible=True
                                )
                        except Exception as e:
                            print(f"  - Lỗi khi xử lý dữ liệu segment {i+1}: {e}")
                            md_update = gr.Markdown(
                                value=f"**Segment {i+1}:** _Lỗi xử lý dữ liệu_", 
                                visible=True
                            )
                    
                    updates.extend([md_update, audio_update])

                area_update = gr.Column(visible=num_segments_found > 0)
                updates.append(area_update)

                print("update_ui_with_segments: Hoàn thành cập nhật UI.")
                return updates

            # Kết nối sự kiện
            evaluate_btn.click(
                fn=run_full_evaluation,
                inputs=[audio_input],
                outputs=[report_output, segment_data_state]
            ).then(
                fn=update_ui_with_segments,
                inputs=[report_output, segment_data_state],
                outputs=[report_output] + segment_outputs_components + [segment_display_area]
            )

        
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Đang khởi chạy Gradio App - Đánh giá Toàn diện")
    print("=" * 70)
    print("📋 Các tiêu chí đánh giá:")
    print("  1. Kỹ năng Giao tiếp (0-2 điểm)")
    print("  2. Kỹ năng Bán hàng (điểm tùy tiêu chí)")
    print("=" * 70)
    print("⚙️  Hãy đảm bảo file .env đã được cấu hình đúng.")
    
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"📁 Thư mục tạm cho audio segments: {temp_dir}")
    
    demo.launch(share=True, debug=True)# -*- coding: utf-8 -*-
import gradio as gr
import asyncio
import os
import re
import tempfile
from pydub import AudioSegment
import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_EVALUATE_FULL_ENDPOINT = f"{API_BASE_URL}/api/v1/evaluate/full"  # Endpoint mới
API_TASK_FULL_ENDPOINT = f"{API_BASE_URL}/api/v1/task/full"  # Endpoint lấy kết quả mới


async def get_full_evaluation_and_analysis(audio_bytes_or_path):
    """
    Gọi API để chấm CẢ 2 TIÊU CHÍ: Giao tiếp + Bán hàng
    
    Args:
        audio_bytes_or_path: Có thể là bytes hoặc đường dẫn file
    
    Returns:
        (evaluation_result, analysis_result)
    """
    print("Bắt đầu chấm điểm TOÀN DIỆN (2 tiêu chí)...")
    
    try:
        if isinstance(audio_bytes_or_path, bytes):
            print("Nhận audio dạng bytes, tạo file tạm...")
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
        
        async with httpx.AsyncClient(timeout=600.0) as client:  # Tăng timeout vì chấm 2 tiêu chí
            print(f"Đang upload file: {audio_file_path}")
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')}
                
                # Gọi API đánh giá toàn diện
                response = await client.post(API_EVALUATE_FULL_ENDPOINT, files=files)
                
                if response.status_code != 200:
                    error_msg = f"API trả về lỗi {response.status_code}: {response.text}"
                    print(f"Lỗi API: {error_msg}")
                    return {"error": error_msg}, {"segments": []}
                
                task_data = response.json()
                task_id = task_data.get("task_id")
                
                if not task_id:
                    return {"error": "Không nhận được task_id từ API"}, {"segments": []}
                
                print(f"✓ Đã upload file. Task ID: {task_id}")
            
            # Poll kết quả
            max_polls = 240  # Tăng lên vì xử lý 2 tiêu chí
            poll_count = 0
            
            while poll_count < max_polls:
                await asyncio.sleep(2)  # Poll mỗi 2s
                poll_count += 1
                
                result_response = await client.get(f"{API_TASK_FULL_ENDPOINT}/{task_id}")
                
                if result_response.status_code != 200:
                    print(f"Lỗi khi lấy kết quả: {result_response.status_code}")
                    continue
                
                result_data = result_response.json()
                status = result_data.get("status")
                
                print(f"Poll {poll_count}: Status = {status}")
                
                if status == "completed":
                    print("✓ API đã hoàn thành xử lý!")
                    
                    evaluation_result = {
                        # Kỹ năng Giao tiếp
                        "chao_xung_danh": result_data.get("chao_xung_danh", 0),
                        "ky_nang_noi": result_data.get("ky_nang_noi", 0),
                        "ky_nang_nghe": result_data.get("ky_nang_nghe", 0),
                        "thai_do": result_data.get("thai_do", 0),
                        "communication_score": result_data.get("communication_score", 0),
                        "muc_loi": result_data.get("muc_loi", "Không"),
                        "ly_do_giao_tiep": result_data.get("ly_do_giao_tiep", ""),
                        
                        # Kỹ năng Bán hàng
                        "sales_score": result_data.get("sales_score", 0),
                        "sales_criteria_details": result_data.get("sales_criteria_details", []),
                        
                        # Tổng hợp
                        "total_score": result_data.get("total_score", 0),
                    }
                    
                    analysis_result = {
                        "segments": result_data.get("segments", []),
                        "metadata": result_data.get("metadata", {})
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
    """Cắt một đoạn audio và lưu vào file tạm"""
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


async def run_full_evaluation(audio_file_path, progress=gr.Progress(track_tqdm=True)):
    """Chạy đánh giá toàn diện cả 2 tiêu chí"""
    
    report_str = "Chưa có báo cáo."
    segment_audio_outputs = []
    
    # Tạo và dọn dẹp thư mục tạm
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if os.path.isfile(item_path) and item.startswith("segment_") and item.endswith(".wav"):
                try: 
                    os.remove(item_path)
                    print(f"Đã xóa file cũ: {item_path}")
                except OSError as e: 
                    print(f"Không thể xóa file cũ {item_path}: {e}")
    except Exception as e: 
        print(f"Không thể tạo/dọn dẹp thư mục tạm {temp_dir}: {e}")
    
    if not audio_file_path or not os.path.exists(audio_file_path):
        print(f"Lỗi: File audio không hợp lệ: {audio_file_path}")
        return "Vui lòng tải lên một file âm thanh hợp lệ.", []
    
    progress(0, desc="Bắt đầu xử lý...")
    
    try:
        print(f"Sử dụng file audio: {audio_file_path}")
        with open(audio_file_path, 'rb') as f: 
            audio_bytes_for_analysis = f.read()
        progress(0.1, desc="Đã đọc file audio...")
    except Exception as e:
        print(f"Lỗi đọc file: {str(e)}")
        return f"Lỗi đọc file: {str(e)}", []
    
    progress(0.2, desc="Đang chạy đánh giá toàn diện (2 tiêu chí)...")
    (eval_result, analysis_result) = await get_full_evaluation_and_analysis(audio_bytes_for_analysis)
    
    if "error" in eval_result:
        return f"LỖI: {eval_result['error']}", []
    
    # Lấy điểm số
    comm_score = eval_result.get('communication_score', 0)
    sales_score = eval_result.get('sales_score', 0)
    total_score = eval_result.get('total_score', 0)
    
    # Xử lý segments được tham chiếu
    llm_reason = eval_result.get('ly_do_giao_tiep', '')
    referenced_segments_info = []
    
    if llm_reason and analysis_result and isinstance(analysis_result.get('segments'), list):
        found_indices = set()
        try:
             matches = re.findall(r'segment\s*(\d+)', llm_reason, re.IGNORECASE)
             found_indices = set(map(int, matches))
             print(f"Tìm thấy tham chiếu đến các segment index: {found_indices}")
        except Exception as e: 
            print(f"Lỗi khi parse segment indices: {e}")
        
        all_segments = analysis_result.get('segments', [])
        for index_from_1 in found_indices:
            index_from_0 = index_from_1 - 1
            if 0 <= index_from_0 < len(all_segments):
                segment_data = all_segments[index_from_0]
                start = segment_data.get('start_time')
                end = segment_data.get('end_time')
                text_preview = str(segment_data.get('text', ''))[:50]
                if len(str(segment_data.get('text', ''))) > 50:
                    text_preview += "..."
                    
                if start is not None and end is not None:
                    segment_audio_path = extract_and_save_segment(audio_file_path, start, end, temp_dir)
                    if segment_audio_path:
                        segment_description = f"**Segment {index_from_1} ({start:.2f}s - {end:.2f}s):** \"{text_preview}\""
                        referenced_segments_info.append((segment_description, segment_audio_path))
    
    try:
        referenced_segments_info.sort(key=lambda x: int(re.search(r'Segment (\d+)', x[0]).group(1)) if re.search(r'Segment (\d+)', x[0]) else 0)
    except Exception as e: 
        print(f"Lỗi khi sắp xếp segments: {e}")
    
    segment_audio_outputs = referenced_segments_info
    
    # Xây dựng báo cáo
    report_str = f"""
╔════════════════════════════════════════════════════════════════╗
║          BÁO CÁO ĐÁNH GIÁ TOÀN DIỆN - 2 TIÊU CHÍ              ║
╚════════════════════════════════════════════════════════════════╝

📊 TỔNG QUAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎯 TỔNG ĐIỂM CUỐI CÙNG: {total_score:.2f} điểm
    
    
═══════════════════════════════════════════════════════════════

 1️⃣  TIÊU CHÍ 1: KỸ NĂNG GIAO TIẾP
─────────────────────────────────────────────────────────────────
    💯 Điểm: {comm_score:.2f}/2.0
    
    📋 Điểm thành phần (0/1):
        • Chào/Xưng danh:  {eval_result.get('chao_xung_danh', 'N/A')}/1
        • Kỹ năng nói:     {eval_result.get('ky_nang_noi', 'N/A')}/1
        • Kỹ năng nghe:    {eval_result.get('ky_nang_nghe', 'N/A')}/1
        • Thái độ:         {eval_result.get('thai_do', 'N/A')}/1
    
    ⚠️  Mức lỗi: {eval_result.get('muc_loi', 'N/A')}
    
    📝 Lý do chi tiết:
    {llm_reason}


═══════════════════════════════════════════════════════════════

 2️⃣  TIÊU CHÍ 2: KỸ NĂNG BÁN HÀNG
─────────────────────────────────────────────────────────────────
    💯 Điểm: {sales_score if sales_score is not None else 'Đang xử lý...'}
    
    📋 Chi tiết các tiêu chí bán hàng:
"""
    
    # Thêm chi tiết bán hàng nếu có
    sales_details = eval_result.get('sales_criteria_details', [])
    if sales_details:
        for detail in sales_details:
            report_str += f"        • {detail.get('criteria_name', 'N/A')}: "
            report_str += f"{'✅ Đạt' if detail.get('status') == 1 else '❌ Chưa đạt'} "
            report_str += f"({detail.get('score', 0)} điểm)\n"
            if detail.get('Note'):
                report_str += f"          └─ {detail.get('Note')}\n"
    else:
        report_str += "        (Đang xử lý hoặc chưa có dữ liệu)\n"
    
    report_str += "\n═══════════════════════════════════════════════════════════════\n"
    
    print("Đã có kết quả tổng hợp và audio segments.")
    progress(1, desc="Hoàn thành!")
    
    return report_str, segment_audio_outputs


# ============================================================
#                    GIAO DIỆN GRADIO
# ============================================================

with gr.Blocks(title="Demo Hệ thống Chấm điểm QA - Full", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎯 DEMO HỆ THỐNG CHẤM ĐIỂM QA - ĐÁNH GIÁ TOÀN DIỆN")
    gr.Markdown("### Đánh giá cả 2 tiêu chí: **Kỹ năng Giao tiếp** + **Kỹ năng Bán hàng**")
   
    segment_data_state = gr.State(value=[])

    with gr.Tabs():
        with gr.TabItem("📞 Đánh giá Toàn diện (2 Tiêu chí)"):
            gr.Markdown("## Tải file âm thanh và xem kết quả chấm điểm chi tiết")
            
            with gr.Row():
                with gr.Column(scale=1):
                    audio_input = gr.Audio(
                        label="🎙️ Tải lên file âm thanh (.wav, .mp3)", 
                        type="filepath"
                    )
                    evaluate_btn = gr.Button(
                        "⚡ Bắt đầu Đánh giá Toàn diện", 
                        variant="primary", 
                        size="lg"
                    )
                    
                    gr.Markdown("""
                    ---
                    **Lưu ý:**
                    - Quá trình đánh giá có thể mất 2-5 phút
                    - Hệ thống sẽ tự động phân tích cả 2 tiêu chí
                    - Kết quả bao gồm điểm chi tiết và giải thích
                    """)

                with gr.Column(scale=2):
                    report_output = gr.Textbox(
                        label="📄 Báo cáo Đánh giá Toàn diện",
                        lines=35,
                        interactive=False,
                        placeholder="Kết quả đánh giá chi tiết sẽ hiển thị ở đây...\n\nBao gồm:\n- Kỹ năng Giao tiếp (2 điểm)\n- Kỹ năng Bán hàng (điểm tùy tiêu chí)\n- Tổng điểm cuối cùng"
                    )
                    
            gr.Markdown("---")
            gr.Markdown("### 🔊 Nghe lại các Audio Segment được tham chiếu")
            gr.Markdown("_Các đoạn audio được AI phân tích và đề cập trong báo cáo_")

            segment_outputs_components = []
            MAX_SEGMENTS_DISPLAY = 10
            
            with gr.Column(visible=False) as segment_display_area:
                for i in range(MAX_SEGMENTS_DISPLAY):
                    md = gr.Markdown(visible=False, elem_id=f"segment-md-{i}")
                    audio_player = gr.Audio(
                        visible=False, 
                        label=f"Segment {i+1}", 
                        elem_id=f"segment-audio-{i}"
                    )
                    segment_outputs_components.extend([md, audio_player])

            def update_ui_with_segments(report, segment_data):
                """Cập nhật UI với báo cáo và các audio segment"""
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
                                print(f"  - Lỗi: File audio cho segment {i+1} không tồn tại")
                                md_update = gr.Markdown(
                                    value=f"{desc}\n\n_(Lỗi: Không tìm thấy file audio)_", 
                                    visible=True
                                )
                        except Exception as e:
                            print(f"  - Lỗi khi xử lý dữ liệu segment {i+1}: {e}")
                            md_update = gr.Markdown(
                                value=f"**Segment {i+1}:** _Lỗi xử lý dữ liệu_", 
                                visible=True
                            )
                    
                    updates.extend([md_update, audio_update])

                area_update = gr.Column(visible=num_segments_found > 0)
                updates.append(area_update)

                print("update_ui_with_segments: Hoàn thành cập nhật UI.")
                return updates

            # Kết nối sự kiện
            evaluate_btn.click(
                fn=run_full_evaluation,
                inputs=[audio_input],
                outputs=[report_output, segment_data_state]
            ).then(
                fn=update_ui_with_segments,
                inputs=[report_output, segment_data_state],
                outputs=[report_output] + segment_outputs_components + [segment_display_area]
            )

        
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Đang khởi chạy Gradio App - Đánh giá Toàn diện")
    print("=" * 70)
    print("📋 Các tiêu chí đánh giá:")
    print("  1. Kỹ năng Giao tiếp (0-2 điểm)")
    print("  2. Kỹ năng Bán hàng (điểm tùy tiêu chí)")
    print("=" * 70)
    print("⚙️  Hãy đảm bảo file .env đã được cấu hình đúng.")
    
    temp_dir = os.path.join(tempfile.gettempdir(), "gradio_audio_segments")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"📁 Thư mục tạm cho audio segments: {temp_dir}")
    
    demo.launch(share=True, debug=True)