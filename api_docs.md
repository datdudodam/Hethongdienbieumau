# Tài liệu API - Hệ Thống Nhập Liệu Thông Minh

## Giới thiệu

Đây là tài liệu API chính thức cho Hệ Thống Nhập Liệu Thông Minh. Tài liệu này mô tả chi tiết các API endpoints có sẵn, cách sử dụng chúng và các tham số cần thiết. Hệ thống cung cấp các API để quản lý hồ sơ người dùng, biểu mẫu, tài liệu, xác thực người dùng, các tính năng AI hỗ trợ nhập liệu và quản trị hệ thống.

## Base URL

Tất cả các API đều sử dụng base URL: `http://localhost:55003`

## Authentication

Hầu hết các API yêu cầu xác thực người dùng. Xác thực được thực hiện thông qua session cookie sau khi đăng nhập.

### Phương thức xác thực

1. **Session-based Authentication**: Sau khi đăng nhập thành công, server sẽ tạo một session và trả về session cookie. Các request tiếp theo cần gửi kèm cookie này để xác thực.

2. **OAuth Authentication**: Hệ thống hỗ trợ đăng nhập thông qua Google OAuth. Sau khi xác thực thành công với Google, server sẽ tạo session tương tự như phương thức đăng nhập thông thường.

### Headers

Các API yêu cầu xác thực cần gửi kèm cookie trong header:

```
Cookie: session=<session_id>
```

### Lỗi xác thực

Khi xác thực thất bại, API sẽ trả về mã lỗi 401 Unauthorized hoặc 403 Forbidden tùy thuộc vào trường hợp cụ thể.

## API Endpoints

### Authentication APIs

#### Đăng nhập

```
POST /login
```

**Mô tả**: Đăng nhập vào hệ thống

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `email` (string, required): Email của người dùng
- `password` (string, required): Mật khẩu của người dùng
- `remember` (boolean, optional): Ghi nhớ đăng nhập, mặc định là `false`

**Responses**:
- `200 OK`: Đăng nhập thành công, chuyển hướng đến trang chủ
  - Set-Cookie: `session=<session_id>; Path=/; HttpOnly`
- `401 Unauthorized`: Thông tin đăng nhập không chính xác
  - Body: `{"error": "Email hoặc mật khẩu không chính xác"}`
- `400 Bad Request`: Thiếu thông tin đăng nhập
  - Body: `{"error": "Vui lòng nhập email và mật khẩu"}`

#### Đăng ký

```
POST /signup
```

**Mô tả**: Đăng ký tài khoản mới

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `email` (string, required): Email của người dùng
- `password` (string, required): Mật khẩu của người dùng (tối thiểu 8 ký tự)
- `confirm_password` (string, required): Xác nhận mật khẩu
- `name` (string, optional): Tên người dùng
- `phone` (string, optional): Số điện thoại

**Validation**:
- Email phải đúng định dạng
- Mật khẩu phải có ít nhất 8 ký tự
- Mật khẩu và xác nhận mật khẩu phải trùng khớp

**Responses**:
- `200 OK`: Đăng ký thành công, chuyển hướng đến trang đăng nhập
  - Body: `{"success": true, "message": "Đăng ký thành công"}`
- `400 Bad Request`: Thông tin đăng ký không hợp lệ
  - Body: `{"error": "<thông báo lỗi cụ thể>"}` (ví dụ: "Email đã tồn tại", "Mật khẩu phải có ít nhất 8 ký tự", "Mật khẩu không khớp")

#### Đăng xuất

```
GET /logout
```

**Mô tả**: Đăng xuất khỏi hệ thống

**Responses**:
- `302 Found`: Đăng xuất thành công, chuyển hướng đến trang đăng nhập

#### Đăng nhập bằng Google

```
GET /login/google
```

**Mô tả**: Bắt đầu quá trình đăng nhập bằng Google OAuth

**Responses**:
- `302 Found`: Chuyển hướng đến trang xác thực Google

```
GET /auth/google/callback
```

**Mô tả**: Callback URL cho quá trình đăng nhập bằng Google OAuth

