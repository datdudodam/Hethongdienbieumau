# utils/fuzzy_matcher.py
import re
import difflib
import unicodedata
import Levenshtein
from typing import Dict, List, Tuple, Set, Optional, Union, Any

class FuzzyMatcher:
    """
    Lớp hỗ trợ fuzzy matching cho việc nhận diện tên trường trong văn bản
    với khả năng xử lý sai chính tả, văn bản không chuẩn hóa và các mẫu câu linh hoạt
    """
    
    def __init__(self):
        # Từ điển đồng nghĩa cho các trường phổ biến
        self.synonym_map = self._build_synonym_map()
        # Từ điển sửa lỗi chính tả phổ biến
        self.spelling_corrections = self._build_spelling_corrections()
        # Các mẫu câu phổ biến để nhận diện ngữ cảnh
        self.context_patterns = self._build_context_patterns()
        # Danh sách từ khóa đặc biệt cần xử lý riêng
        self.special_words = self._build_special_words()
        # Cache để lưu kết quả xử lý
        self.processed_text_cache = {}
        # Ngưỡng tương đồng cho fuzzy matching
        self.similarity_threshold = 0.75
        # Ngưỡng tương đồng cho Levenshtein
        self.levenshtein_threshold = 2
    
    def _build_synonym_map(self) -> Dict[str, List[str]]:
        """
        Xây dựng từ điển đồng nghĩa mở rộng cho các trường phổ biến
        với khả năng nhận diện nâng cao cho các trường hợp văn bản không chuẩn hóa
        """
        return {
            'họ tên': [
                # Tiếng Việt chuẩn
                'hovaten', 'ho va ten', 'ho và tên', 'hoten', 'họ_tên', 'tên', 
                'họ và tên', 'tên đầy đủ', 'tên người', 'tên người khai', 'người khai',
                # Tiếng Anh
                'fullname', 'full name', 'name', 'your name', 'applicant name', 'candidate name',
                # Biến thể và lỗi chính tả
                'ho ten', 'họ ten', 'ho tên', 'tên họ', 'ten ho', 'họ và ten', 'ho và tên',
                'tên đầy đủ của bạn', 'tên của bạn', 'tên của ứng viên', 'tên người làm đơn',
                # Ngữ cảnh
                'người làm đơn', 'người ký tên', 'người đề nghị', 'người yêu cầu', 'ứng viên',
                'người nộp đơn', 'bên a', 'bên b', 'bên thuê', 'bên được thuê'
            ],
            'địa chỉ': [
                # Tiếng Việt chuẩn
                'diachi', 'địa_chỉ', 'địa chỉ', 'chỗ ở', 'nơi ở', 'địa chỉ hiện tại',
                'địa chỉ thường trú', 'địa chỉ tạm trú', 'nơi cư trú', 'hộ khẩu thường trú',
                # Tiếng Anh
                'address', 'place', 'location', 'home address', 'residence', 'current address', 
                'address line', 'permanent address', 'residential address', 'mailing address',
                # Biến thể và lỗi chính tả
                'dia chi', 'đia chỉ', 'địa chi', 'địa chỉ nhà', 'chỗ ở hiện tại', 'nơi sinh sống',
                'nơi ở hiện nay', 'nơi cư trú hiện tại', 'địa chỉ liên lạc', 'địa chỉ liên hệ',
                # Ngữ cảnh
                'cư trú tại', 'sinh sống tại', 'thường trú tại', 'tạm trú tại', 'hiện ở tại'
            ],
            'điện thoại': [
                # Tiếng Việt chuẩn
                'sdt', 'so_dien_thoai', 'so dien thoai', 'đt', 'số điện thoại', 'số đt', 'điện thoại di động',
                'số điện thoại di động', 'số điện thoại liên lạc', 'số điện thoại liên hệ', 'hotline',
                # Tiếng Anh
                'phone', 'tel', 'telephone', 'mobile', 'mobile phone', 'phone number', 'contact number',
                'cell phone', 'contact phone', 'telephone number', 'contact tel',
                # Biến thể và lỗi chính tả
                'dien thoai', 'điên thoại', 'đien thoai', 'điện thoai', 'so dt', 'số dt', 'sdt di động',
                'điện thoại liên hệ', 'điện thoại liên lạc', 'số liên lạc', 'số liên hệ',
                # Ngữ cảnh
                'liên hệ qua số', 'gọi số', 'liên lạc qua số', 'liên hệ theo số'
            ],
            'email': [
                # Tiếng Việt chuẩn
                'email', 'thư điện tử', 'địa chỉ email', 'hòm thư điện tử', 'email liên hệ',
                # Tiếng Anh
                'e-mail', 'mail', 'email address', 'e mail', 'electronic mail', 'mail address',
                # Biến thể và lỗi chính tả
                'thu dien tu', 'thư điên tử', 'thư điện tu', 'địa chỉ thư điện tử', 'hòm thư',
                'email liên lạc', 'email liên hệ', 'địa chỉ mail',
                # Ngữ cảnh
                'liên hệ qua email', 'gửi email tới', 'liên lạc qua email'
            ],
            'ngày sinh': [
                # Tiếng Việt chuẩn
                'ngày sinh', 'sinh ngày', 'ngày tháng năm sinh', 'ngày/tháng/năm sinh',
                # Tiếng Anh
                'dob', 'birth date', 'birthdate', 'date of birth', 'd.o.b', 'birth', 'born on',
                'birth day', 'birthday',
                # Biến thể và lỗi chính tả
                'ngay sinh', 'ngày sịnh', 'sinh ngay', 'ngày tháng sinh', 'ngày/tháng sinh',
                'ngày_sinh', 'ngày_tháng_năm_sinh',
                # Ngữ cảnh
                'sinh ra ngày', 'sinh vào ngày', 'sinh nhật', 'ngày ra đời'
            ],
            'giới tính': [
                # Tiếng Việt chuẩn
                'giới tính', 'nam/nữ', 'nam nữ', 'phái', 'giới',
                # Tiếng Anh
                'gender', 'sex', 'male/female', 'm/f', 'gender identity',
                # Biến thể và lỗi chính tả
                'gioi tinh', 'giới tinh', 'gioi tính', 'nam hay nữ', 'nam hoặc nữ',
                # Ngữ cảnh
                'là nam hay nữ', 'thuộc giới tính', 'thuộc phái'
            ],
            'mã số thuế': [
                # Tiếng Việt chuẩn
                'mã số thuế', 'mst', 'mã thuế', 'số thuế',
                # Tiếng Anh
                'tax code', 'tax id', 'tax identification number', 'tin',
                # Biến thể và lỗi chính tả
                'ma so thue', 'mã sô thuế', 'mã số thue', 'mã thuê',
                # Ngữ cảnh
                'mã số thuế cá nhân', 'mã số thuế doanh nghiệp'
            ],
            'quốc tịch': [
                # Tiếng Việt chuẩn
                'quốc tịch', 'quốc gia', 'công dân nước',
                # Tiếng Anh
                'nationality', 'country', 'citizenship', 'nation',
                # Biến thể và lỗi chính tả
                'quoc tich', 'quốc tich', 'quoc tịch', 'quốc gia gốc',
                # Ngữ cảnh
                'mang quốc tịch', 'có quốc tịch', 'thuộc quốc tịch'
            ],
            'thành phố': [
                # Tiếng Việt chuẩn
                'thành phố', 'tỉnh thành', 'tỉnh/thành phố', 'tỉnh', 'tp', 't.p',
                # Tiếng Anh
                'city', 'province', 'town', 'municipality',
                # Biến thể và lỗi chính tả
                'thanh pho', 'thành phô', 'thanh phố', 'tinh thanh', 'tinh/thanh pho',
                # Ngữ cảnh
                'sống tại thành phố', 'thuộc thành phố', 'thuộc tỉnh'
            ],
            'quận huyện': [
                # Tiếng Việt chuẩn
                'quận', 'huyện', 'quận/huyện', 'q.', 'h.',
                # Tiếng Anh
                'district', 'county', 'borough',
                # Biến thể và lỗi chính tả
                'quan', 'huyen', 'quận huyên', 'quân huyện', 'quận/huyên',
                # Ngữ cảnh
                'thuộc quận', 'thuộc huyện', 'nằm ở quận'
            ],
            'phường xã': [
                # Tiếng Việt chuẩn
                'phường', 'xã', 'phường/xã', 'p.', 'x.',
                # Tiếng Anh
                'ward', 'commune', 'village',
                # Biến thể và lỗi chính tả
                'phuong', 'xa', 'phường xa', 'phuong/xa', 'phường/xa',
                # Ngữ cảnh
                'thuộc phường', 'thuộc xã', 'nằm ở phường'
            ],
            'chuyên ngành': [
                # Tiếng Việt chuẩn
                'chuyên ngành', 'ngành học', 'ngành', 'chuyên môn', 'lĩnh vực học tập',
                # Tiếng Anh
                'major', 'specialization', 'field of study', 'discipline', 'concentration',
                # Biến thể và lỗi chính tả
                'chuyen nganh', 'chuyên nganh', 'chuyen ngành', 'ngành hoc', 'nganh học',
                # Ngữ cảnh
                'học chuyên ngành', 'theo học ngành', 'chuyên về ngành'
            ],
            'trường học': [
                # Tiếng Việt chuẩn
                'trường', 'trường học', 'cơ sở đào tạo', 'học viện', 'viện', 'đại học',
                # Tiếng Anh
                'school', 'university', 'college', 'academy', 'institute', 'institution',
                # Biến thể và lỗi chính tả
                'truong', 'truong hoc', 'trường hoc', 'truờng học', 'đai học', 'dai hoc',
                # Ngữ cảnh
                'học tại trường', 'tốt nghiệp trường', 'sinh viên trường'
            ],
            'công ty': [
                # Tiếng Việt chuẩn
                'công ty', 'doanh nghiệp', 'cơ quan', 'đơn vị công tác', 'nơi làm việc',
                # Tiếng Anh
                'company', 'organization', 'workplace', 'employer', 'firm', 'corporation',
                # Biến thể và lỗi chính tả
                'cong ty', 'công ti', 'cong ti', 'doanh nghiêp', 'co quan', 'nơi làm viêc',
                # Ngữ cảnh
                'làm việc tại công ty', 'công tác tại', 'làm cho công ty'
            ],
            'chức vụ': [
                # Tiếng Việt chuẩn
                'chức vụ', 'vị trí', 'chức danh', 'vai trò', 'cấp bậc',
                # Tiếng Anh
                'position', 'title', 'job title', 'role', 'rank', 'designation',
                # Biến thể và lỗi chính tả
                'chuc vu', 'chức vu', 'chuc vụ', 'vị tri', 'vi trí', 'chức dánh',
                # Ngữ cảnh
                'giữ chức vụ', 'đảm nhận vị trí', 'làm việc ở vị trí'
            ],
            'lương': [
                # Tiếng Việt chuẩn
                'lương', 'mức lương', 'thu nhập', 'tiền lương', 'lương tháng',
                # Tiếng Anh
                'salary', 'wage', 'income', 'pay', 'compensation', 'remuneration',
                # Biến thể và lỗi chính tả
                'luong', 'mức luong', 'thu nhap', 'tiền luong', 'luong tháng',
                # Ngữ cảnh
                'mức lương mong muốn', 'lương đề nghị', 'mức thu nhập'
            ],
            'ngày ký': [
                # Tiếng Việt chuẩn
                'ngày ký', 'ký ngày', 'ngày tháng ký', 'ngày lập', 'ngày viết',
                # Tiếng Anh
                'date of signing', 'signed date', 'execution date', 'date',
                # Biến thể và lỗi chính tả
                'ngay ky', 'ký ngay', 'ngày tháng ky', 'ngay lập', 'ngay viết',
                # Ngữ cảnh
                'ký tên ngày', 'làm tại ... ngày', 'lập vào ngày'
            ]
        }
    
    def _build_spelling_corrections(self) -> Dict[str, str]:
        """
        Xây dựng từ điển sửa lỗi chính tả phổ biến
        """
        return {
            'họ vâ tên': 'họ và tên',
            'địa chi': 'địa chỉ',
            'đia chỉ': 'địa chỉ',
            'điên thoại': 'điện thoại',
            'dien thoai': 'điện thoại',
            'e-mail': 'email',
            'ngày sịnh': 'ngày sinh',
            'ngay sinh': 'ngày sinh',
            'gioi tinh': 'giới tính',
            'quoc tich': 'quốc tịch',
            'thanh pho': 'thành phố',
            'quan huyen': 'quận huyện',
            'phuong xa': 'phường xã',
            'chuyen nganh': 'chuyên ngành',
            'truong hoc': 'trường học',
            'cong ty': 'công ty',
            'chuc vu': 'chức vụ'
        }
    
    def _build_context_patterns(self) -> Dict[str, List[str]]:
        """
        Xây dựng các mẫu câu phổ biến để nhận diện ngữ cảnh với khả năng nhận diện nâng cao
        cho các trường hợp tên trường không nằm cố định theo mẫu
        """
        return {
            'học vấn': [
                # Mẫu câu chuẩn
                r'tôi\s+từng\s+học\s+tại', 
                r'sinh\s+viên\s+(của|tại|trường)', 
                r'tốt\s+nghiệp\s+(từ|tại|trường)', 
                r'đã\s+học\s+tại', 
                r'trường\s+\w+',
                r'chuyên\s+ngành',
                r'ngành\s+học',
                # Mẫu câu linh hoạt
                r'học\s+tại\s+trường',
                r'theo\s+học\s+(tại|ngành)',
                r'(đang|đã)\s+là\s+sinh\s+viên',
                r'(đang|đã)\s+học\s+(tại|ngành)',
                r'bằng\s+cấp',
                r'văn\s+bằng',
                r'chứng\s+chỉ',
                r'khóa\s+học',
                r'(đại\s+học|cao\s+đẳng|trung\s+cấp)',
                r'chuyên\s+môn',
                r'lĩnh\s+vực\s+học\s+tập',
                r'lớp\s+\d+',
                r'niên\s+khóa',
                r'khóa\s+\d+',
                # Mẫu câu có thể bị lỗi chính tả
                r'truong\s+hoc',
                r'tot\s+nghiep',
                r'bang\s+cap',
                r'chuyen\s+nganh'
            ],
            'kinh nghiệm': [
                # Mẫu câu chuẩn
                r'làm\s+việc\s+tại', 
                r'công\s+ty\s+\w+', 
                r'vị\s+trí', 
                r'chức\s+vụ', 
                r'kinh\s+nghiệm',
                r'đã\s+từng\s+làm',
                r'nhiệm\s+vụ',
                # Mẫu câu linh hoạt
                r'(đang|đã|từng)\s+(công\s+tác|làm\s+việc|đảm\s+nhận)',
                r'(kinh\s+nghiệm|thời\s+gian)\s+làm\s+việc',
                r'(năm|tháng)\s+kinh\s+nghiệm',
                r'(phụ\s+trách|quản\s+lý)\s+(mảng|phòng|bộ\s+phận)',
                r'(làm|công\s+tác)\s+trong\s+lĩnh\s+vực',
                r'(đảm\s+nhận|giữ)\s+chức\s+vụ',
                r'(trách\s+nhiệm|công\s+việc)\s+chính',
                r'dự\s+án\s+(đã|từng)\s+tham\s+gia',
                r'thành\s+tích\s+nổi\s+bật',
                r'kỹ\s+năng\s+chuyên\s+môn',
                # Mẫu câu có thể bị lỗi chính tả
                r'kinh\s+nghiem',
                r'cong\s+ty',
                r'vi\s+tri',
                r'chuc\s+vu'
            ],
            'thông tin cá nhân': [
                # Mẫu câu chuẩn
                r'sinh\s+ngày', 
                r'quê\s+quán', 
                r'nơi\s+sinh', 
                r'địa\s+chỉ', 
                r'liên\s+hệ',
                r'số\s+điện\s+thoại',
                r'email',
                r'giới\s+tính',
                # Mẫu câu linh hoạt
                r'(sinh|ngày)\s+(ngày|tháng|năm)',
                r'ngày\s+tháng\s+năm\s+sinh',
                r'(quê|quê\s+quán|nơi\s+sinh)\s+(tại|là)',
                r'(địa\s+chỉ|nơi\s+ở|chỗ\s+ở)\s+(hiện\s+tại|hiện\s+nay)',
                r'(liên\s+hệ|liên\s+lạc)\s+(qua|theo|tại)',
                r'(số|đt|sđt|điện\s+thoại)\s*:',
                r'(mail|email|thư\s+điện\s+tử)\s*:',
                r'(nam|nữ|giới\s+tính)\s*:',
                r'(cmnd|cccd|căn\s+cước|chứng\s+minh\s+nhân\s+dân)\s*(số|:)',
                r'(dân\s+tộc|tôn\s+giáo)\s*:',
                r'(tình\s+trạng|trạng\s+thái)\s+hôn\s+nhân',
                r'(ngày|nơi)\s+cấp',
                # Mẫu câu có thể bị lỗi chính tả
                r'dia\s+chi',
                r'so\s+dien\s+thoai',
                r'gioi\s+tinh',
                r'que\s+quan'
            ],
            'thông tin hợp đồng': [
                # Mẫu câu liên quan đến hợp đồng, giấy tờ pháp lý
                r'(hợp\s+đồng|giấy\s+tờ)\s+(số|ngày)',
                r'(ký\s+kết|thực\s+hiện)\s+ngày',
                r'(bên\s+a|bên\s+b|bên\s+thuê|bên\s+được\s+thuê)',
                r'(đại\s+diện|người\s+đại\s+diện)\s+(bởi|là)',
                r'(chức\s+vụ|vai\s+trò)\s+(là|:)',
                r'(thời\s+hạn|thời\s+gian)\s+(hợp\s+đồng|thực\s+hiện)',
                r'(giá\s+trị|trị\s+giá)\s+(hợp\s+đồng|dịch\s+vụ)',
                r'(thanh\s+toán|chi\s+trả)\s+(theo|vào)',
                r'(điều\s+khoản|điều\s+kiện)\s+(chung|riêng)',
                r'(quyền|nghĩa\s+vụ)\s+(và|của)'
            ]
        }
    
    def _build_special_words(self) -> Set[str]:
        """
        Xây dựng danh sách từ khóa đặc biệt cần xử lý riêng
        """
        return {
            "ngày", "tháng", "năm", "họ tên", "địa chỉ", "điện thoại", "email",
            "giới tính", "quốc tịch", "thành phố", "quận", "huyện", "phường", "xã"
        }
    
    def normalize_text(self, text: str) -> str:
        """
        Chuẩn hóa văn bản: loại bỏ dấu câu, chuyển về chữ thường, sửa lỗi chính tả
        và xử lý các trường hợp văn bản không chuẩn hóa
        """
        if not text:
            return ""
        
        # Kiểm tra cache
        cache_key = hash(text)
        if cache_key in self.processed_text_cache:
            return self.processed_text_cache[cache_key]
        
        # Chuẩn hóa Unicode và chuyển đổi về chữ thường
        normalized = unicodedata.normalize('NFC', text.lower())
        
        # Loại bỏ các ký tự đặc biệt nhưng giữ lại dấu tiếng Việt
        # Cải tiến: giữ lại dấu câu quan trọng như dấu chấm, phẩy để phân tích ngữ cảnh tốt hơn
        cleaned = re.sub(r'[^\w\s\.,;:\-_áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]', ' ', normalized)
        
        # Chuẩn hóa các dấu câu (thêm khoảng trắng sau dấu câu nếu không có)
        cleaned = re.sub(r'([\.,;:])([^\s])', r'\1 \2', cleaned)
        
        # Xử lý các trường hợp viết tắt phổ biến
        abbreviations = {
            'đc': 'được',
            'ko': 'không',
            'k': 'không',
            'khi nao': 'khi nào',
            'dc': 'được',
            'ng': 'người',
            'tg': 'thời gian',
            'sdt': 'số điện thoại',
            'đt': 'điện thoại',
            'tp': 'thành phố',
            'hcm': 'hồ chí minh',
            'hn': 'hà nội',
            'đn': 'đà nẵng',
            'sv': 'sinh viên',
            'gv': 'giáo viên',
            'nv': 'nhân viên',
            'ql': 'quản lý',
            'kh': 'khách hàng',
            'vn': 'việt nam'
        }
        
        # Thay thế các từ viết tắt
        for abbr, full in abbreviations.items():
            cleaned = re.sub(r'\b' + re.escape(abbr) + r'\b', full, cleaned)
        
        # Thay thế từ đồng nghĩa phổ biến - cải tiến: sử dụng từ điển đồng nghĩa mở rộng
        for target, synonyms in sorted(self.synonym_map.items(), key=lambda x: len(x[0]), reverse=True):
            for synonym in sorted(synonyms, key=len, reverse=True):
                # Sử dụng fuzzy matching cho từ đồng nghĩa
                pattern = r'\b' + re.escape(synonym).replace('\\ ', '\s*') + r'\b'
                cleaned = re.sub(pattern, target, cleaned)
        
        # Sửa lỗi chính tả - cải tiến: xử lý các lỗi chính tả phổ biến trong tiếng Việt
        for misspelled, correct in self.spelling_corrections.items():
            # Sử dụng fuzzy matching cho việc sửa lỗi chính tả
            pattern = r'\b' + re.escape(misspelled).replace('\\ ', '\s*') + r'\b'
            cleaned = re.sub(pattern, correct, cleaned)
        
        # Xử lý các trường hợp thiếu dấu trong tiếng Việt
        vietnamese_chars = {
            'a': ['á', 'à', 'ả', 'ã', 'ạ', 'ă', 'ắ', 'ằ', 'ẳ', 'ẵ', 'ặ', 'â', 'ấ', 'ầ', 'ẩ', 'ẫ', 'ậ'],
            'e': ['é', 'è', 'ẻ', 'ẽ', 'ẹ', 'ê', 'ế', 'ề', 'ể', 'ễ', 'ệ'],
            'i': ['í', 'ì', 'ỉ', 'ĩ', 'ị'],
            'o': ['ó', 'ò', 'ỏ', 'õ', 'ọ', 'ô', 'ố', 'ồ', 'ổ', 'ỗ', 'ộ', 'ơ', 'ớ', 'ờ', 'ở', 'ỡ', 'ợ'],
            'u': ['ú', 'ù', 'ủ', 'ũ', 'ụ', 'ư', 'ứ', 'ừ', 'ử', 'ữ', 'ự'],
            'y': ['ý', 'ỳ', 'ỷ', 'ỹ', 'ỵ'],
            'd': ['đ']
        }
        
        # Loại bỏ khoảng trắng thừa
        result = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Lưu vào cache
        self.processed_text_cache[cache_key] = result
        return result
    
    def find_field_name(self, text: str, field_code_position: int, context_window: int = 200) -> str:
        """
        Tìm tên trường từ văn bản dựa trên vị trí của mã trường [_123_]
        Cải tiến với khả năng nhận diện nâng cao cho các trường hợp đặc biệt
        
        Args:
            text: Văn bản cần phân tích
            field_code_position: Vị trí bắt đầu của mã trường trong văn bản
            context_window: Số ký tự tối đa xem xét trước mã trường
            
        Returns:
            Tên trường tìm được hoặc chuỗi rỗng nếu không tìm thấy
        """
        if not text or field_code_position <= 0:
            return ""
        
        # Lấy đoạn văn bản trước mã trường để phân tích (tăng context_window để bắt được các mẫu câu dài hơn)
        start_index = max(0, field_code_position - context_window)
        preceding_text = text[start_index:field_code_position].strip()
        
        # Lấy thêm một đoạn văn bản sau mã trường để phân tích ngữ cảnh tốt hơn
        end_index = min(len(text), field_code_position + 50)
        following_text = text[field_code_position:end_index].strip()
        
        # Khởi tạo tên trường và điểm tin cậy
        field_name = ""
        confidence_score = 0.0
        candidate_fields = []
        
        # 1. Kiểm tra các từ đặc biệt trước với độ tin cậy cao
        i = field_code_position - 1
        while i >= 0 and text[i] == " ":
            i -= 1
            
        for word in self.special_words:
            # Tìm từ đặc biệt với fuzzy matching (cho phép sai lệch nhẹ)
            search_window = text[max(0, i - len(word) - 15):field_code_position].lower()
            
            # Tìm chính xác
            if search_window.find(word) != -1:
                candidate_fields.append((word, 0.95))  # Độ tin cậy cao
            
            # Tìm với Levenshtein distance cải tiến
            words_in_window = search_window.split()
            for potential_word in words_in_window:
                # Chỉ xem xét các từ có độ dài tương đương
                if abs(len(potential_word) - len(word)) <= 3:
                    # Sử dụng thuật toán Levenshtein
                    distance = Levenshtein.distance(potential_word, word)
                    if distance <= self.levenshtein_threshold:
                        # Tính điểm tin cậy dựa trên khoảng cách Levenshtein
                        confidence = 0.9 - (distance * 0.1)
                        candidate_fields.append((word, confidence))
            
            # Tìm với fuzzy matching cải tiến
            for j in range(len(search_window) - 2):
                if j + len(word) + 2 <= len(search_window):
                    substring = search_window[j:j + len(word) + 2]
                    similarity = self.calculate_similarity(substring, word, 'hybrid')
                    
                    # Điều chỉnh ngưỡng tương đồng dựa trên độ dài từ
                    threshold = 0.75 if len(word) < 5 else 0.7
                    
                    if similarity > threshold:
                        candidate_fields.append((word, similarity))
        
        # 2. Tìm theo chữ in hoa (thường là tiêu đề trường)
        uppercase_field = ""
        for j in range(i, max(0, i-70), -1):  # Tăng phạm vi tìm kiếm
            if j < len(text) and text[j].isupper():
                # Tìm điểm bắt đầu của cụm từ in hoa
                start_j = j
                while start_j > 0 and (text[start_j-1].isupper() or text[start_j-1] == ' ' or text[start_j-1] == ':'):
                    start_j -= 1
                uppercase_field = text[start_j:field_code_position].strip()
                
                # Loại bỏ các ký tự không cần thiết ở cuối
                uppercase_field = re.sub(r'[\s:*]+$', '', uppercase_field)
                
                if uppercase_field:
                    # Độ tin cậy phụ thuộc vào độ dài và khoảng cách đến mã trường
                    confidence = 0.85 - (0.01 * (i - j))
                    candidate_fields.append((uppercase_field, confidence))
                    break
        
        # 3. Tìm theo mẫu câu phổ biến với cải tiến nhận diện ngữ cảnh
        for context_type, patterns in self.context_patterns.items():
            for pattern in patterns:
                matches_context = re.search(pattern, preceding_text.lower())
                if matches_context:
                    # Lấy đoạn văn bản sau mẫu câu làm tên trường
                    context_end = matches_context.end()
                    context_field = preceding_text[context_end:].strip()
                    
                    # Cải tiến: Tìm từ cuối cùng hoặc cụm từ có ý nghĩa
                    # Loại bỏ các từ nối không cần thiết ở cuối
                    context_field = re.sub(r'\s+(là|của|cho|với|và|hoặc|hay|tại|về)\s*$', '', context_field)
                    
                    # Nếu tên trường quá dài, cắt bớt nhưng thông minh hơn
                    if len(context_field) > 40:
                        # Tìm dấu câu cuối cùng để cắt tại đó
                        last_punct = max(context_field.rfind('.'), context_field.rfind(','), 
                                        context_field.rfind(':'), context_field.rfind(';'))
                        if last_punct > 10:  # Nếu có dấu câu và không quá gần đầu chuỗi
                            context_field = context_field[last_punct+1:].strip()
                        else:
                            # Nếu không có dấu câu, lấy 30 ký tự cuối
                            context_field = context_field[-30:].strip()
                    
                    if context_field:
                        # Độ tin cậy phụ thuộc vào loại ngữ cảnh và độ dài của mẫu câu
                        pattern_confidence = 0.7 + (0.05 * len(pattern) / 50)  # Mẫu câu dài thường chính xác hơn
                        candidate_fields.append((context_field, pattern_confidence))

        
        # 4. Chọn tên trường tốt nhất từ các ứng viên
        if candidate_fields:
            # Sắp xếp theo độ tin cậy giảm dần
            candidate_fields.sort(key=lambda x: x[1], reverse=True)
            
            # Lấy ứng viên có độ tin cậy cao nhất
            field_name, confidence_score = candidate_fields[0]
            
            # Nếu có nhiều ứng viên với độ tin cậy gần nhau, ưu tiên ứng viên ngắn gọn hơn
            if len(candidate_fields) > 1:
                for candidate, score in candidate_fields[1:3]:  # Chỉ xem xét top 3 ứng viên
                    if score > confidence_score - 0.1:  # Nếu độ tin cậy chỉ kém 0.1
                        if len(candidate) < len(field_name) and len(candidate) > 3:  # Và ngắn gọn hơn
                            field_name = candidate
                            confidence_score = score
        
        # 5. Sửa lỗi chính tả trong tên trường
        if field_name:
            field_name_lower = field_name.lower()
            for misspelled, correct in self.spelling_corrections.items():
                if field_name_lower.find(misspelled) != -1:
                    field_name = field_name.lower().replace(misspelled, correct)
                    break
            
            # Chuẩn hóa tên trường (viết hoa chữ cái đầu và loại bỏ ký tự đặc biệt ở đầu/cuối)
            field_name = re.sub(r'^[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]+', '', field_name)
            field_name = re.sub(r'[^\w\sáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ]+$', '', field_name)
            field_name = field_name.strip().capitalize()
        
        return field_name
    
    def calculate_similarity(self, str1: str, str2: str, method: str = 'levenshtein') -> float:
        """
        Tính toán độ tương đồng giữa hai chuỗi sử dụng nhiều phương pháp khác nhau
        
        Args:
            str1: Chuỗi thứ nhất
            str2: Chuỗi thứ hai
            method: Phương pháp tính toán ('levenshtein', 'sequence', 'hybrid')
            
        Returns:
            Độ tương đồng giữa hai chuỗi (0.0 - 1.0)
        """
        if not str1 or not str2:
            return 0.0
            
        # Chuẩn hóa chuỗi trước khi so sánh
        str1 = self.normalize_text(str1.lower())
        str2 = self.normalize_text(str2.lower())
        
        if method == 'levenshtein':
            # Sử dụng khoảng cách Levenshtein và chuẩn hóa
            max_len = max(len(str1), len(str2))
            if max_len == 0:
                return 1.0  # Hai chuỗi rỗng được coi là giống nhau
            distance = Levenshtein.distance(str1, str2)
            # Chuyển đổi khoảng cách thành độ tương đồng (0-1)
            return 1.0 - (distance / max_len)
            
        elif method == 'sequence':
            # Sử dụng SequenceMatcher từ difflib
            return difflib.SequenceMatcher(None, str1, str2).ratio()
            
        elif method == 'hybrid':
            # Kết hợp cả hai phương pháp để có kết quả tốt nhất
            levenshtein_sim = 1.0 - (Levenshtein.distance(str1, str2) / max(len(str1), len(str2), 1))
            sequence_sim = difflib.SequenceMatcher(None, str1, str2).ratio()
            # Trọng số cho từng phương pháp
            return 0.6 * levenshtein_sim + 0.4 * sequence_sim
            
        else:
            # Mặc định sử dụng SequenceMatcher
            return difflib.SequenceMatcher(None, str1, str2).ratio()
    
    def get_field_context(self, text: str, field_name: str, field_code_position: int) -> str:
        """
        Phân tích ngữ cảnh của trường để hiểu rõ hơn về mục đích của trường
        
        Args:
            text: Văn bản cần phân tích
            field_name: Tên trường đã tìm được
            field_code_position: Vị trí của mã trường trong văn bản
            
        Returns:
            Thông tin ngữ cảnh của trường
        """
        # Lấy đoạn văn bản xung quanh mã trường (50 ký tự trước và sau)
        start_index = max(0, field_code_position - 50)
        end_index = min(len(text), field_code_position + 50)
        context_text = text[start_index:end_index]
        
        # Phân tích ngữ cảnh dựa trên tên trường và văn bản xung quanh
        context_info = ""
        
        # Xác định loại trường dựa trên tên
        field_name_lower = field_name.lower()
        
        if any(keyword in field_name_lower for keyword in ["họ tên", "tên", "name"]):
            context_info = "personal_info:name"
        elif any(keyword in field_name_lower for keyword in ["địa chỉ", "address"]):
            context_info = "personal_info:address"
        elif any(keyword in field_name_lower for keyword in ["điện thoại", "phone", "sdt"]):
            context_info = "personal_info:phone"
        elif any(keyword in field_name_lower for keyword in ["email", "mail"]):
            context_info = "personal_info:email"
        elif any(keyword in field_name_lower for keyword in ["ngày sinh", "birth"]):
            context_info = "personal_info:birth_date"
        elif any(keyword in field_name_lower for keyword in ["giới tính", "gender", "sex"]):
            context_info = "personal_info:gender"
        elif any(keyword in field_name_lower for keyword in ["trường", "school", "university"]):
            context_info = "education:school"
        elif any(keyword in field_name_lower for keyword in ["ngành", "chuyên ngành", "major"]):
            context_info = "education:major"
        elif any(keyword in field_name_lower for keyword in ["công ty", "company", "workplace"]):
            context_info = "experience:company"
        elif any(keyword in field_name_lower for keyword in ["chức vụ", "position", "title"]):
            context_info = "experience:position"
        else:
            # Phân tích ngữ cảnh từ văn bản xung quanh
            for context_type, patterns in self.context_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, context_text.lower()):
                        context_info = f"{context_type}:general"
                        break
                if context_info:
                    break
        
        return context_info if context_info else "unknown"