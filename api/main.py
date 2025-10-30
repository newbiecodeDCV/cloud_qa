import sys
import io


from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any,List 
import asyncio
import sys
from pathlib import Path
import json
from datetime import datetime
import logging
import uuid


file_handler = logging.FileHandler('api_server.log', encoding='utf-8')
from api.langsmith_integration import (
    trace_chain, 
    trace_llm, 
    trace_tool,
    log_feedback,
    add_metadata,
    add_tags,
    LANGSMITH_ENABLED
)
stream_handler = None
if sys.platform == 'win32':
    stream_handler = logging.StreamHandler(
        io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    )
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
else:
    stream_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        stream_handler
    ]
)
logger = logging.getLogger(__name__)



project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.qa_communicate.audio_processing.analysis    import extract_features
    from src.qa_communicate.evaluation.evaluator   import get_qa_evaluation
    from src.qa_communicate.database.database import init_db, get_db
    from src.qa_communicate.database.repository import EvaluationRepository, SegmentRepository
    from src.qa_communicate.core.utils import hash_str
    from src.qa_communicate.core.utils import create_task_id
    logger.info("Import thanh cong cac module tu src/")
except ImportError as e:
    logger.error(f"Loi import: {e}")
    raise ImportError("Khong tim thay module trong src/.")

from api.main_evaluator import QAMainEvaluator
import os
from dotenv import load_dotenv

load_dotenv()

@trace_tool(name="acoustic_feature_extraction")
async def extract_features_tracked(task_id: str, audio_bytes: bytes):
    """Wrapper cho extract_features với LangSmith tracking"""
    logger.info(f"[{task_id}] Đang phân tích acoustic features...")
    add_tags("acoustic", "feature-extraction")
    
    analysis_result = await extract_features(audio_bytes)
    
    if analysis_result.get('status') == 1:
        log_feedback(
            key="acoustic_success",
            score=1.0,
            comment=f"Duration: {analysis_result.get('metadata', {}).get('duration')}s"
        )
        logger.info(f"[{task_id}] ✓ Phân tích acoustic thành công")
    else:
        log_feedback(
            key="acoustic_error",
            score=0.0,
            comment=analysis_result.get('message', 'Unknown error')
        )
    
    return analysis_result


@trace_llm(name="communication_evaluation", model="gpt-4")
async def evaluate_communication_tracked(task_id: str, data_for_llm: dict):
    """Wrapper cho get_qa_evaluation với LangSmith tracking"""
    logger.info(f"[{task_id}] Đang chấm Kỹ năng Giao tiếp...")
    add_tags("communication", "llm-evaluation")
    
    evaluation_result = await get_qa_evaluation(data_for_llm)
    
    if evaluation_result and "error" not in evaluation_result:
        # Tính điểm
        chao_xung_danh = int(evaluation_result.get('chao_xung_danh', 0))
        ky_nang_noi = int(evaluation_result.get('ky_nang_noi', 0))
        ky_nang_nghe = int(evaluation_result.get('ky_nang_nghe', 0))
        thai_do = int(evaluation_result.get('thai_do', 0))
        communication_score = 0.2 * (chao_xung_danh + ky_nang_noi) + \
                            0.8 * (ky_nang_nghe + thai_do)
        
        log_feedback(
            key="communication_score",
            score=communication_score / 2.0,  # Normalize to 0-1
            comment=f"Score: {communication_score}/2.0"
        )
        logger.info(f"[{task_id}] ✓ Chấm giao tiếp: {communication_score}/2.0")
    else:
        log_feedback(
            key="communication_error",
            score=0.0,
            comment=evaluation_result.get('error', 'Unknown error') if evaluation_result else 'No response'
        )
    
    return evaluation_result

