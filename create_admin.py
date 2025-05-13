from flask import Flask
from models.user import db, User, Role
import os
import sqlite3

# Đảm bảo thư mục instance tồn tại
instance_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_dir):
    try:
        os.makedirs(instance_dir, exist_ok=True)
        print(f'Đã tạo thư mục instance tại: {instance_dir}')
    except Exception as e:
        print(f'Lỗi khi tạo thư mục instance: {e}')
        exit(1)
else:
    print(f'Thư mục instance đã tồn tại tại: {instance_dir}')

# Kiểm tra quyền ghi vào thư mục instance
if not os.access(instance_dir, os.W_OK):
    print(f'Không có quyền ghi vào thư mục instance: {instance_dir}')
    print('Vui lòng cấp quyền ghi cho thư mục này và thử lại.')
    exit(1)

# Tạo file database trống nếu chưa tồn tại
db_path = os.path.join(instance_dir, 'database.db')
if not os.path.exists(db_path):
    try:
        # Tạo file database trống
        conn = sqlite3.connect(db_path)
        conn.close()
        print(f'Đã tạo file database tại: {db_path}')
    except Exception as e:
        print(f'Lỗi khi tạo file database: {e}')
        exit(1)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    try:
        # Kiểm tra xem bảng đã tồn tại chưa trước khi tạo
        inspector = db.inspect(db.engine)
        tables_needed = ['role', 'user']
        tables_to_create = False
        
        for table in tables_needed:
            if not inspector.has_table(table):
                tables_to_create = True
                print(f'Bảng {table} chưa tồn tại, cần tạo mới.')
        
        if tables_to_create:
            db.create_all()
            print('Đã tạo cơ sở dữ liệu thành công!')
            
            # Chỉ khởi tạo vai trò nếu bảng role vừa được tạo
            print('Tạo vai trò admin...')
            Role.insert_roles()
        else:
            print('Các bảng đã tồn tại, bỏ qua việc tạo bảng.')
        
        # Kiểm tra xem đã có vai trò admin chưa
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            print('Không tìm thấy vai trò admin, tạo mới...')
            Role.insert_roles()
            admin_role = Role.query.filter_by(name='admin').first()
    except Exception as e:
        print(f'Lỗi khi kiểm tra hoặc tạo bảng: {e}')
        exit(1)
    
    # Kiểm tra xem đã có tài khoản admin chưa
    admin = User.query.filter_by(role_id=admin_role.id).first()
    
    if admin:
        print(f'Đã tồn tại tài khoản admin: {admin.email}')
    else:
        # Tạo tài khoản admin mới
        admin = User(fullname='Administrator', email='dat@example.com', role_id=admin_role.id)
        admin.set_password('Admin@123')
        db.session.add(admin)
        db.session.commit()
        print('Đã tạo tài khoản admin thành công!')
        print('Email: dat@example.com')
        print('Mật khẩu: Admin@123')