**Responses**:
- `302 Found`: Đăng nhập thành công, chuyển hướng đến trang chủ
- `401 Unauthorized`: Đăng nhập thất bại

### Profile APIs

#### Xem thông tin cá nhân

```
GET /profile
```

**Mô tả**: Xem thông tin cá nhân của người dùng đã đăng nhập

**Yêu cầu xác thực**: Có

**Responses**:
- `200 OK`: Hiển thị trang thông tin cá nhân với đầy đủ thông tin người dùng
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập

#### Cập nhật thông tin cá nhân

```
POST /profile/update
```

**Mô tả**: Cập nhật thông tin cá nhân của người dùng

**Yêu cầu xác thực**: Có

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `fullname` (string, required): Họ và tên đầy đủ của người dùng
- `phone` (string, optional): Số điện thoại
- `address` (string, optional): Địa chỉ
- `bio` (string, optional): Thông tin giới thiệu

**Validation**:
- Họ và tên không được để trống

**Responses**:
- `200 OK`: Cập nhật thành công, chuyển hướng đến trang hồ sơ
  - Flash message: `Cập nhật thông tin thành công!`
- `400 Bad Request`: Thông tin không hợp lệ
  - Flash message: `Họ và tên không được để trống`

#### Đổi mật khẩu

```
POST /profile/change-password
```

**Mô tả**: Đổi mật khẩu của người dùng

**Yêu cầu xác thực**: Có

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `current_password` (string, required): Mật khẩu hiện tại
- `new_password` (string, required): Mật khẩu mới
- `confirm_password` (string, required): Xác nhận mật khẩu mới

**Validation**:
- Mật khẩu hiện tại phải chính xác
- Mật khẩu mới và xác nhận mật khẩu phải trùng khớp
- Mật khẩu mới phải đáp ứng các yêu cầu về độ mạnh (được kiểm tra bởi hàm validate_password)

**Responses**:
- `200 OK`: Đổi mật khẩu thành công, chuyển hướng đến trang hồ sơ
  - Flash message: `Đổi mật khẩu thành công!`
- `400 Bad Request`: Thông tin không hợp lệ
  - Flash message: `Mật khẩu hiện tại không chính xác`, `Mật khẩu xác nhận không khớp`, hoặc thông báo lỗi từ validate_password

#### Thiết lập mật khẩu (cho tài khoản OAuth)

```
POST /profile/set-password
```

**Mô tả**: Thiết lập mật khẩu cho tài khoản đăng nhập bằng OAuth

**Yêu cầu xác thực**: Có

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `new_password` (string, required): Mật khẩu mới
- `confirm_password` (string, required): Xác nhận mật khẩu mới

**Validation**:
- Mật khẩu mới và xác nhận mật khẩu phải trùng khớp
- Mật khẩu mới phải đáp ứng các yêu cầu về độ mạnh (được kiểm tra bởi hàm validate_password)

**Responses**:
- `200 OK`: Thiết lập mật khẩu thành công, chuyển hướng đến trang hồ sơ
  - Flash message: `Thiết lập mật khẩu thành công!`
- `400 Bad Request`: Thông tin không hợp lệ
  - Flash message: `Mật khẩu xác nhận không khớp` hoặc thông báo lỗi từ validate_password

#### Nâng cấp tài khoản

```
GET /upgrade
```

**Mô tả**: Nâng cấp tài khoản lên gói Thường

**Yêu cầu xác thực**: Có

**Responses**:
- `200 OK`: Nâng cấp tài khoản thành công, cập nhật thông tin subscription_type và subscription_start
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập

```
GET /upgrade_vip
```

**Mô tả**: Nâng cấp tài khoản lên gói VIP

**Yêu cầu xác thực**: Có

**Responses**:
- `200 OK`: Nâng cấp tài khoản thành công, cập nhật thông tin subscription_type và subscription_start
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập

### Home APIs

#### Trang chủ

```
GET /
```

**Mô tả**: Hiển thị trang chủ

