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
