import csv
from pathlib import Path
import sys

# --- BẠN CẦN CẤU HÌNH 3 MỤC SAU ---

# 1. Tên cột bạn muốn dùng để LỌC (VÍ DỤ: 'Dạng cuộc gọi')
COLUMN_TO_FILTER = 'Mã cuộc gọi' 

# 2. Giá trị bạn muốn LỌC (VÍ DỤ: 'BH' - nghĩa là "Bán hàng")
VALUE_TO_MATCH = 'BH' 

# 3. ÁNH XẠ TÊN CỘT (Rất quan trọng!)
#    (Kiểm tra file CSV gốc [_CG mẫu AI - 2025- QA CALL IBS _ REPORT - Cuộc gọi chấm.csv] 
#    và đảm bảo tên cột BÊN TRÁI khớp 100%)
COLUMN_RENAME_MAP = {
    # Tên cột trong CSV gốc : Tên cột mới (để benchmark dùng)
    'Link ghi âm': 'Link cuộc gọi',
    'Chào/ xưng danh': 'chào xưng danh',
    'Kỹ năng nói (Tốc độ - Âm lượng)': 'kỹ năng nói',
    'Kỹ năng nghe, Trấn an': 'kỹ năng nghe',
    'Thái độ giao tiếp': 'Thái độ giao tiếp'
}
# ------------------------------------

# [MỚI] Tên cột chứa link (lấy từ key của map ở trên)
LINK_COLUMN_ORIGINAL_NAME = 'Link ghi âm'

# [MỚI] Từ khóa không mong muốn trong link (sẽ bị loại bỏ)
EXCLUDE_KEYWORD = 'crm'

# Số lượng cuộc gọi muốn lấy
NUMBER_TO_SELECT = 50

# Tên file CSV gốc (file bạn đã upload)
INPUT_CSV_FILE = 'qa.csv'

# Tên file CSV mới - ĐÂY LÀ INPUT CHO BENCHMARK
OUTPUT_CSV_FILE = 'qa_data_50_sales_calls_input.csv'


def filter_and_transform_calls():
    """
    Đọc file CSV gốc, lọc (theo dạng cuộc gọi VÀ loại trừ link crm), 
    chỉ chọn và đổi tên các cột, sau đó lưu vào file mới.
    """
    print(f"--- BẮT ĐẦU LỌC VÀ BIẾN ĐỔI FILE ---")
    print(f"File đầu vào: {INPUT_CSV_FILE}")
    print(f"Lấy tối đa: {NUMBER_TO_SELECT} cuộc gọi")
    print(f"Tiêu chí lọc 1: Cột '{COLUMN_TO_FILTER}' == '{VALUE_TO_MATCH}'")
    print(f"Tiêu chí lọc 2: Cột '{LINK_COLUMN_ORIGINAL_NAME}' KHÔNG chứa '{EXCLUDE_KEYWORD}'")
    
    if not Path(INPUT_CSV_FILE).exists():
        print(f"\nLỗi: Không tìm thấy file CSV gốc '{INPUT_CSV_FILE}'.")
        sys.exit(1)

    filtered_and_renamed_calls = []
    original_headers_to_check = list(COLUMN_RENAME_MAP.keys())
    new_headers = list(COLUMN_RENAME_MAP.values()) # Đây là các cột output

    try:
        with open(INPUT_CSV_FILE, mode='r', encoding='latin-1') as f_in:
            reader = csv.DictReader(f_in)
            headers = reader.fieldnames
            
            # --- Kiểm tra các cột cần thiết ---
            missing_cols = []
            if COLUMN_TO_FILTER not in headers:
                missing_cols.append(COLUMN_TO_FILTER)
            for col in original_headers_to_check:
                if col not in headers:
                    missing_cols.append(col)
            
            if missing_cols:
                print(f"\nLỗi: Không tìm thấy các cột sau trong file CSV:")
                for col in missing_cols:
                    print(f" - '{col}'")
                print("\Vui lòng kiểm tra lại cấu hình COLUMN_TO_FILTER và COLUMN_RENAME_MAP.")
                sys.exit(1)
            # --- Kết thúc kiểm tra ---

            # Lặp qua từng hàng
            for row in reader:
                
                # --- ÁP DỤNG BỘ LỌC ---
                # 1. Lọc theo dạng cuộc gọi (ví dụ: 'BH')
                is_sales_call = (row.get(COLUMN_TO_FILTER) == VALUE_TO_MATCH)
                
                # 2. [MỚI] Lọc (loại trừ) link chứa 'crm' (không phân biệt hoa thường)
                link_value = row.get(LINK_COLUMN_ORIGINAL_NAME, '').lower()
                is_not_crm_link = (EXCLUDE_KEYWORD not in link_value)
                
                # Chỉ xử lý nếu thỏa mãn CẢ HAI điều kiện
                if is_sales_call and is_not_crm_link:
                    
                    # Tạo hàng mới chỉ chứa các cột cần thiết và đổi tên
                    new_row = {}
                    for original_name, new_name in COLUMN_RENAME_MAP.items():
                        new_row[new_name] = row[original_name]
                    
                    filtered_and_renamed_calls.append(new_row)
                    
                    # Dừng lại khi đã đủ 50 cuộc gọi
                    if len(filtered_and_renamed_calls) >= NUMBER_TO_SELECT:
                        break
        
        print(f"\nTìm thấy {len(filtered_and_renamed_calls)} cuộc gọi phù hợp.")

        # Ghi 50 cuộc gọi đã lọc ra file mới
        if filtered_and_renamed_calls:
            with open(OUTPUT_CSV_FILE, mode='w', encoding='utf-8', newline='') as f_out:
                # Sử dụng new_headers để ghi file
                writer = csv.DictWriter(f_out, fieldnames=new_headers)
                writer.writeheader()
                writer.writerows(filtered_and_renamed_calls)
            
            print(f"--- THÀNH CÔNG! ---")
            print(f"Đã lưu {len(filtered_and_renamed_calls)} cuộc gọi vào file: '{OUTPUT_CSV_FILE}'")
            print(f"File này đã SẴN SÀNG làm input cho script benchmark.")
        else:
            print("Không tìm thấy cuộc gọi nào phù hợp với cả 2 tiêu chí.")

    except Exception as e:
        print(f"\nĐã xảy ra lỗi: {e}")

if __name__ == "__main__":
    filter_and_transform_calls()