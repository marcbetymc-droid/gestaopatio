
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_caching import Cache
from dotenv import load_dotenv
import os

load_dotenv()

# Inicialização das extensões (sem app)
database = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
login_manager = LoginManager()
cache = Cache()

def create_app():
    app = Flask(__name__)

    # Configurações
    app.config['SECRET_KEY'] = os.getenv(
        'SECRET_KEY',
        'e3f1c2a8b9d4e6f7a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4'
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL',
        'sqlite:///database/gestaopatio.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300

    # Inicializa extensões
    database.init_app(app)
    migrate.init_app(app, database)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    cache.init_app(app)

    # Config do login
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'alert-info'

    @login_manager.user_loader
    def load_usuario(id_usuario):
        from gestaopatio.models import Usuario
        return Usuario.query.get(int(id_usuario))

    # Importa rotas
    from gestaopatio import routes
    app.register_blueprint(routes.bp)

    return app