@trace_chain(name="sales_evaluation")
async def evaluate_sales_tracked(task_id: str, audio_bytes: bytes):
    """Wrapper cho sales evaluation với LangSmith tracking"""
    logger.info(f"[{task_id}] Đang chấm Kỹ năng Bán hàng...")
    add_tags("sales", "script-matching")
    
    try:
        sales_detail, sales_score = await qa_main_evaluator.evaluate_sale_skills(
            audio_bytes=audio_bytes,
            task_id=int(task_id)
        )
        
        log_feedback(
            key="sales_score",
            score=sales_score / 10.0,  # Normalize nếu max score là 10
            comment=f"Sales score: {sales_score}"
        )
        logger.info(f"[{task_id}] ✓ Chấm bán hàng: {sales_score}")
        
        return sales_detail, sales_score
        
    except Exception as e:
        log_feedback(
            key="sales_error",
            score=0.0,
            comment=f"Error: {str(e)}"
        )
        logger.error(f"[{task_id}] Lỗi chấm bán hàng: {e}")
        raise


qa_main_evaluator = QAMainEvaluator(
    gpt_model=os.getenv("MODEL_NAME", "gpt-4.1-mini"),
    csv_path ="/home/hiennt/cloud-callcenter-qa/src/qa_sales/modules/databases/salescript.tsv",
    eval_prompt_template="src/qa_sales/modules/prompt_templates/evaluate_script.txt",
    preprocess_prompt_template="src/qa_sales/modules/prompt_templates/preprocess.txt",
    classify_prompt_template="src/qa_sales/modules/prompt_templates/classify_utterances.txt",
    db_path="/home/hiennt/cloud-callcenter-qa/src/qa_sales/modules/databases/salescript_db"
)

# Khoi tao FastAPI
app = FastAPI(
    title="Call Center QA API",
    description="API danh gia chat luong cuoc goi Sales",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production nen gioi han domain cu the
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RESULTS_DIR = Path("results") / "score"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


task_storage: Dict[str, Dict[str, Any]] = {}



class FullEvaluationResponse(BaseModel):
    """Response model cho kết quả đánh giá tổng hợp (cả 2 tiêu chí)"""
    task_id: str = Field(..., description="ID tác vụ")
    status: str = Field(..., description="pending | processing | completed | failed")
    
    # Tiêu chí 1: Kỹ năng Giao tiếp
    communication_score: Optional[float] = Field(None, ge=0, le=2, description="Điểm giao tiếp (0-2)")
    chao_xung_danh: Optional[int] = Field(None, ge=0, le=1)
    ky_nang_noi: Optional[int] = Field(None, ge=0, le=1)
    ky_nang_nghe: Optional[int] = Field(None, ge=0, le=1)
    thai_do: Optional[int] = Field(None, ge=0, le=1)
    muc_loi: Optional[str] = Field(None, description="Mức lỗi")
    ly_do_giao_tiep: Optional[str] = Field(None, description="Lý do đánh giá giao tiếp")
    
    # Tiêu chí 2: Kỹ năng Bán hàng
    sales_score: Optional[float] = Field(None, description="Điểm bán hàng")
    sales_criteria_details: Optional[List[Dict[str, Any]]] = Field(None, description="Chi tiết từng tiêu chí bán hàng")
    
    # Tổng hợp
    total_score: Optional[float] = Field(None, description="Tổng điểm (Giao tiếp + Bán hàng)")
    
    metadata: Optional[Dict[str, Any]] = Field(None)
    segments: Optional[List[Dict[str, Any]]] = Field(None)
    error_message: Optional[str] = Field(None)
    created_at: Optional[str] = Field(None)
    completed_at: Optional[str] = Field(None)



class EvaluationResponse(BaseModel):
    """Response model cho ket qua danh gia"""
    task_id: str = Field(..., description="ID tac vu de tracking")
    status: str = Field(..., description="pending | processing | completed | failed")
    chao_xung_danh: Optional[int] = Field(None, ge=0, le=1, description="Diem chao/xung danh (0 hoac 1)")
    ky_nang_noi: Optional[int] = Field(None, ge=0, le=1, description="Diem ky nang noi (0 hoac 1)")
    ky_nang_nghe: Optional[int] = Field(None, ge=0, le=1, description="Diem ky nang nghe (0 hoac 1)")
    thai_do: Optional[int] = Field(None, ge=0, le=1, description="Diem thai do (0 hoac 1)")
    tong_diem: Optional[float] = Field(None, ge=0, le=2, description="Tong diem (0-2)")
    muc_loi: Optional[str] = Field(None, description="Muc loi: Khong | M1 | M2 | M3")
    ly_do: Optional[str] = Field(None, description="Ly do chi tiet")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata cuoc goi")
    error_message: Optional[str] = Field(None, description="Thong bao loi neu co")
    created_at: Optional[str] = Field(None, description="Thoi gian tao task")
    completed_at: Optional[str] = Field(None, description="Thoi gian hoan thanh")
    segments: Optional[List[Dict[str, Any]]] = Field(None, description="Du lieu cac doan am thanh")
    

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "chao_xung_danh": 1,
                "ky_nang_noi": 1,
                "ky_nang_nghe": 0,
                "thai_do": 1,
                "tong_diem": 1.2,
                "muc_loi": "M1",
                "ly_do": "- Chao hoi tot\n- Noi hoi nhanh\n- Chua lang nghe tot",
                "metadata": {
                    "duration": 120.5,
                    "turns": 15,
                    "ratio_sales": 0.65
                }
            }
        }


