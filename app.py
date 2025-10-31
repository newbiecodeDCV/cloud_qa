# -*- coding: utf-8 -*-
import gradio as gr
import asyncio
import os
import tempfile
from pydub import AudioSegment
from dotenv import load_dotenv


from src.qa_communicate.audio_processing.qa import call_qa_api
from src.qa_communicate.core.utils import create_task_id
load_dotenv()


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
        print(f"✓ Đã lưu segment: {output_path} ({start_sec}s - {end_sec}s)")
        return output_path
    except Exception as e:
        print(f"✗ Lỗi khi cắt audio segment ({start_sec}-{end_sec}): {e}")
        return None


async def process_audio_and_evaluate(audio_file_path, progress=gr.Progress()):
    """Xử lý audio qua API"""
    
    
    report_str = "Đang xử lý..."
    
    
    if not audio_file_path or not os.path.exists(audio_file_path):
        return "❌ Vui lòng tải lên một file âm thanh hợp lệ."
    
    progress(0.1, desc="📁 Đang đọc file audio...")
    
    try:
        with open(audio_file_path, 'rb') as f:
            audio_bytes = f.read()
    except Exception as e:
        return f"❌ Lỗi đọc file: {str(e)}"
    
    
    
    task_id = create_task_id(audio_bytes)
    
    progress(0.3, desc="🔄 Đang gửi yêu cầu đến API...")
    
    
    try:
        result = await call_qa_api(
            audio_bytes=audio_bytes,
            task_id=task_id,
            max_poll_seconds=120.0,
            poll_interval_seconds=2.0,
            verbose=True
        )
    except Exception as e:
        return f"❌ Lỗi khi gọi API: {str(e)}"
    
    progress(0.8, desc="📊 Đang xử lý kết quả...")
    
    
    if result.get('status') != 1:
        error_msg = result.get('message', 'Không xác định')
        return f"❌ Lỗi từ API: {error_msg}"
    
    
    dialogue_report = result.get('dialogue', '')
    
    
    report_lines = []
    report_lines.append("╔════════════════════════════════════════════════════════════════╗")
    report_lines.append("║              📊 BÁO CÁO ĐÁNH GIÁ CUỘC GỌI QA                  ║")
    report_lines.append("╚════════════════════════════════════════════════════════════════╝")
    report_lines.append("")
    
    if dialogue_report:
     
        if isinstance(dialogue_report, str):
            report_lines.append(dialogue_report)
        
        else:
            report_lines.append(str(dialogue_report))
    else:
        report_lines.append("⚠️ API trả về thành công nhưng không có báo cáo.")
    
    report_lines.append("")
    report_lines.append("═══════════════════════════════════════════════════════════════")
    report_lines.append("✅ Hoàn tất!")
    
    report_str = "\n".join(report_lines)
    
    progress(1.0, desc="✅ Hoàn thành!")
    
    return report_str



custom_css = """
.gradio-container {
    max-width: 1200px !important;
    margin: auto !important;
}
.report-box textarea {
    font-family: 'Courier New', monospace !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}
.main-header {
    text-align: center;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px;
    margin-bottom: 30px;
}
.analyze-button {
    width: 100% !important;
    height: 60px !important;
    font-size: 18px !important;
    font-weight: bold !important;
}
.info-box {
    background: #f0f7ff;
    padding: 15px;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    margin-top: 15px;
}
"""

with gr.Blocks(title="QA Audio Processor", theme=gr.themes.Soft(), css=custom_css) as demo:
    
    # Header
    with gr.Row(elem_classes="main-header"):
        gr.Markdown("""
        # 🎯 HỆ THỐNG XỬ LÝ AUDIO QA
        ### Phân tích cuộc gọi tự động với AI
        """)
    
    with gr.Row():
        # Cột trái - Input
        with gr.Column(scale=2):
            gr.Markdown("## 📤 Tải lên file âm thanh")
            
            audio_input = gr.Audio(
                label="🎙️ Chọn file audio (.wav, .mp3, .m4a)",
                type="filepath",
                elem_classes="audio-input"
            )
            
            analyze_btn = gr.Button(
                "🚀 Bắt đầu Xử lý",
                variant="primary",
                size="lg",
                elem_classes="analyze-button"
            )
            
            with gr.Group(elem_classes="info-box"):
                gr.Markdown("""
                ### 📋 Hướng dẫn sử dụng:
                
                1. 📁 **Tải file**: Chọn file audio từ máy tính
                2. ▶️ **Bắt đầu**: Nhấn nút "Bắt đầu Xử lý"
                3. ⏳ **Chờ đợi**: Quá trình xử lý 1-2 phút
                4. ✅ **Kết quả**: Xem báo cáo bên phải
                
                ---
                
                
                """)
        
        
        with gr.Column(scale=3):
            gr.Markdown("## 📊 Kết quả Xử lý")
            
            report_output = gr.Textbox(
                label="📄 Báo cáo Chi tiết",
                lines=25,
                max_lines=40,
                interactive=False,
                show_copy_button=True,
                placeholder="🔄 Kết quả xử lý sẽ hiển thị tại đây...\n\n"
                           "Sau khi tải file và nhấn 'Bắt đầu Xử lý',\n"
                           "hệ thống sẽ:\n\n"
                           "• Gửi audio đến API\n"
                           "• Poll kết quả định kỳ\n"
                           "• Hiển thị thông tin chi tiết\n\n"
                           "Vui lòng đợi trong giây lát...",
                elem_classes="report-box"
            )
            
            gr.Markdown("""
            <div style="background: #e8f5e9; padding: 10px; border-radius: 5px; margin-top: 10px;">
                💡 <b>Lưu ý:</b> Bạn có thể sao chép kết quả bằng nút Copy ở góc trên bên phải
            </div>
            """)
    
    # Kết nối events
    analyze_btn.click(
        fn=process_audio_and_evaluate,
        inputs=[audio_input],
        outputs=[report_output]
    )
    
    # Footer
    gr.Markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 13px; padding: 20px;">
        <p><b>🔧 Powered by AI Speech Recognition API</b></p>
        <p>⚡ Fast • 🎯 Accurate • 🔒 Secure</p>
    </div>
    """)


if __name__ == "__main__":
    print("=" * 80)
    print("🚀 KHỞI ĐỘNG HỆ THỐNG XỬ LÝ AUDIO QA")
    print("=" * 80)
    print("📋 Thông tin:")
    print("   • API: call_qa_api từ qa.py")
    print("   • Max timeout: 120 giây")
    print("   • Poll interval: 2 giây")
    print("=" * 80)
    print("⏳ Đang khởi động Gradio...")
    print("=" * 80)
    
    demo.launch(
        share=True,
        debug=False,
        server_name="0.0.0.0",
        server_port=7860
    )