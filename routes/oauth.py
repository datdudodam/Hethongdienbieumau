from flask import Blueprint, redirect, url_for, session, request, current_app, flash
from flask_login import login_user, current_user
from authlib.integrations.flask_client import OAuth
from models.user import db, User
from datetime import datetime, timezone
import os

oauth = OAuth()

def register_oauth_routes(app):
    """ Đăng ký các route OAuth """
    # Cấu hình OAuth
    oauth.init_app(app)
    
    # Đăng ký Google OAuth
    google = oauth.register(
        name='google',
        client_id="30787395526-jqgac7lj9usbv356ho35cahvcokq7868.apps.googleusercontent.com",
        client_secret="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",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    
    @app.route('/login/google')
    def login_google():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        session.permanent = True
        session['next_url'] = request.args.get('next') or url_for('index')

        redirect_uri = url_for('login_google_callback', _external=True)
        return google.authorize_redirect(redirect_uri)


    @app.route('/auth/google/callback')
    def login_google_callback():
        try:
            token = google.authorize_access_token()
        except Exception as e:
            app.logger.error(f"OAuth error: {str(e)}")
            flash('Đăng nhập không thành công. Vui lòng thử lại.', 'error')
            return redirect(url_for('login'))

        user_info = google.get('https://www.googleapis.com/oauth2/v2/userinfo').json()

        app.logger.info(f"Google user info: {user_info}")

        user = User.query.filter_by(email=user_info['email']).first()

        if not user:
            user = User(
                fullname=user_info.get('name', ''),
                email=user_info['email'],
                google_id=user_info['id'],
                
                last_login = datetime.now(timezone.utc)
            )
            db.session.add(user)
        else:
            user.google_id = user_info['id']
            
            user.last_login = datetime.utcnow()

        db.session.commit()
        login_user(user)

        flash('Đăng nhập bằng Google thành công!', 'success')
        next_url = session.pop('next_url', url_for('index'))
        return redirect(next_url)