**Responses**:
- `200 OK`: Hiển thị trang chủ

#### Dashboard

```
GET /dashboard
```

**Mô tả**: Hiển thị trang dashboard

**Responses**:
- `200 OK`: Hiển thị trang dashboard
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập

#### Upload tài liệu

```
POST /upload
```

**Mô tả**: Tải lên tài liệu docx

**Parameters**:
- `file` (file, required): Tài liệu docx cần tải lên

**Responses**:
- `200 OK`: Tải lên thành công
- `400 Bad Request`: Không có file hoặc file không hợp lệ

#### Lấy danh sách biểu mẫu gần đây

```
GET /get-recent-forms
```

**Mô tả**: Lấy danh sách các biểu mẫu gần đây của người dùng

**Parameters**:
- `query` (string, optional): Từ khóa tìm kiếm

**Responses**:
- `200 OK`: Trả về danh sách biểu mẫu

### Form APIs

#### Hiển thị biểu mẫu

```
GET /form
```

**Mô tả**: Hiển thị biểu mẫu từ tài liệu đã tải lên

**Yêu cầu tiên quyết**: Phải có tài liệu đã được tải lên trước đó

**Responses**:
- `200 OK`: Hiển thị biểu mẫu với các trường được trích xuất từ tài liệu
  - Body: Trang HTML với các trường biểu mẫu
- `400 Bad Request`: Không có tài liệu nào được tải lên
  - Body: `{"error": "No document uploaded"}`

#### Lưu và tạo tài liệu docx

```
POST /save-and-generate-docx
```

**Mô tả**: Lưu dữ liệu biểu mẫu vào lịch sử và tạo tài liệu docx với dữ liệu đã nhập

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `document_name` (string, optional): Tên tài liệu, nếu không cung cấp sẽ sử dụng tên file gốc
- Các trường dữ liệu của biểu mẫu: Mỗi trường được xác định bởi field_code tương ứng

**Xử lý**:
- Tạo form_id mới (UUID)
- Lưu dữ liệu vào lịch sử biểu mẫu với thông tin người dùng (nếu đã đăng nhập)
- Tạo tài liệu docx với dữ liệu đã nhập

**Responses**:
- `200 OK`: Lưu và tạo tài liệu thành công, trả về file docx để tải xuống
  - Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - Content-Disposition: `attachment; filename="<tên_file>.docx"`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Body: `{"error": "Không có dữ liệu được gửi"}` hoặc `{"error": "Không tìm thấy tài liệu"}`
- `500 Internal Server Error`: Lỗi xử lý yêu cầu
  - Body: `{"error": "Có lỗi xảy ra khi xử lý yêu cầu"}`

#### Xem biểu mẫu theo ID

```
GET /form/<form_id>
```

**Mô tả**: Xem biểu mẫu theo ID từ lịch sử biểu mẫu

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu

**Xử lý**:
- Tìm kiếm biểu mẫu trong lịch sử theo form_id
- Tải lại tài liệu gốc và trích xuất các trường
- Điền dữ liệu từ lịch sử vào biểu mẫu

**Responses**:
- `200 OK`: Hiển thị biểu mẫu với dữ liệu đã lưu
  - Body: Trang HTML với các trường biểu mẫu đã được điền
- `404 Not Found`: Không tìm thấy biểu mẫu
  - Body: `{"error": "Không tìm thấy biểu mẫu"}`
- `500 Internal Server Error`: Lỗi xử lý yêu cầu
  - Body: `{"error": "Có lỗi xảy ra khi xử lý yêu cầu"}`

#### Xóa biểu mẫu

```
DELETE /delete-form/<form_id>
```

**Mô tả**: Xóa biểu mẫu theo ID khỏi lịch sử biểu mẫu

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu

**Xử lý**:
- Tìm kiếm và xóa biểu mẫu khỏi lịch sử theo form_id
- Lưu lại lịch sử biểu mẫu đã cập nhật

**Responses**:
- `200 OK`: Xóa biểu mẫu thành công
  - Body: `{"success": true, "message": "Đã xóa biểu mẫu thành công"}`
