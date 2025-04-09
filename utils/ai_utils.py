from openai import OpenAI
from config.config import OPENAI_API_KEY
from collections import defaultdict, Counter
import re

client = OpenAI(api_key=OPENAI_API_KEY)
def extract_context_from_form_text(form_text: str) -> str:
    prompt = (
        "Đây là nội dung một biểu mẫu do người dùng cung cấp:\n\n"
        f"{form_text}\n\n"
        "Hãy mô tả ngắn gọn biểu mẫu này dùng để làm gì, ai sử dụng, và nội dung chính gồm những gì.\n"
        "Mô tả nên rõ ràng để hệ thống gợi ý AI hiểu đúng mục đích biểu mẫu."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý AI giúp phân tích và gợi ý biểu mẫu."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=200
    )

    # Add null check before calling strip()
    content = response.choices[0].message.content
    return content.strip() if content else ""

def call_gpt_for_suggestions(field_name, historical_values, context=None, recent_values=None):
    try:
        prompt = (
            f"Bạn là một hệ thống gợi ý biểu mẫu tự động, thông minh và thân thiện.\n"
            f"Trường cần gợi ý: '{field_name}'.\n"
            f"Lịch sử người dùng từng nhập: {', '.join(historical_values)}.\n"
        )
        if recent_values:
            prompt += f"Gần đây người dùng hay chọn: {', '.join(recent_values)}.\n"
        if context:
            prompt += f"Biểu mẫu này thuộc ngữ cảnh: {context}.\n"

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

    # Lấy dữ liệu theo người dùng
    for entry in db_data:
        if entry["user_id"] == user_id:
            for key, value in entry["data"].items():
                if field_code is None or key == field_code:
                    # Viết lại nếu nội dung dài (văn bản), ngược lại giữ nguyên
                    cleaned_value = value.strip()
                    if len(cleaned_value.split()) >= 5:  # Nếu là câu dài
                        rewritten_value = rewrite_user_input_for_suggestion(key, cleaned_value, context)
                    else:
                        rewritten_value = cleaned_value

                    suggestions[key][rewritten_value] += 1
                    recent_data[key].append(rewritten_value)


    result = {}

    for key, counter in suggestions.items():
        all_values = list(counter.keys())
        recent_values = recent_data[key][-3:]  # Lấy 3 giá trị gần nhất

        gpt_response = call_gpt_for_suggestions(
            field_name=key,
            historical_values=all_values,
            context=context,
            recent_values=recent_values
        )

        # Kết hợp gợi ý GPT với top phổ biến
        most_common_values = [val for val, _ in counter.most_common(3)]
        combined = list(dict.fromkeys(most_common_values + gpt_response["suggestions"]))[:5]

        result[key] = {
            "suggestions": combined,
            "default": gpt_response["default"]
        }

    return result if field_code is None else result.get(field_code, {"suggestions": [], "default": ""})
