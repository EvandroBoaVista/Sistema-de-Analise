# run.py

from app import create_app

# Cria a instância da aplicação Flask
app = create_app()

if __name__ == '__main__':
    # Inicia o servidor de desenvolvimento
    # O host '0.0.0.0' permite que a aplicação seja acessada por outros dispositivos na mesma rede.
    app.run(host='0.0.0.0', port=5000, debug=True)