class TaskStatusResponse(BaseModel):
    """Response cho trang thai task"""
    task_id: str
    status: str
    message: str
    progress: Optional[float] = Field(None, ge=0, le=1, description="Tien do 0-1")




def validate_audio_file(filename: str) -> tuple[bool, str]:
    """Validate audio file format"""
    allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        return False, f"Dinh dang file khong duoc ho tro. Chi chap nhan: {', '.join(allowed_extensions)}"
    
    return True, "OK"





def save_result_to_file(task_id: str, result: Dict[str, Any]) -> Path:
    """Luu ket qua vao file JSON"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"evaluation_{task_id[:8]}_{timestamp}.json"
    output_path = RESULTS_DIR / output_filename
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        logger.info(f" Da luu ket qua vao: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f" Loi luu file: {e}")
        raise

@trace_chain(name="communication_evaluation_pipeline")
async def process_evaluation_task(task_id: str, audio_bytes: bytes):
    """Background task de xu ly danh gia cuoc goi"""
    
    add_metadata({
        "task_id": task_id,
        "audio_size_mb": len(audio_bytes) / (1024 * 1024),
        "timestamp": datetime.now().isoformat()
    })
    add_tags("production", "communication-only")
    
    with get_db() as db:
        try:
    
            EvaluationRepository.update_status(db, task_id, 'processing')
            logger.info(f"[{task_id}] Bat dau xu ly...")
            
           
            logger.info(f"[{task_id}] Dang phan tich acoustic features...")
            analysis_result = await extract_features_tracked(task_id, audio_bytes)
            
            if analysis_result.get('status') != 1:
                error_msg = analysis_result.get('message', 'Loi khong xac dinh')
                logger.error(f"[{task_id}] Loi phan tich: {error_msg}")
                EvaluationRepository.update_error(db, task_id, f"Loi phan tich audio: {error_msg}")
                return
            
            logger.info(f"[{task_id}] ✓ Phan tich acoustic thanh cong")
            
           
            logger.info(f"[{task_id}] Dang cham diem bang LLM...")
            data_for_llm = {
                'metadata': analysis_result.get('metadata'),
                'segments': analysis_result.get('segments')
            }
            
            evaluation_result = await evaluate_communication_tracked(task_id, data_for_llm)
            
            if not evaluation_result or "error" in evaluation_result:
                error_msg = evaluation_result.get('error', 'Loi khong xac dinh') if evaluation_result else 'Khong nhan duoc response'
                logger.error(f"[{task_id}] Loi LLM: {error_msg}")
                EvaluationRepository.update_error(db, task_id, f"Loi cham diem LLM: {error_msg}")
                return
            
            logger.info(f"[{task_id}] ✓ Cham diem thanh cong")
            
            
            chao_xung_danh = int(evaluation_result.get('chao_xung_danh', 0))
            ky_nang_noi = int(evaluation_result.get('ky_nang_noi', 0))
            ky_nang_nghe = int(evaluation_result.get('ky_nang_nghe', 0))
            thai_do = int(evaluation_result.get('thai_do', 0))
            tong_diem = 0.2 * (chao_xung_danh + ky_nang_noi) + 0.8 * (ky_nang_nghe + thai_do)
            
        
            result_data = {
                'chao_xung_danh': chao_xung_danh,
                'ky_nang_noi': ky_nang_noi,
                'ky_nang_nghe': ky_nang_nghe,
                'thai_do': thai_do,
                'tong_diem': tong_diem,
                'muc_loi': str(evaluation_result.get('muc_loi', 'Khong')),
                'ly_do': str(evaluation_result.get('ly_do', '')),
                'metadata': analysis_result.get('metadata'),
                'segments': analysis_result.get('segments')
            }
            
            
            evaluation = EvaluationRepository.update_result(db, task_id, result_data)
            
            
            if evaluation and analysis_result.get('segments'):
                SegmentRepository.create_bulk(
                    db, 
                    evaluation.id, 
                    analysis_result.get('segments')
                )
            
            
            try:
                save_result_to_file(task_id, result_data)
            except Exception as e:
                logger.warning(f"[{task_id}] Khong the luu file JSON: {e}")
            
            logger.info(f"[{task_id}] ✓ Hoan thanh. Diem: {tong_diem}/2")
            
        except Exception as e:
            logger.error(f"[{task_id}] ✗ Loi he thong: {e}", exc_info=True)
            EvaluationRepository.update_error(db, task_id, f"Loi he thong: {str(e)}")

@trace_chain(name="full_evaluation_pipeline")
async def process_full_evaluation_task(task_id: str, audio_bytes: bytes):
    """Background task đánh giá cả 2 tiêu chí - WITH LANGSMITH"""
    
    # Thêm metadata
    add_metadata({
        "task_id": task_id,
        "audio_size_mb": len(audio_bytes) / (1024 * 1024),
        "timestamp": datetime.now().isoformat()
    })
    add_tags("production", "full-evaluation", "communication+sales")
    
    with get_db() as db:
        try:
            EvaluationRepository.update_status(db, task_id, 'processing')
            logger.info(f"[{task_id}] Bắt đầu đánh giá tổng hợp (2 tiêu chí)...")
            
            # 1. Phân tích acoustic
            analysis_result = await extract_features_tracked(task_id, audio_bytes)
            
            if analysis_result.get('status') != 1:
                error_msg = analysis_result.get('message', 'Lỗi không xác định')
                logger.error(f"[{task_id}] Lỗi phân tích: {error_msg}")
                EvaluationRepository.update_error(db, task_id, f"Lỗi phân tích audio: {error_msg}")
                return
            
            # 2. Đánh giá giao tiếp
            data_for_llm = {
                'metadata': analysis_result.get('metadata'),
                'segments': analysis_result.get('segments')
            }
            
            evaluation_result = await evaluate_communication_tracked(task_id, data_for_llm)
            
            if not evaluation_result or "error" in evaluation_result:
                error_msg = evaluation_result.get('error', 'Lỗi không xác định') if evaluation_result else 'Không nhận được response'
                logger.error(f"[{task_id}] Lỗi chấm giao tiếp: {error_msg}")
                EvaluationRepository.update_error(db, task_id, f"Lỗi chấm giao tiếp: {error_msg}")
                return
            
            # Tính điểm giao tiếp
            chao_xung_danh = int(evaluation_result.get('chao_xung_danh', 0))
            ky_nang_noi = int(evaluation_result.get('ky_nang_noi', 0))
            ky_nang_nghe = int(evaluation_result.get('ky_nang_nghe', 0))
            thai_do = int(evaluation_result.get('thai_do', 0))
            communication_score = 0.2 * (chao_xung_danh + ky_nang_noi) + \
                                 0.8 * (ky_nang_nghe + thai_do)
            
            logger.info(f"[{task_id}] ✓ Chấm giao tiếp: {communication_score}/2.0")
            
            # 3. Đánh giá bán hàng
            try:
                sales_detail, sales_score = await evaluate_sales_tracked(task_id, audio_bytes)
                logger.info(f"[{task_id}] ✓ Chấm bán hàng: {sales_score}")
            except Exception as sales_error:
                logger.error(f"[{task_id}] Lỗi chấm bán hàng: {sales_error}")
                sales_score = 0.0
                sales_detail = f"Lỗi: {str(sales_error)}"
            
            # 4. Tính tổng điểm
            total_score = communication_score + sales_score
            
            # 5. Lưu kết quả
            result_data = {
                'chao_xung_danh': chao_xung_danh,
                'ky_nang_noi': ky_nang_noi,
                'ky_nang_nghe': ky_nang_nghe,
                'thai_do': thai_do,
                'tong_diem': total_score,
                'muc_loi': str(evaluation_result.get('muc_loi', 'Không')),
                'ly_do': f"=== GIAO TIẾP ===\n{evaluation_result.get('ly_do', '')}\n\n=== BÁN HÀNG ===\n{sales_detail}",
                'metadata': analysis_result.get('metadata'),
                'segments': analysis_result.get('segments')
            }
            
            evaluation = EvaluationRepository.update_result(db, task_id, result_data)
            
            if evaluation and analysis_result.get('segments'):
                SegmentRepository.create_bulk(
                    db, 
                    evaluation.id, 
                    analysis_result.get('segments')
                )
            
            try:
                save_result_to_file(task_id, result_data)
            except Exception as e:
                logger.warning(f"[{task_id}] Không thể lưu file JSON: {e}")
            
            # Log final success
            log_feedback(
                key="total_score",
                score=total_score / (communication_score + 10.0),  # Normalize
                comment=f"Communication: {communication_score}/2.0, Sales: {sales_score}, Total: {total_score}"
            )
            logger.info(f"[{task_id}] ✓ Hoàn thành. Giao tiếp: {communication_score}/2.0, Bán hàng: {sales_score}, Tổng: {total_score}")
            
        except Exception as e:
            logger.error(f"[{task_id}] ✗ Lỗi hệ thống: {e}", exc_info=True)
            log_feedback(
                key="pipeline_error",
                score=0.0,
                comment=f"System error: {str(e)}"
            )
            EvaluationRepository.update_error(db, task_id, f"Lỗi hệ thống: {str(e)}")


@app.get("/")
async def root():
    return {
        "service": "Call Center QA API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": len([t for t in task_storage.values() if t["status"] == "processing"])
    }

@app.post("/api/v1/evaluate/full", response_model=TaskStatusResponse)
async def evaluate_full(
    audio_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Đánh giá TOÀN DIỆN cả 2 tiêu chí:
    - Kỹ năng Giao tiếp (0-2 điểm)
    - Kỹ năng Bán hàng (điểm tùy theo số tiêu chí)
    """
    
    is_valid, message = validate_audio_file(audio_file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
   
    
    
    try:
        audio_bytes = await audio_file.read()
        task_id = str(create_task_id(audio_bytes=audio_bytes))
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        logger.info(f"[{task_id}] Nhận request đánh giá TOÀN DIỆN: {audio_file.filename}")
        if file_size_mb > 50:
            raise HTTPException(status_code=400, detail=f"File quá lớn ({file_size_mb:.2f}MB)")
        
        with get_db() as db:
            EvaluationRepository.create(
                db, 
                task_id=task_id,
                filename=audio_file.filename,
                file_size_mb=round(file_size_mb, 2)
            )
        
        # Sử dụng background task cho đánh giá tổng hợp
        background_tasks.add_task(process_full_evaluation_task, task_id, audio_bytes)
        
        return TaskStatusResponse(
            task_id=task_id,
            status="pending",
            message=f"Đã nhận file '{audio_file.filename}'. Đang đánh giá TOÀN DIỆN (2 tiêu chí)...",
            progress=0.0
        )
        
    except Exception as e:
        logger.error(f"[{task_id}] Lỗi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
                            
app.post("/api/v1/evaluate", response_model=TaskStatusResponse)
async def evaluate(
    audio_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """Đánh giá kỹ năng giao tiếp từ file audio"""
    
    is_valid, message = validate_audio_file(audio_file.filename)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    try:
        audio_bytes = await audio_file.read()
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        
        if file_size_mb > 50:
            raise HTTPException(status_code=400, detail=f"File quá lớn ({file_size_mb:.2f}MB)")
        
        # Tạo task_id từ audio_bytes (deterministic)
        task_id = str(create_task_id(audio_bytes=audio_bytes))
        logger.info(f"[{task_id}] Nhận request: {audio_file.filename}")
        
        with get_db() as db:
            EvaluationRepository.create(
                db, 
                task_id=task_id,
                filename=audio_file.filename,
                file_size_mb=round(file_size_mb, 2)
            )
        
        background_tasks.add_task(process_evaluation_task, task_id, audio_bytes)
        
        return TaskStatusResponse(
            task_id=task_id,
            status="pending",
            message=f"Đã nhận file '{audio_file.filename}'. Đang xử lý...",
            progress=0.0
        )
        
    except Exception as e:
        logger.error(f"Lỗi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/task/full/{task_id}", response_model=FullEvaluationResponse)
async def get_full_task_result(task_id: str):
    """
    Lấy kết quả đánh giá TOÀN DIỆN theo task_id
    Bao gồm cả điểm Giao tiếp và Bán hàng
    """
    
    with get_db() as db:
        evaluation = EvaluationRepository.get_by_task_id(db, task_id)
        
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy task_id: {task_id}")
        
        segments_data = None
        if evaluation.status == 'completed':
            segments = SegmentRepository.get_by_evaluation_id(db, evaluation.id)
            segments_data = [seg.to_dict() for seg in segments]
        
        # Parse ly_do để tách giao tiếp và bán hàng
        ly_do_giao_tiep = evaluation.ly_do if evaluation.ly_do else ""
        sales_detail = ""
        
        if evaluation.ly_do and "=== BÁN HÀNG ===" in evaluation.ly_do:
            parts = evaluation.ly_do.split("=== BÁN HÀNG ===")
            ly_do_giao_tiep = parts[0].replace("=== GIAO TIẾP ===", "").strip()
            sales_detail = parts[1].strip() if len(parts) > 1 else ""
        
        # Tính điểm giao tiếp
        communication_score = None
        if evaluation.tong_diem is not None:
            communication_score = 0.2 * (evaluation.chao_xung_danh + evaluation.ky_nang_noi) + \
                                 0.8 * (evaluation.ky_nang_nghe + evaluation.thai_do)
        
        return FullEvaluationResponse(
            task_id=evaluation.task_id,
            status=evaluation.status,
            communication_score=communication_score,
            chao_xung_danh=evaluation.chao_xung_danh,
            ky_nang_noi=evaluation.ky_nang_noi,
            ky_nang_nghe=evaluation.ky_nang_nghe,
            thai_do=evaluation.thai_do,
            muc_loi=evaluation.muc_loi,
            ly_do_giao_tiep=ly_do_giao_tiep,
            sales_score=None,  # TODO: Có thể lưu riêng trong database
            sales_criteria_details=None,  # TODO: Parse từ sales_detail
            total_score=evaluation.tong_diem,
            metadata={
                'duration': evaluation.duration,
                'turns': evaluation.turns,
                'ratio_sales': evaluation.ratio_sales
            } if evaluation.duration else None,
            segments=segments_data,
            error_message=evaluation.error_message,
            created_at=evaluation.created_at.isoformat(),
            completed_at=evaluation.completed_at.isoformat() if evaluation.completed_at else None
        )

@app.get("/api/v1/task/{task_id}", response_model=EvaluationResponse)
async def get_task_result(task_id: str):
    """Lay ket qua danh gia theo task_id"""
    
    with get_db() as db:
        evaluation = EvaluationRepository.get_by_task_id(db, task_id)
        
        if not evaluation:
            raise HTTPException(status_code=404, detail=f"Khong tim thay task_id: {task_id}")
        
 
        segments_data = None
        if evaluation.status == 'completed':
            segments = SegmentRepository.get_by_evaluation_id(db, evaluation.id)
            segments_data = [seg.to_dict() for seg in segments]
        
        return EvaluationResponse(
            task_id=evaluation.task_id,
            status=evaluation.status,
            chao_xung_danh=evaluation.chao_xung_danh,
            ky_nang_noi=evaluation.ky_nang_noi,
            ky_nang_nghe=evaluation.ky_nang_nghe,
            thai_do=evaluation.thai_do,
            tong_diem=evaluation.tong_diem,
            muc_loi=evaluation.muc_loi,
            ly_do=evaluation.ly_do,
            metadata={
                'duration': evaluation.duration,
                'turns': evaluation.turns,
                'ratio_sales': evaluation.ratio_sales
            } if evaluation.duration else None,
            error_message=evaluation.error_message,
            created_at=evaluation.created_at.isoformat(),
            completed_at=evaluation.completed_at.isoformat() if evaluation.completed_at else None,
            segments=segments_data
        )


@app.get("/api/v1/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    Liet ke cac task danh gia.
    
    **Params:**
    - status: Loc theo trang thai (pending, processing, completed, failed)
    - limit: So luong task toi da tra ve (mac dinh: 50)
    """
    tasks = list(task_storage.values())
    
   
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
 
    tasks.sort(key=lambda x: x["created_at"], reverse=True)
    
    
    tasks = tasks[:limit]
    
    return {
        "total": len(tasks),
        "tasks": tasks
    }


@app.delete("/api/v1/task/{task_id}")
async def delete_task(task_id: str):
    """Xoa task khoi storage (chi xoa in-memory, khong xoa file ket qua)"""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail=f"Khong tim thay task_id: {task_id}")
    
    task_data = task_storage.pop(task_id)
    logger.info(f"[{task_id}] Da xoa task")
    
    return {
        "message": "Da xoa task thanh cong",
        "task_id": task_id,
        "status": task_data["status"]
    }


@app.get("/api/v1/statistics")
async def get_statistics():
    """Lay thong ke tong quan"""
    with get_db() as db:
        return EvaluationRepository.get_statistics(db)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# ==================== STARTUP & SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Actions on startup"""
    logger.info("="*60)
    logger.info(" Call Center QA API dang khoi dong...")
    init_db()
    logger.info(" Database initialized")
    
    if LANGSMITH_ENABLED:
        logger.info(f"✓ LangSmith tracking: ENABLED")
        logger.info(f"  Project: {os.getenv('LANGCHAIN_PROJECT', 'call-center-qa')}")
    else:
        logger.info("  LangSmith tracking: DISABLED")
    
    logger.info(f" Results directory: {RESULTS_DIR}")
    logger.info(f" API Docs: http://localhost:8000/docs")
    logger.info("="*60)

@app.on_event("shutdown")
async def shutdown_event():
    """Actions on shutdown"""
    logger.info(" API dang tat...")
    
    # Luu task storage vao file truoc khi tat (optional)
    try:
        backup_file = RESULTS_DIR / "task_storage_backup.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(task_storage, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Da backup task storage vao {backup_file}")
    except Exception as e:
        logger.error(f"✗ Khong the backup task storage: {e}")


# ==================== RUN ====================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Dang khoi dong API server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )