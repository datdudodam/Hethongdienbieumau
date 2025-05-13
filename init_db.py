from flask import Flask
from models.user import db, Role
import os

def init_database():
    # Khởi tạo ứng dụng Flask
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://postgres:postgres@db:5432/updatelan5')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        try:
            # Kiểm tra xem bảng đã tồn tại chưa
            inspector = db.inspect(db.engine)
            tables_needed = ['role', 'user', 'web_config']
            tables_to_create = False
            
            for table in tables_needed:
                if not inspector.has_table(table):
                    tables_to_create = True
                    print(f'Bảng {table} chưa tồn tại, cần tạo mới.')
            
            if tables_to_create:
                # Import các model để đảm bảo chúng được đăng ký với SQLAlchemy
                from models.web_config import WebConfig
                
                # Tạo tất cả các bảng
                db.create_all()
                print('Đã tạo cơ sở dữ liệu thành công!')
                
                # Khởi tạo vai trò
                Role.insert_roles()
            else:
                print('Các bảng đã tồn tại, bỏ qua việc tạo bảng.')
                
        except Exception as e:
            print(f'Lỗi khi khởi tạo cơ sở dữ liệu: {e}')

if __name__ == '__main__':
    init_database()