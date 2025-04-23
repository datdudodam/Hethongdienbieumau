from flask import render_template, request, jsonify
from utils.document_utils import upload_document
from flask import redirect, url_for
from flask_login import current_user
def register_home_routes(app):
    """
    Đăng ký các route cho trang chủ và tải lên tài liệu
    """
    @app.route('/',methods=['GET', 'POST'])
    def home():
        return render_template('home.html')
    @app.route('/dashboard')
    def index():
        if not current_user.is_authenticated:
            return redirect('/login')
        return render_template("TrangChu.html")
    
    @app.route('/upload', methods=['POST'])
    def upload_file():
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        result, status_code = upload_document(file)
        return jsonify(result), status_code
    
    @app.route('/get-recent-forms')
    def get_recent_forms():
        from models.data_model import load_form_history
        import datetime
        import os
        from flask_login import current_user
        
        try:
            form_history = load_form_history()
            # Đảm bảo form_history là một list
            if form_history is None or not isinstance(form_history, list):
                form_history = []
            query = request.args.get('query', '')
            
            # Format the forms for display
            formatted_forms = []
            for form in form_history:
                # Chỉ hiển thị biểu mẫu của người dùng hiện tại
                # Nếu form không có user_id hoặc user_id khác với current_user.id thì bỏ qua
                if current_user.is_authenticated:
                    # Kiểm tra nếu form có user_id và khác với current_user.id thì bỏ qua
                    if 'user_id' in form and form['user_id'] is not None and form['user_id'] != current_user.id:
                        continue
                    # Nếu không có user_id, vẫn hiển thị (có thể là biểu mẫu cũ)
                
                # Format the date for display
                timestamp = datetime.datetime.fromisoformat(form['timestamp'])
                formatted_date = timestamp.strftime('%d/%m/%Y %H:%M')
                
                # Create a formatted form object
                formatted_form = {
                    'id': os.path.basename(form['path']).split('.')[0],
                    'name': form.get('name', os.path.basename(form['path'])),
                    'date': formatted_date,
                    'path': form['path']
                }
                
                # Add form data if available
                if 'form_data' in form:
                    formatted_form['form_data'] = form['form_data']
                
                # Add user info if available
                if 'user_name' in form and form['user_name']:
                    formatted_form['user_name'] = form['user_name']
                
                # Filter by search query if provided
                form_name = form.get('name', os.path.basename(form['path']))
                if not query or query.lower() in form_name.lower():
                    formatted_forms.append(formatted_form)
            
            # Sort by date (newest first)
            formatted_forms.sort(key=lambda x: x['date'], reverse=True)
            
            return jsonify({'forms': formatted_forms})
        except Exception as e:
            print(f"Error loading recent forms: {str(e)}")
            return jsonify({'error': 'Failed to load recent forms'}), 500