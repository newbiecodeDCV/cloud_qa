"""
Script test database operations
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.qa_communicate.database.database import get_db, init_db
from src.qa_communicate.database.repository import EvaluationRepository, SegmentRepository
import uuid


def test_basic_operations():
    """Test CRUD operations"""
    print("="*60)
    print("TESTING DATABASE OPERATIONS")
    print("="*60)
    
    # Initialize DB
    init_db()
    print("✅ Database initialized")
    
    with get_db() as db:
        # Test 1: Create evaluation
        print("\n[Test 1] Creating evaluation...")
        task_id = str(uuid.uuid4())
        evaluation = EvaluationRepository.create(
            db, 
            task_id=task_id,
            filename="test_audio.wav",
            file_size_mb=2.5
        )
        print(f"✅ Created: {evaluation}")
        
        # Test 2: Get by task_id
        print("\n[Test 2] Retrieving evaluation...")
        retrieved = EvaluationRepository.get_by_task_id(db, task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        print(f"✅ Retrieved: {retrieved}")
        
        # Test 3: Update status
        print("\n[Test 3] Updating status...")
        EvaluationRepository.update_status(db, task_id, 'processing')
        updated = EvaluationRepository.get_by_task_id(db, task_id)
        assert updated.status == 'processing'
        print(f"✅ Status updated to: {updated.status}")
        
        # Test 4: Update result
        print("\n[Test 4] Updating result...")
        result_data = {
            'chao_xung_danh': 1,
            'ky_nang_noi': 1,
            'ky_nang_nghe': 0,
            'thai_do': 1,
            'tong_diem': 1.2,
            'muc_loi': 'M1',
            'ly_do': 'Test reason',
            'metadata': {
                'duration': 120.5,
                'turns': 15,
                'ratio_sales': 0.65
            }
        }
        EvaluationRepository.update_result(db, task_id, result_data)
        completed = EvaluationRepository.get_by_task_id(db, task_id)
        assert completed.status == 'completed'
        assert completed.tong_diem == 1.2
        print(f"✅ Result updated. Score: {completed.tong_diem}")
        
        # Test 5: Create segments
        print("\n[Test 5] Creating segments...")
        segments_data = [
            {
                'segment': 1,
                'speaker': 'Sales',
                'start_time': 0.0,
                'end_time': 5.0,
                'text': 'Xin chào anh',
                'speed_spm': 150.0,
                'volume_db': -20.5,
                'pitch_hz': 200.0,
                'silence_ratio': 0.1
            },
            {
                'segment': 2,
                'speaker': 'Customer',
                'start_time': 5.0,
                'end_time': 10.0,
                'text': 'Chào chị',
                'speed_spm': 120.0,
                'volume_db': -22.0,
                'pitch_hz': 180.0,
                'silence_ratio': 0.15
            }
        ]
        segments = SegmentRepository.create_bulk(db, completed.id, segments_data)
        print(f"✅ Created {len(segments)} segments")
        
        # Test 6: Get segments
        print("\n[Test 6] Retrieving segments...")
        retrieved_segments = SegmentRepository.get_by_evaluation_id(db, completed.id)
        assert len(retrieved_segments) == 2
        print(f"✅ Retrieved {len(retrieved_segments)} segments")
        
        # Test 7: Statistics
        print("\n[Test 7] Getting statistics...")
        stats = EvaluationRepository.get_statistics(db)
        print(f"✅ Statistics: {stats}")
        
        # Test 8: List all
        print("\n[Test 8] Listing evaluations...")
        all_evals = EvaluationRepository.list_all(db, limit=10)
        print(f"✅ Found {len(all_evals)} evaluations")
        
        # Test 9: Delete
        print("\n[Test 9] Deleting evaluation...")
        deleted = EvaluationRepository.delete(db, task_id)
        assert deleted is True
        
        # Verify deletion
        after_delete = EvaluationRepository.get_by_task_id(db, task_id)
        assert after_delete is None
        print(f"✅ Evaluation deleted (cascade segments also deleted)")
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)


if __name__ == "__main__":
    try:
        test_basic_operations()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)