- `404 Not Found`: Không tìm thấy biểu mẫu
  - Body: `{"error": "Không tìm thấy biểu mẫu"}`
- `500 Internal Server Error`: Lỗi xử lý yêu cầu
  - Body: `{"error": "Có lỗi xảy ra khi xử lý yêu cầu"}`

### Document APIs

#### Tạo tài liệu docx

```
POST /generate-docx
```

**Mô tả**: Tạo tài liệu docx từ dữ liệu biểu mẫu

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu

**Responses**:
- `200 OK`: Tạo tài liệu thành công, trả về file docx
- `400 Bad Request`: Dữ liệu không hợp lệ
- `401 Unauthorized`: Chưa đăng nhập
- `403 Forbidden`: Không đủ quyền hoặc đã hết lượt tải

### AI Services APIs

#### Tự động điền trường

```
POST /auto_fill_field
```

**Mô tả**: Tự động điền một trường dữ liệu bằng AI dựa trên ngữ cảnh của các trường khác và dữ liệu lịch sử

**Content-Type**: `application/json`

**Parameters**:
- `field_code` (string, required): Mã trường cần điền (ví dụ: "field_1", "name", "address")
- `field_name` (string, required): Tên hiển thị của trường cần điền (ví dụ: "Họ và tên", "Địa chỉ")
- `field_type` (string, optional): Loại trường (ví dụ: "text", "number", "date")
- `current_values` (object, required): Giá trị hiện tại của các trường khác trong form
  - Cấu trúc: `{"field_code1": "value1", "field_code2": "value2", ...}`
- `form_context` (string, optional): Ngữ cảnh của form (ví dụ: "đơn xin việc", "hợp đồng")
- `max_tokens` (integer, optional): Số lượng token tối đa cho kết quả, mặc định là 100

**Xử lý**:
- Phân tích ngữ cảnh của biểu mẫu
- Tìm kiếm trong lịch sử biểu mẫu để tìm các giá trị tương tự
- Sử dụng AI để gợi ý giá trị phù hợp nhất

**Responses**:
- `200 OK`: Trả về giá trị được gợi ý
  - Body: `{"success": true, "suggested_value": "<giá trị được gợi ý>", "confidence": 0.85}`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Body: `{"error": "<thông báo lỗi>", "field_code": "<mã trường>"}`
- `401 Unauthorized`: Chưa đăng nhập
- `403 Forbidden`: Không đủ quyền hoặc đã hết lượt sử dụng AI
  - Body: `{"error": "Bạn đã hết lượt sử dụng AI. Vui lòng nâng cấp tài khoản.", "upgrade_url": "/upgrade"}`

#### Tự động điền tất cả các trường

```
POST /auto_fill_all_fields
```

**Mô tả**: Tự động điền tất cả các trường dữ liệu bằng AI dựa trên ngữ cảnh và dữ liệu lịch sử

**Content-Type**: `application/json`

**Parameters**:
- `fields` (array, required): Danh sách các trường cần điền
  - Cấu trúc mỗi phần tử: `{"field_code": "field_1", "field_name": "Họ và tên", "field_type": "text"}`
- `current_values` (object, required): Giá trị hiện tại của các trường
  - Cấu trúc: `{"field_code1": "value1", "field_code2": "value2", ...}`
- `form_context` (string, optional): Ngữ cảnh của form

**Xử lý**:
- Phân tích ngữ cảnh của biểu mẫu
- Tìm kiếm trong lịch sử biểu mẫu để tìm các giá trị tương tự cho mỗi trường
- Sử dụng AI để gợi ý giá trị phù hợp nhất cho mỗi trường

**Responses**:
- `200 OK`: Trả về giá trị được gợi ý cho tất cả các trường
  - Body: `{"success": true, "suggestions": {"field_code1": {"value": "<giá trị>", "confidence": 0.85}, "field_code2": {"value": "<giá trị>", "confidence": 0.7}, ...}}`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Body: `{"error": "<thông báo lỗi>"}`
