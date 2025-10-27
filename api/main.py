from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import sys
from pathlib import Path
import json
from datetime import datetime

# Thêm thư mục src vào Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.audio_processing.analysis import extract_features
    from src.evaluation.evaluator import get_qa_evaluation
except ImportError:
    raise ImportError("Không tìm thấy module trong src/. Hãy chạy từ thư mục gốc.")

app = FastAPI(title="QA Cloud API", version="1.0")

RESULTS_DIR = Path("results") / "score"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/api/v1/evaluate-communication")
async def evaluate_communication_skill(audio_file: UploadFile = File(...)):
    if not audio_file.filename.endswith(('.wav', '.mp3', '.m4a')):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file âm thanh (.wav, .mp3, .m4a)")

    try:
        # Đọc nội dung file
        audio_bytes = await audio_file.read()

        # Gọi hàm phân tích âm học
        analysis_result = await extract_features(audio_bytes)
        if analysis_result.get('status') != 1:
            raise HTTPException(status_code=500, detail=analysis_result.get('message'))

        # Gửi dữ liệu cho LLM để chấm điểm
        data_for_llm = {
            'metadata': analysis_result.get('metadata'),
            'segments': analysis_result.get('segments')
        }
        evaluation_result = await get_qa_evaluation(data_for_llm)

        if not evaluation_result or "error" in evaluation_result:
            raise HTTPException(status_code=500, detail="Lỗi khi chấm điểm từ LLM.")

        # Trích xuất điểm số và nhận xét (giả sử có các trường này)
        chao_xung_danh = evaluation_result.get('chao_xung_danh', 1.0)
        ky_nang_noi = evaluation_result.get('ky_nang_noi', 1.0),
        ky_nang_nghe = evaluation_result.get('ky_nang_nghe', 1.0),
        thai_do = evaluation_result.get('thai_do',1.0),
        muc_loi = evaluation_result.get('muc_loi',"M1")
        ly_do = evaluation_result.get('ly_do',"Không có lý do")

        # Tạo kết quả trả về
        result = {
            "chao_xung_danh": float(chao_xung_danh),
            "ky_nang_noi": float(ky_nang_noi),
            "ky_nang_nghe": float(ky_nang_nghe),
            "thai_do": float(thai_do),
            "muc_loi": float(muc_loi),
            "ly_do": float(ly_do)
        }

        # Lưu kết quả
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"comm_eval_{Path(audio_file.filename).stem}_{timestamp}.json"
        output_path = RESULTS_DIR / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        return JSONResponse(content=result, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")