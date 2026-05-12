"""
Servidor IoT — protocolo JSON sobre UDP.
Carrega configuração de um arquivo JSON.
Uso: python IoTServer.py <config.json>
     Ex: python IoTServer.py config_filial1.json
"""

import socket
import json
import sys
import os


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _send(sock: socket.socket, payload: dict, addr: tuple) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sock.sendto(raw, addr)


def _dispatch(req: dict, state: dict, ids: list,
              admin_user: str, admin_pass: str) -> dict:
    # Authentication
    if req.get("user") != admin_user or req.get("password") != admin_pass:
        return {"cmd": "error", "message": "Autenticação falhou."}

    cmd = req.get("cmd", "").lower()

    if cmd == "list_req":
        return {"cmd": "list_resp", "id": ids}

    if cmd == "get_status":
        resp = {"cmd": "get_resp"}
        for id_ in ids:
            resp[id_] = state[id_]
        return resp

    if cmd == "set_req":
        id_   = req.get("id", "")
        value = req.get("value")

        if id_ not in ids:
            return {"cmd": "set_resp", "id": id_, "value": None,
                    "status": "error: ID não encontrado"}

        if id_.startswith("sensor_"):
            return {"cmd": "set_resp", "id": id_, "value": state[id_],
                    "status": "error: sensor é somente leitura"}

        state[id_] = bool(value)
        return {"cmd": "set_resp", "id": id_, "value": state[id_]}

    return {"cmd": "error", "message": f"Comando desconhecido: {cmd}"}


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python IoTServer.py <config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    if not os.path.isfile(config_path):
        print(f"[!] Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)

    config     = load_config(config_path)
    port       = config["port"]
    admin_user = config["admin_user"]
    admin_pass = config["admin_pass"]
    ids        = config["id"]

    # Initialize all devices as False (off)
    state: dict = {id_: False for id_ in ids}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))

    print(f"[*] Servidor IoT rodando na porta {port}")
    print(f"[*] Usuário: {admin_user}  |  Dispositivos ({len(ids)}): {ids}")

    try:
        while True:
            data, addr = sock.recvfrom(65535)
            try:
                req  = json.loads(data.decode("utf-8"))
                resp = _dispatch(req, state, ids, admin_user, admin_pass)
                print(f"  [{addr[0]}:{addr[1]}] cmd={req.get('cmd')} -> {resp}")
                _send(sock, resp, addr)
            except json.JSONDecodeError:
                _send(sock, {"cmd": "error", "message": "JSON inválido"}, addr)
            except Exception as exc:
                print(f"[!] Erro: {exc}")

    except KeyboardInterrupt:
        print("\n[*] Servidor encerrado.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
