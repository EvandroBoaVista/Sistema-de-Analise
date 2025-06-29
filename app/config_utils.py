# app/config_utils.py

import json
import os
from flask import current_app

def get_config_path():
    return os.path.join(current_app.instance_path, 'config.json')

def save_config(data):
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")
        return False

def load_config():
    config_path = get_config_path()
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'dbf_path': ''}
    except Exception as e:
        print(f"Erro ao carregar configuração: {e}")
        return {'dbf_path': ''}