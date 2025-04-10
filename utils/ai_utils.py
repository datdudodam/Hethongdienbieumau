from openai import OpenAI
from config.config import OPENAI_API_KEY
from collections import defaultdict, Counter
import re

client = OpenAI(api_key=OPENAI_API_KEY)
def extract_context_from_form_text(form_text: str) -> str:
    prompt = (
        "Đây là nội dung một biểu mẫu do người dùng cung cấp:\n\n"
        f"{form_text}\n\n"
        "Hãy phân tích biểu mẫu này và cung cấp thông tin sau:\n"
        "1. Mục đích chính của biểu mẫu này là gì?\n"
        "2. Đối tượng sử dụng biểu mẫu này là ai?\n"
        "3. Các trường thông tin chính trong biểu mẫu gồm những gì?\n"
        "4. Ngữ cảnh sử dụng của biểu mẫu (ví dụ: hành chính, pháp lý, kinh doanh, giáo dục, y tế, v.v.)\n"
        "5. Các giá trị thường được điền vào biểu mẫu này có đặc điểm gì?\n\n"
        "Hãy tổng hợp thành một đoạn văn ngắn gọn, súc tích để hệ thống gợi ý AI hiểu đúng ngữ cảnh và mục đích của biểu mẫu."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý AI chuyên phân tích và hiểu ngữ cảnh biểu mẫu để cung cấp gợi ý chính xác."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,  # Giảm temperature để kết quả nhất quán hơn
        max_tokens=300    # Tăng max_tokens để có thêm thông tin chi tiết
    )

    # Check if response and content exist before calling strip()
    if response and response.choices and response.choices[0].message.content:
        return response.choices[0].message.content.strip()
    return ""

def call_gpt_for_suggestions(field_name, historical_values, context=None, recent_values=None, frequency_data=None):
    try:
        prompt = (
            f"Bạn là một hệ thống gợi ý biểu mẫu tự động, thông minh và thân thiện.\n"
            f"Trường cần gợi ý: '{field_name}'.\n"
        )
        
        # Thêm thông tin về lịch sử người dùng
        if historical_values:
            if len(historical_values) > 10:
                # Nếu có quá nhiều giá trị lịch sử, chỉ hiển thị 10 giá trị đầu tiên
                prompt += f"Lịch sử người dùng từng nhập (top 10): {', '.join(historical_values[:10])}.\n"
            else:
                prompt += f"Lịch sử người dùng từng nhập: {', '.join(historical_values)}.\n"
        
        # Nhấn mạnh các giá trị gần đây
        if recent_values:
            prompt += f"Gần đây người dùng hay chọn (theo thứ tự mới nhất): {', '.join(recent_values)}.\n"
            prompt += f"Hãy ưu tiên các giá trị gần đây nhất khi đưa ra gợi ý.\n"
        
        # Thêm thông tin về tần suất sử dụng nếu có
        if frequency_data:
            prompt += f"Tần suất sử dụng: {frequency_data}\n"
        
        # Thêm ngữ cảnh biểu mẫu
        if context:
            prompt += f"Biểu mẫu này thuộc ngữ cảnh: {context}.\n"
            prompt += f"Hãy đảm bảo gợi ý phù hợp với ngữ cảnh biểu mẫu.\n"

        prompt += (
            "Hãy gợi ý 5 giá trị phù hợp nhất cho trường này, cách nhau bằng dấu phẩy.\n"
            "Ngoài ra, hãy chọn ra 1 giá trị mặc định hợp lý nhất để điền sẵn.\n"
            "Trả kết quả theo định dạng: \n"
            "Gợi ý: [giá trị1, giá trị2, ...]\n"
            "Mặc định: giá trị"
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a smart and contextual form assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=200
        )

        content = response.choices[0].message.content

        # Trích xuất danh sách gợi ý và mặc định
        suggestions = []
        default_value = ""

        # Xử lý text
        suggestions_match = re.search(r"Gợi ý:\s*\[(.*?)\]", content, re.DOTALL)
        if suggestions_match:
            suggestions_raw = suggestions_match.group(1)
            suggestions = [s.strip() for s in suggestions_raw.split(",") if s.strip()]

        default_match = re.search(r"Mặc định:\s*(.+)", content)
        if default_match:
            default_value = default_match.group(1).strip()

        return {
            "suggestions": suggestions[:5],
            "default": default_value
        }

    except Exception as e:
        print(f"Lỗi khi gọi GPT: {e}")
        return {"suggestions": [], "default": ""}

