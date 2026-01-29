import json
import re

def mergeJsons(file1Path, file2Path, outputPath):
    # 1. Đọc dữ liệu từ 2 file
    with open(file1Path, 'r', encoding='utf-8') as f1, \
         open(file2Path, 'r', encoding='utf-8') as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)

    # 2. Thu thập tất cả các key duy nhất từ cả 2 file
    all_keys = set()
    for item in data1 + data2:
        all_keys.update(item.keys())

    # 3. Phân loại và sắp xếp các key
    # Tách riêng các trường Level để sắp xếp theo số (Level 1, Level 2, Level 10...)
    level_keys = [k for k in all_keys if k.startswith('Level')]
    
    def extractLevelNumber(key):
        # Tìm số trong chuỗi "Level X", nếu không thấy trả về 0
        match = re.search(r'\d+', key)
        return int(match.group()) if match else 0

    sorted_level_keys = sorted(level_keys, key=extractLevelNumber)
    
    # Xác định các trường cố định khác (trừ Index và Level)
    other_keys = [k for k in all_keys if k not in sorted_level_keys and k != 'Index']
    # Thứ tự cuối cùng: Index -> Các Level -> Các trường còn lại (Article, Content...)
    final_key_order = ['Index'] + sorted_level_keys + sorted_level_keys + other_keys

    # 4. Xử lý đánh lại Index cho JSON 2
    # Lấy index cuối cùng của JSON 1. Giả sử data1 không rỗng.
    last_index_json1 = data1[-1].get('Index', 0) if data1 else 0
    
    for i, item in enumerate(data2):
        item['Index'] = last_index_json1 + (i + 1)

    # 5. Gộp và điền giá trị trống cho các trường thiếu
    merged_data = data1 + data2
    final_json = []

    for item in merged_data:
        # Tạo dictionary mới với đầy đủ các key theo thứ tự đã sắp xếp
        new_item = {}
        for key in final_key_order:
            # Nếu không có giá trị thì để trống ("")
            new_item[key] = item.get(key, "")
        final_json.append(new_item)

    # 6. Lưu file kết quả
    with open(outputPath, 'w', encoding='utf-8') as f_out:
        json.dump(final_json, f_out, ensure_ascii=False, indent=4)
    
    print(f"Đã gộp thành công vào file: {outputPath}")

# --- Cách sử dụng ---

# merge_jsons('data1.json', 'data2.json', 'merged.json')