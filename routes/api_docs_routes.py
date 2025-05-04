from flask import render_template, send_file, Response
import os

def register_api_docs_routes(app):
    """
    Đăng ký các route cho tài liệu API
    """
    @app.route('/api-docs')
    def api_docs():
        """
        Hiển thị tài liệu API
        """
        return render_template('api_docs.html')
        
    @app.route('/api-docs/download')
    def download_api_docs():
        """
        Tải xuống tài liệu API dạng Markdown
        """
        api_docs_path = os.path.join(app.root_path, '..', 'api_docs.md')
        return send_file(api_docs_path, as_attachment=True, download_name='api_docs.md', mimetype='text/markdown')