from flask import Flask
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect

from dotenv import load_dotenv

load_dotenv()
socketio = SocketIO()
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
csrf = CSRFProtect()
UPLOAD_FOLDER = 'uploads'
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["30 per second"]
)


def create_app():
    app = Flask(__name__)
    CORS(app)
    csrf.init_app(app)
    app.config[
        'SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        from src.routes import users_app
        app.register_blueprint(users_app, url_prefix='')
        db.create_all()
        return app
