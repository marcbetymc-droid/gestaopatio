from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_caching import Cache
from dotenv import load_dotenv
import os

# Carrega variáveis de ambiente
load_dotenv()

# Inicializa a aplicação Flask
app = Flask(__name__)

# Configurações de segurança
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY',
    'e3f1c2a8b9d4e6f7a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4'
)

# Configurações do banco de dados
#app.config['SQLALCHEMY_DATABASE_URI'] = (
#    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
#    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
#)

# Configuração DB SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/gestaopatio.db'


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurações de CSRF
app.config['WTF_CSRF_ENABLED'] = True

# Configurações de cache com Redis
app.config['CACHE_TYPE'] = 'SimpleCache'
#app.config['CACHE_REDIS_HOST'] = os.getenv('CACHE_REDIS_HOST', 'localhost')
#app.config['CACHE_REDIS_PORT'] = int(os.getenv('CACHE_REDIS_PORT', 6379))
#app.config['CACHE_DEFAULT_TIMEOUT'] = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))
app.config['CACHE_DEFAULT_TIMEOUT'] = 300

# Inicializa extensões
database = SQLAlchemy(app)
migrate = Migrate(app, database)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
cache = Cache(app)

# Configurações do login
login_manager.login_view = 'login'
login_manager.login_message_category = 'alert-info'

# Função para carregar o usuário logado
@login_manager.user_loader
def load_usuario(id_usuario):
    from gestaopatio.models import Usuario
    return Usuario.query.get(int(id_usuario))

# Importa as rotas da aplicação
from gestaopatio import routes
