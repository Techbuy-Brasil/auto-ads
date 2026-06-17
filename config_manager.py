import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENTS_FILE = os.path.join(BASE_DIR, "clientes.json")


def _load():
    if not os.path.exists(CLIENTS_FILE):
        return {}
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def listar():
    data = _load()
    if not data:
        print("Nenhum cliente cadastrado.")
        return data
    return data


def adicionar(client_id, nome, ad_account_id, access_token, page_id=None):
    data = _load()
    if client_id in data:
        print(f"Cliente '{client_id}' já existe.")
        return False
    data[client_id] = {
        "nome": nome,
        "ad_account_id": ad_account_id,
        "access_token": access_token,
        "page_id": page_id or "",
        "criado_em": datetime.now().isoformat(),
        "atualizado_em": datetime.now().isoformat(),
    }
    _save(data)
    print(f"Cliente '{client_id}' cadastrado.")
    return True


def atualizar(client_id, **kwargs):
    data = _load()
    if client_id not in data:
        print(f"Cliente '{client_id}' não encontrado.")
        return False
    allowed = {"nome", "ad_account_id", "access_token", "page_id"}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            data[client_id][k] = v
    data[client_id]["atualizado_em"] = datetime.now().isoformat()
    _save(data)
    print(f"Cliente '{client_id}' atualizado.")
    return True


def remover(client_id):
    data = _load()
    if client_id not in data:
        print(f"Cliente '{client_id}' não encontrado.")
        return False
    del data[client_id]
    _save(data)
    print(f"Cliente '{client_id}' removido.")
    return True


def obter(client_id):
    data = _load()
    return data.get(client_id)


def todos():
    return _load()
