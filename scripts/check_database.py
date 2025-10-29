"""
Script để kiểm tra và xem dữ liệu trong database
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.qa_communicate.database.database import get_db
from src.qa_communicate.database.repository import EvaluationRepository, SegmentRepository
from tabulate import tabulate  # pip install tabulate


def show_statistics():
    """Hiển thị thống kê tổng quan"""
    print("\n" + "="*80)
    print("📊 THỐNG KÊ TỔNG QUAN")
    print("="*80)
    
    with get_db() as db:
        stats = EvaluationRepository.get_statistics(db)
        
        print(f"\n📈 Tổng số evaluations: {stats['total_evaluations']}")
        print(f"   ├─ ⏳ Pending: {stats['pending']}")
        print(f"   ├─ 🔄 Processing: {stats['processing']}")
        print(f"   ├─ ✅ Completed: {stats['completed']}")
        print(f"   └─ ❌ Failed: {stats['failed']}")
        
        if stats['average_score'] is not None:
            print(f"\n💯 Điểm trung bình: {stats['average_score']}/2.0")
        
        if stats['error_distribution']:
            print(f"\n⚠️  Phân bố mức lỗi:")
            for level, count in stats['error_distribution'].items():
                print(f"   ├─ {level}: {count} cuộc gọi")


def show_recent_evaluations(limit=10):
    """Hiển thị các evaluations gần nhất"""
    print("\n" + "="*80)
    print(f"📋 {limit} CUỘC GỌI GẦN NHẤT")
    print("="*80)
    
    with get_db() as db:
        evaluations = EvaluationRepository.list_all(db, limit=limit)
        
        if not evaluations:
            print("\n⚠️  Chưa có dữ liệu nào trong database.")
            return
        
        table_data = []
        for eval in evaluations:
            table_data.append([
                eval.task_id[:12] + "...",
                eval.filename[:30] if eval.filename else "N/A",
                eval.status,
                f"{eval.tong_diem:.1f}" if eval.tong_diem is not None else "N/A",
                eval.muc_loi or "N/A",
                eval.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        headers = ["Task ID", "Filename", "Status", "Điểm", "Mức lỗi", "Thời gian"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))


def show_evaluation_detail(task_id: str):
    """Hiển thị chi tiết một evaluation"""
    print("\n" + "="*80)
    print(f"🔍 CHI TIẾT EVALUATION: {task_id}")
    print("="*80)
    
    with get_db() as db:
        evaluation = EvaluationRepository.get_by_task_id(db, task_id)
        
        if not evaluation:
            print(f"\n❌ Không tìm thấy evaluation với task_id: {task_id}")
            return
        
        print(f"\n📁 File Info:")
        print(f"   ├─ Filename: {evaluation.filename}")
        print(f"   ├─ Size: {evaluation.file_size_mb:.2f} MB")
        print(f"   └─ Status: {evaluation.status}")
        
        print(f"\n⏰ Timestamps:")
        print(f"   ├─ Created: {evaluation.created_at}")
        print(f"   └─ Completed: {evaluation.completed_at or 'N/A'}")
        
        if evaluation.status == 'completed':
            print(f"\n📊 Call Metadata:")
            print(f"   ├─ Duration: {evaluation.duration:.2f}s")
            print(f"   ├─ Turns: {evaluation.turns}")
            print(f"   └─ Sales Ratio: {evaluation.ratio_sales:.2%}")
            
            print(f"\n💯 Scoring Results:")
            print(f"   ├─ Chào/Xưng danh: {evaluation.chao_xung_danh}/1")
            print(f"   ├─ Kỹ năng nói: {evaluation.ky_nang_noi}/1")
            print(f"   ├─ Kỹ năng nghe: {evaluation.ky_nang_nghe}/1")
            print(f"   ├─ Thái độ: {evaluation.thai_do}/1")
            print(f"   ├─ 🎯 Tổng điểm: {evaluation.tong_diem:.2f}/2.0")
            print(f"   └─ ⚠️  Mức lỗi: {evaluation.muc_loi}")
            
            print(f"\n📝 Lý do chi tiết:")
            print(f"   {evaluation.ly_do}")
            
            # Show segments
            segments = SegmentRepository.get_by_evaluation_id(db, evaluation.id)
            if segments:
                print(f"\n🗣️  Segments ({len(segments)} đoạn):")
                seg_table = []
                for seg in segments[:5]:  # Show first 5 segments
                    seg_table.append([
                        seg.segment_number,
                        seg.speaker,
                        f"{seg.start_time:.1f}s - {seg.end_time:.1f}s",
                        seg.text[:50] + "..." if seg.text and len(seg.text) > 50 else seg.text,
                        f"{seg.speed_spm:.0f}" if seg.speed_spm else "N/A"
                    ])
                
                headers = ["#", "Speaker", "Time", "Text", "SPM"]
                print(tabulate(seg_table, headers=headers, tablefmt="grid"))
                
                if len(segments) > 5:
                    print(f"   ... và {len(segments) - 5} segments khác")
        
        elif evaluation.status == 'failed':
            print(f"\n❌ Error Message:")
            print(f"   {evaluation.error_message}")


def show_error_distribution():
    """Hiển thị phân bố lỗi chi tiết"""
    print("\n" + "="*80)
    print("⚠️  PHÂN BỐ MỨC LỖI CHI TIẾT")
    print("="*80)
    
    with get_db() as db:
        from sqlalchemy import func
        from src.qa_communicate.database.models import Evaluation
        
        results = db.query(
            Evaluation.muc_loi,
            func.count(Evaluation.id).label('count'),
            func.avg(Evaluation.tong_diem).label('avg_score')
        ).filter(
            Evaluation.status == 'completed',
            Evaluation.muc_loi.isnot(None)
        ).group_by(Evaluation.muc_loi).all()
        
        if not results:
            print("\n⚠️  Chưa có dữ liệu completed để phân tích.")
            return
        
        table_data = []
        for muc_loi, count, avg_score in results:
            table_data.append([
                muc_loi,
                count,
                f"{avg_score:.2f}" if avg_score else "N/A"
            ])
        
        headers = ["Mức lỗi", "Số lượng", "Điểm TB"]
        print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))


def interactive_menu():
    """Menu tương tác"""
    while True:
        print("\n" + "="*80)
        print("🗄️  DATABASE INSPECTOR")
        print("="*80)
        print("\n[1] Xem thống kê tổng quan")
        print("[2] Xem 10 cuộc gọi gần nhất")
        print("[3] Xem chi tiết một evaluation (theo task_id)")
        print("[4] Xem phân bố mức lỗi")
        print("[5] Xem tất cả evaluations (có pagination)")
        print("[0] Thoát")
        
        choice = input("\nChọn (0-5): ").strip()
        
        if choice == '0':
            print("\n👋 Tạm biệt!")
            break
        elif choice == '1':
            show_statistics()
        elif choice == '2':
            show_recent_evaluations(10)
        elif choice == '3':
            task_id = input("\nNhập task_id: ").strip()
            if task_id:
                show_evaluation_detail(task_id)
            else:
                print("❌ Task ID không hợp lệ!")
        elif choice == '4':
            show_error_distribution()
        elif choice == '5':
            limit = input("\nSố lượng records (mặc định 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            show_recent_evaluations(limit)
        else:
            print("❌ Lựa chọn không hợp lệ!")
        
        input("\nNhấn Enter để tiếp tục...")


if __name__ == "__main__":
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Đã dừng chương trình!")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()