def rewrite_user_input_for_suggestion(field_name, user_input, context=None):
    try:
        prompt = (
            f"Người dùng đã từng nhập cho trường '{field_name}': \"{user_input}\"\n"
        )
        if context:
            prompt += f"Ngữ cảnh: {context}\n"
        prompt += (
            "Hãy viết lại nội dung trên theo cách chuyên nghiệp, rõ ràng, thuyết phục và tự nhiên hơn.\n"
            "Chỉ trả về nội dung đã viết lại, không thêm gì khác."
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Bạn là một trợ lý AI giúp viết lại nội dung biểu mẫu chuyên nghiệp."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=150
        )

        improved_text = response.choices[0].message.content.strip()
        return improved_text

    except Exception as e:
        print(f"Lỗi khi rewrite: {e}")
        return user_input

def generate_personalized_suggestions(db_data, user_id, field_code=None, context=None):
    suggestions = defaultdict(Counter)
    recent_data = defaultdict(list)
    entry_timestamps = defaultdict(list)  # Lưu timestamp của mỗi entry

    # Sắp xếp dữ liệu theo thời gian (mới nhất trước)
    sorted_entries = sorted(
        [entry for entry in db_data if entry.get("user_id") == user_id],
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )

    # Lấy dữ liệu theo người dùng với trọng số theo thời gian
    for idx, entry in enumerate(sorted_entries):
        recency_weight = max(1, 5 - idx // 2)  # Trọng số giảm dần theo thời gian
        
        for key, value in entry["form_data"].items():
            if field_code is None or key == field_code:
                # Viết lại nếu nội dung dài (văn bản), ngược lại giữ nguyên
                cleaned_value = value.strip()
                if len(cleaned_value.split()) >= 5:  # Nếu là câu dài
                    rewritten_value = rewrite_user_input_for_suggestion(key, cleaned_value, context)
                else:
                    rewritten_value = cleaned_value

                # Áp dụng trọng số theo độ mới của dữ liệu
                suggestions[key][rewritten_value] += recency_weight
                recent_data[key].append(rewritten_value)
                entry_timestamps[key].append((rewritten_value, entry.get("timestamp", ""), recency_weight))


    result = {}

    for key, counter in suggestions.items():
        all_values = list(counter.keys())
        
        # Lấy 3 giá trị gần đây nhất dựa trên timestamp
        recent_entries = sorted(entry_timestamps[key], key=lambda x: x[1], reverse=True)[:3]
        recent_values = [entry[0] for entry in recent_entries]
        
        # Thêm thông tin về tần suất sử dụng và thời gian vào prompt
        gpt_response = call_gpt_for_suggestions(
            field_name=key,
            historical_values=all_values,
            context=context,
            recent_values=recent_values
        )
        
        # Kết hợp gợi ý GPT với top phổ biến có trọng số
        most_common_values = [val for val, _ in counter.most_common(3)]
        
        # Ưu tiên các giá trị gần đây
        prioritized_values = recent_values.copy()
        
        # Thêm các giá trị phổ biến nếu chưa có trong danh sách ưu tiên
        for val in most_common_values:
            if val not in prioritized_values:
                prioritized_values.append(val)
        
        # Kết hợp với gợi ý từ GPT
        combined = []
        # Đầu tiên thêm các giá trị ưu tiên
        for val in prioritized_values:
            if val not in combined and len(combined) < 3:
                combined.append(val)
        
        # Sau đó thêm các gợi ý từ GPT
        for val in gpt_response["suggestions"]:
            if val not in combined and len(combined) < 5:
                combined.append(val)
        
        # Chọn giá trị mặc định thông minh hơn
        default_value = gpt_response["default"]
        if not default_value and recent_values:
            # Nếu không có giá trị mặc định từ GPT, sử dụng giá trị gần đây nhất
            default_value = recent_values[0]
        
        result[key] = {
            "suggestions": combined,
            "default": default_value,
            "confidence": 0.9,  # Thêm độ tin cậy
            "details": {
                "source_name": "Lịch sử người dùng + AI",
                "method": "Kết hợp dữ liệu lịch sử và gợi ý AI",
                "confidence": 0.9
            }
        }

    return result if field_code is None else result.get(field_code, {"suggestions": [], "default": ""})