- `401 Unauthorized`: Chưa đăng nhập
- `403 Forbidden`: Không đủ quyền hoặc đã hết lượt sử dụng AI

#### AI điền form

```
POST /AI_FILL
```

**Mô tả**: Sử dụng AI để điền một trường trong form dựa trên dữ liệu lịch sử và ngữ cảnh

**Content-Type**: `application/json`

**Parameters**:
- `field_name` (string, required): Mã trường cần điền (frontend gửi field_code với key là field_name)

**Xử lý**:
- Lấy document path hiện tại
- Trích xuất tất cả các trường từ tài liệu
- Tìm field_name tương ứng với field_code
- Trích xuất ngữ cảnh từ nội dung biểu mẫu
- Gọi hàm generate_personalized_suggestions từ AIFieldMatcher

**Responses**:
- `200 OK`: Trả về giá trị được gợi ý và danh sách gợi ý
  - Body: `{"value": "<giá trị>", "suggestions": ["<gợi ý 1>", "<gợi ý 2>", ...], "confidence": 0.85, "field_name": "<tên trường>", "field_code": "<mã trường>"}`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Body: `{"error": "Field code is required"}` hoặc `{"error": "No document loaded"}`
- `500 Internal Server Error`: Lỗi xử lý yêu cầu
  - Body: `{"error": "<thông báo lỗi>"}`

#### Lưu phản hồi AI

```
POST /AI_SAVE_FEEDBACK
```

**Mô tả**: Lưu phản hồi của người dùng về gợi ý AI để cải thiện độ chính xác trong tương lai

**Content-Type**: `application/json`

**Parameters**:
- `field_code` (string, required): Mã trường
- `field_name` (string, optional): Tên trường, nếu không cung cấp sẽ sử dụng field_code
- `selected_value` (string, required): Giá trị được chọn

**Xử lý**:
- Lấy user_id từ session nếu người dùng đã đăng nhập
- Cập nhật giá trị vào lịch sử thông qua AIFieldMatcher

**Responses**:
- `200 OK`: Lưu phản hồi thành công
  - Body: `{"success": true, "message": "Đã lưu phản hồi thành công", "field_code": "<mã trường>", "field_name": "<tên trường>", "selected_value": "<giá trị được chọn>"}`
- `400 Bad Request`: Thiếu thông tin bắt buộc
  - Body: `{"error": "Thiếu thông tin bắt buộc"}`
- `500 Internal Server Error`: Lỗi xử lý yêu cầu
  - Body: `{"error": "<thông báo lỗi>"}`

### Admin APIs

#### Trang quản trị

```
GET /admin
```

**Mô tả**: Hiển thị trang dashboard quản trị với thống kê tổng quan về hệ thống

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Xử lý**:
- Kiểm tra quyền admin của người dùng hiện tại
- Tính toán số lượng người dùng trong hệ thống
- Tính toán số lượng biểu mẫu trong lịch sử

**Responses**:
- `200 OK`: Hiển thị trang quản trị với thông tin thống kê
  - Body: Trang HTML với thông tin thống kê
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
- `403 Forbidden`: Không có quyền admin
  - Flash message: `Bạn không có quyền truy cập trang này`

#### Cấu hình web

```
GET /web-config
```

**Mô tả**: Hiển thị trang cấu hình web với các tùy chọn cấu hình hiện tại

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Xử lý**:
- Kiểm tra quyền admin của người dùng hiện tại
- Lấy các giá trị cấu hình hiện tại từ WebConfig

**Responses**:
- `200 OK`: Hiển thị trang cấu hình web với các giá trị hiện tại
  - Body: Trang HTML với form cấu hình
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
- `403 Forbidden`: Không có quyền admin
  - Flash message: `Bạn không có quyền truy cập trang này`

```
POST /web-config
```

**Mô tả**: Cập nhật cấu hình web

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Content-Type**: `application/x-www-form-urlencoded` hoặc `multipart/form-data` (khi có file upload)

