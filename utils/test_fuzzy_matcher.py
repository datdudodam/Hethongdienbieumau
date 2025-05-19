# utils/test_fuzzy_matcher.py
import unittest
from fuzzy_matcher import FuzzyMatcher

class TestFuzzyMatcher(unittest.TestCase):
    """Kiểm tra hiệu quả của lớp FuzzyMatcher với các trường hợp đặc biệt"""
    
    def setUp(self):
        self.matcher = FuzzyMatcher()
    
    def test_find_field_name_standard_case(self):
        """Kiểm tra trường hợp chuẩn"""
        text = "Họ và tên: [_123_]"
        field_name = self.matcher.find_field_name(text, text.find("[_123_]"))
        self.assertEqual(field_name, "Họ và tên")
    
    def test_find_field_name_with_typo(self):
        """Kiểm tra trường hợp có lỗi chính tả"""
        text = "Họ vâ tên: [_123_]"
        field_name = self.matcher.find_field_name(text, text.find("[_123_]"))
        self.assertEqual(field_name, "Họ và tên")
    
    def test_find_field_name_with_context(self):
        """Kiểm tra trường hợp tên trường nằm trong ngữ cảnh"""
        text = "Tôi từng học tại trường Đại học Bách Khoa Hà Nội [_123_]"
        field_name = self.matcher.find_field_name(text, text.find("[_123_]"))
        self.assertTrue("trường" in field_name.lower() or "học" in field_name.lower())
    
    def test_find_field_name_with_uppercase(self):
        """Kiểm tra trường hợp tên trường viết hoa"""
        text = "CHỨC VỤ HIỆN TẠI [_123_]"
        field_name = self.matcher.find_field_name(text, text.find("[_123_]"))
        self.assertEqual(field_name.lower(), "chức vụ hiện tại")
    
    