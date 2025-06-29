# app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Inicializa a extensão do banco de dados
db = SQLAlchemy()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Habilita o modo WAL (Write-Ahead Logging) para o SQLite.
    Isso permite múltiplas leituras enquanto uma escrita está ocorrendo,
    resolvendo o erro "database is locked".
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

def create_app():
    """
    Cria e configura uma instância da aplicação Flask.
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Define uma chave secreta segura (idealmente carregada do ambiente)
    app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-e-diferente'
    
    # Garante que o diretório 'instance' exista
    if not os.path.exists(app.instance_path):
        os.makedirs(app.instance_path)
        
    # Configura o caminho do banco de dados SQLite
    db_path = os.path.join(app.instance_path, 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}?timeout=20"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicializa o banco de dados com a aplicação
    db.init_app(app)

    with app.app_context():
        # Importa os modelos aqui para evitar importação circular
        from . import models
        
        # Cria as tabelas do banco de dados se não existirem
        db.create_all()
        
        # Importa e registra as rotas da aplicação
        from . import routes
        
        return app