**Parameters**:
- **Metadata Form**:
  - `site_title` (string, optional): Tiêu đề trang web
  - `site_description` (string, optional): Mô tả trang web
  - `site_logo` (file, optional): Logo trang web
- **SEO Form**:
  - `meta_title` (string, optional): Tiêu đề SEO
  - `meta_description` (string, optional): Mô tả SEO
  - `og_image` (file, optional): Hình ảnh Open Graph
  - `robots_txt` (string, optional): Nội dung file robots.txt
- **UI Form**:
  - `primary_color` (string, optional): Màu chủ đạo
  - `font_family` (string, optional): Font chữ
  - `layout_type` (string, optional): Kiểu layout
  - `display_mode` (string, optional): Chế độ hiển thị (light/dark)
- **Contact Form**:
  - `contact_phone` (string, optional): Số điện thoại liên hệ
  - `contact_email` (string, optional): Email liên hệ
  - `contact_address` (string, optional): Địa chỉ liên hệ

**Xử lý**:
- Kiểm tra loại form được gửi (metadata_form, seo_form, ui_form, contact_form)
- Lưu các giá trị cấu hình tương ứng
- Xử lý upload file nếu có

**Responses**:
- `200 OK`: Cập nhật cấu hình thành công, chuyển hướng đến trang cấu hình web
  - Flash message: `Cập nhật metadata thành công`, `Cập nhật SEO thành công`, `Cập nhật giao diện thành công`, hoặc `Cập nhật thông tin liên hệ thành công`
- `400 Bad Request`: Dữ liệu không hợp lệ
- `403 Forbidden`: Không có quyền admin

#### Quản lý người dùng

```
GET /admin/users
```

**Mô tả**: Hiển thị trang quản lý người dùng với danh sách tất cả người dùng

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Responses**:
- `200 OK`: Hiển thị trang quản lý người dùng
  - Body: Trang HTML với danh sách người dùng
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
- `403 Forbidden`: Không có quyền admin
  - Flash message: `Bạn không có quyền truy cập trang này`

```
POST /admin/users/add
```

**Mô tả**: Thêm người dùng mới vào hệ thống

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `email` (string, required): Email của người dùng
- `password` (string, required): Mật khẩu của người dùng
- `fullname` (string, optional): Họ và tên đầy đủ
- `role_id` (integer, optional): ID vai trò của người dùng (1: Admin, 2: User)
- `subscription_type` (string, optional): Loại gói đăng ký (free, standard, vip)

**Validation**:
- Email phải đúng định dạng và chưa tồn tại trong hệ thống
- Mật khẩu phải đáp ứng các yêu cầu về độ mạnh

**Responses**:
- `200 OK`: Thêm người dùng thành công
  - Flash message: `Thêm người dùng thành công`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Flash message: `Email đã tồn tại` hoặc thông báo lỗi khác
- `403 Forbidden`: Không có quyền admin

```
POST /admin/users/edit/<int:user_id>
```

**Mô tả**: Chỉnh sửa thông tin người dùng

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `user_id` (integer, required): ID của người dùng
- `email` (string, optional): Email mới
- `fullname` (string, optional): Họ và tên mới
- `role_id` (integer, optional): ID vai trò mới
- `subscription_type` (string, optional): Loại gói đăng ký mới
- `reset_password` (boolean, optional): Đặt lại mật khẩu
- `new_password` (string, optional): Mật khẩu mới (nếu reset_password = true)

**Validation**:
- Email phải đúng định dạng
- Nếu reset_password = true, new_password phải đáp ứng các yêu cầu về độ mạnh

**Responses**:
- `200 OK`: Chỉnh sửa thành công
  - Flash message: `Cập nhật thông tin người dùng thành công`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Flash message: Thông báo lỗi cụ thể
- `404 Not Found`: Không tìm thấy người dùng
  - Flash message: `Không tìm thấy người dùng`
- `403 Forbidden`: Không có quyền admin

```
POST /admin/users/delete/<int:user_id>
```

**Mô tả**: Xóa người dùng khỏi hệ thống

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Parameters**:
- `user_id` (integer, required): ID của người dùng

