"""
Servidor de Arquivos TCP — protocolo JSON próprio (similar ao FTP anônimo).
Uso: python FileServer.py [porta]
     porta padrão: 5100
"""

import socket
import threading
import json
import os
import hashlib
import base64
import sys

STORAGE_DIR = os.path.join(os.path.dirname(__file__), "server_files")
os.makedirs(STORAGE_DIR, exist_ok=True)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- protocol --

def _recv_message(conn: socket.socket) -> dict | None:
    """Lê dados até encontrar '\\n' e decodifica como JSON."""
    buf = b""
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            return None
        buf += chunk
        if b"\n" in buf:
            line, _ = buf.split(b"\n", 1)
            return json.loads(line.decode("utf-8"))


def _send_message(conn: socket.socket, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False) + "\n"
    conn.sendall(raw.encode("utf-8"))


# ---------------------------------------------------------------- commands --

def _cmd_list() -> dict:
    files = [f for f in os.listdir(STORAGE_DIR)
             if os.path.isfile(os.path.join(STORAGE_DIR, f))]
    return {"cmd": "list_resp", "files": files}


def _cmd_put(req: dict) -> dict:
    filename  = req.get("file", "")
    hash_recv = req.get("hash", "")
    value_b64 = req.get("value", "")

    if not filename or not value_b64:
        return {"cmd": "put_resp", "file": filename, "status": "error: dados incompletos"}

    safe_name = os.path.basename(filename)
    if not safe_name:
        return {"cmd": "put_resp", "file": filename, "status": "error: nome de arquivo inválido"}

    try:
        data     = base64.b64decode(value_b64)
        computed = sha256(data)

        if computed != hash_recv:
            return {"cmd": "put_resp", "file": filename, "status": "error: hash SHA-256 inválido"}

        path = os.path.join(STORAGE_DIR, safe_name)
        with open(path, "wb") as fh:
            fh.write(data)

        return {"cmd": "put_resp", "file": filename, "status": "ok"}

    except Exception as exc:
        return {"cmd": "put_resp", "file": filename, "status": f"error: {exc}"}


def _cmd_get(req: dict) -> dict:
    filename  = req.get("file", "")
    safe_name = os.path.basename(filename)
    path      = os.path.join(STORAGE_DIR, safe_name)

    if not os.path.isfile(path):
        return {"cmd": "get_resp", "file": filename, "hash": "", "value": "",
                "status": "error: arquivo não encontrado"}

    try:
        with open(path, "rb") as fh:
            data = fh.read()
        return {
            "cmd":   "get_resp",
            "file":  filename,
            "hash":  sha256(data),
            "value": base64.b64encode(data).decode("utf-8"),
        }
    except Exception as exc:
        return {"cmd": "get_resp", "file": filename, "hash": "", "value": "",
                "status": f"error: {exc}"}


def _dispatch(req: dict) -> dict:
    cmd = req.get("cmd", "").lower()
    if cmd == "list_req":
        return _cmd_list()
    if cmd == "put_req":
        return _cmd_put(req)
    if cmd == "get_req":
        return _cmd_get(req)
    return {"cmd": "error", "message": f"Comando desconhecido: {cmd}"}


# ----------------------------------------------------------------- server --

def _handle_client(conn: socket.socket, addr: tuple) -> None:
    print(f"[+] Conexão de {addr[0]}:{addr[1]}")
    try:
        while True:
            req = _recv_message(conn)
            if req is None:
                break
            print(f"  [{addr[0]}] cmd={req.get('cmd')} file={req.get('file','')}")
            resp = _dispatch(req)
            _send_message(conn, resp)
    except Exception as exc:
        print(f"[!] Erro com {addr}: {exc}")
    finally:
        conn.close()
        print(f"[-] Conexão encerrada: {addr[0]}:{addr[1]}")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5100
    host = "0.0.0.0"

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(10)
    print(f"[*] Servidor de arquivos TCP iniciado em {host}:{port}")
    print(f"[*] Armazenamento: {os.path.abspath(STORAGE_DIR)}")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=_handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[*] Servidor encerrado.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