**Xử lý**:
- Kiểm tra người dùng tồn tại
- Xóa người dùng khỏi cơ sở dữ liệu

**Responses**:
- `200 OK`: Xóa người dùng thành công
  - Flash message: `Xóa người dùng thành công`
- `404 Not Found`: Không tìm thấy người dùng
  - Flash message: `Không tìm thấy người dùng`
- `403 Forbidden`: Không có quyền admin
- `400 Bad Request`: Không thể xóa tài khoản admin hiện tại
  - Flash message: `Không thể xóa tài khoản admin hiện tại`

#### Quản lý biểu mẫu

```
GET /admin/forms
```

**Mô tả**: Hiển thị trang quản lý biểu mẫu với danh sách tất cả biểu mẫu trong hệ thống

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Responses**:
- `200 OK`: Hiển thị trang quản lý biểu mẫu
  - Body: Trang HTML với danh sách biểu mẫu
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
- `403 Forbidden`: Không có quyền admin
  - Flash message: `Bạn không có quyền truy cập trang này`

```
GET /admin/forms/<form_id>
```

**Mô tả**: Xem chi tiết biểu mẫu

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu

**Xử lý**:
- Tìm kiếm biểu mẫu trong lịch sử theo form_id
- Hiển thị chi tiết biểu mẫu và dữ liệu

**Responses**:
- `200 OK`: Hiển thị chi tiết biểu mẫu
  - Body: Trang HTML với chi tiết biểu mẫu
- `404 Not Found`: Không tìm thấy biểu mẫu
  - Flash message: `Không tìm thấy biểu mẫu`
- `403 Forbidden`: Không có quyền admin

```
POST /admin/forms/edit/<form_id>
```

**Mô tả**: Chỉnh sửa biểu mẫu

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Content-Type**: `application/x-www-form-urlencoded`

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu
- `document_name` (string, optional): Tên tài liệu mới
- Các trường dữ liệu của biểu mẫu: Mỗi trường được xác định bởi field_name tương ứng

**Xử lý**:
- Tìm kiếm biểu mẫu trong lịch sử theo form_id
- Cập nhật dữ liệu biểu mẫu
- Lưu lại lịch sử biểu mẫu đã cập nhật

**Responses**:
- `200 OK`: Chỉnh sửa biểu mẫu thành công
  - Flash message: `Cập nhật biểu mẫu thành công`
- `400 Bad Request`: Dữ liệu không hợp lệ
  - Flash message: Thông báo lỗi cụ thể
- `404 Not Found`: Không tìm thấy biểu mẫu
  - Flash message: `Không tìm thấy biểu mẫu`
- `403 Forbidden`: Không có quyền admin

```
POST /admin/forms/delete/<form_id>
```

**Mô tả**: Xóa biểu mẫu khỏi lịch sử

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Parameters**:
- `form_id` (string, required): ID của biểu mẫu

**Xử lý**:
- Tìm kiếm biểu mẫu trong lịch sử theo form_id
- Xóa biểu mẫu khỏi lịch sử
- Lưu lại lịch sử biểu mẫu đã cập nhật

**Responses**:
- `200 OK`: Xóa biểu mẫu thành công
  - Flash message: `Xóa biểu mẫu thành công`
- `404 Not Found`: Không tìm thấy biểu mẫu
  - Flash message: `Không tìm thấy biểu mẫu`
- `403 Forbidden`: Không có quyền admin

```
GET /admin/forms/history
```

**Mô tả**: Xem lịch sử biểu mẫu của tất cả người dùng

**Yêu cầu xác thực**: Có

**Yêu cầu quyền**: Admin (role_id = 1)

**Responses**:
- `200 OK`: Hiển thị lịch sử biểu mẫu
  - Body: Trang HTML với lịch sử biểu mẫu
- `302 Found`: Chuyển hướng đến trang đăng nhập nếu chưa đăng nhập
- `403 Forbidden`: Không có quyền admin
  - Flash message: `Bạn không có quyền truy cập trang này`

## Mã lỗi và Xử lý lỗi

### Mã trạng thái HTTP

- `200 OK`: Yêu cầu thành công
- `302 Found`: Chuyển hướng
- `400 Bad Request`: Yêu cầu không hợp lệ (thiếu tham số, dữ liệu không hợp lệ)
- `401 Unauthorized`: Chưa xác thực (chưa đăng nhập)
- `403 Forbidden`: Không có quyền truy cập (đã đăng nhập nhưng không đủ quyền)
- `404 Not Found`: Không tìm thấy tài nguyên (biểu mẫu, người dùng, tài liệu)
- `500 Internal Server Error`: Lỗi máy chủ

### Định dạng phản hồi lỗi

Khi xảy ra lỗi, API sẽ trả về phản hồi JSON với cấu trúc sau:

```json
{
  "error": "Thông báo lỗi",
  "field": "Tên trường gây lỗi (nếu có)",
  "code": "Mã lỗi (nếu có)"
}
```

Hoặc sử dụng Flash message trong trường hợp chuyển hướng:

```
Flash message: "Thông báo lỗi"
```

### Xử lý lỗi phổ biến

- **Lỗi xác thực**: Đảm bảo người dùng đã đăng nhập và có session cookie hợp lệ
- **Lỗi quyền truy cập**: Kiểm tra vai trò của người dùng (admin, user)
- **Lỗi dữ liệu**: Kiểm tra tính hợp lệ của dữ liệu trước khi gửi
- **Lỗi tài nguyên**: Đảm bảo ID của tài nguyên (biểu mẫu, người dùng) tồn tại

## Ví dụ sử dụng API

### Đăng nhập

**Request**:
```
POST /login
Content-Type: application/x-www-form-urlencoded

email=user@example.com&password=password123
```

**Response thành công**:
```
HTTP/1.1 302 Found
Location: /dashboard
Set-Cookie: session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...; Path=/; HttpOnly
```

**Response thất bại**:
```
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"error": "Email hoặc mật khẩu không chính xác"}
```

### Tự động điền trường bằng AI

**Request**:
```
POST /AI_FILL
Content-Type: application/json

{
  "field_name": "field_1"
}
```

**Response thành công**:
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "value": "Nguyễn Văn A",
  "suggestions": ["Nguyễn Văn A", "Trần Thị B", "Lê Văn C"],
  "confidence": 0.85,
  "field_name": "Họ và tên",
  "field_code": "field_1"
}
```

**Response thất bại**:
```
HTTP/1.1 400 Bad Request
Content-Type: application/json

{"error": "Field code is required"}
```

### Lưu và tạo tài liệu docx

**Request**:
```
POST /save-and-generate-docx
Content-Type: application/x-www-form-urlencoded

document_name=Don_xin_viec&field_1=Nguyễn Văn A&field_2=Công ty ABC&field_3=Nhân viên kế toán
```

**Response thành công**:
```
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="Don_xin_viec.docx"

(binary data)
```
Set-Cookie: session=...; Path=/; HttpOnly
```

### Tải lên tài liệu

**Request**:
```
POST /upload
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="document.docx"
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document

(binary data)
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**Response**:
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": true,
  "message": "File uploaded successfully",
  "file_path": "uploads/12345678-1234-1234-1234-123456789012_document.docx"
}
```

### Tự động điền trường

**Request**:
```
POST /auto_fill_field
Content-Type: application/json

{
  "field_code": "field1",
  "field_name": "Họ và tên",
  "current_values": {
    "field2": "Công ty ABC",
    "field3": "Nhân viên kế toán"
  }
}
```

**Response**:
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "suggested_value": "Nguyễn Văn A"
}
```

## Lưu ý

- Tất cả các API yêu cầu xác thực sẽ trả về mã lỗi 401 nếu người dùng chưa đăng nhập.
- Các API admin yêu cầu người dùng có vai trò admin, nếu không sẽ trả về mã lỗi 403.
- Các API liên quan đến tạo tài liệu docx có thể bị giới hạn số lượt tải xuống tùy theo gói dịch vụ của người dùng.