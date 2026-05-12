"""
Cliente de Arquivos TCP — protocolo JSON próprio (similar ao FTP anônimo).
Interface gráfica com tkinter.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import socket
import json
import hashlib
import base64
import os
import threading


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FTPClient:
    def __init__(self, root: tk.Tk):
        self.root   = root
        self.root.title("Cliente FTP TCP — JSON")
        self.root.geometry("780x620")
        self.root.resizable(True, True)

        self.sock:      socket.socket | None = None
        self.connected: bool                  = False

        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self) -> None:
        # --- connection bar ---
        conn = ttk.LabelFrame(self.root, text="Conexão", padding=8)
        conn.pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(conn, text="Servidor:").grid(row=0, column=0, sticky=tk.W)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(conn, textvariable=self.host_var, width=18).grid(row=0, column=1, padx=4)

        ttk.Label(conn, text="Porta:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.port_var = tk.StringVar(value="5100")
        ttk.Entry(conn, textvariable=self.port_var, width=7).grid(row=0, column=3, padx=4)

        self.conn_btn = ttk.Button(conn, text="Conectar", command=self._toggle_connect)
        self.conn_btn.grid(row=0, column=4, padx=10)

        self.status_var = tk.StringVar(value="Desconectado")
        self.status_lbl = ttk.Label(conn, textvariable=self.status_var, foreground="red")
        self.status_lbl.grid(row=0, column=5)

        # --- file list ---
        list_frame = ttk.LabelFrame(self.root, text="Arquivos no Servidor", padding=6)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self.file_lb = tk.Listbox(list_frame, selectmode=tk.SINGLE, font=("Consolas", 10))
        self.file_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_lb.config(yscrollcommand=sb.set)

        # --- action buttons ---
        acts = ttk.Frame(self.root, padding=(10, 2))
        acts.pack(fill=tk.X)
        ttk.Button(acts, text="Listar arquivos (LIST)",    command=self._list_files).pack(side=tk.LEFT, padx=4)
        ttk.Button(acts, text="Download selecionado (GET)", command=self._get_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(acts, text="Upload de arquivo (PUT)",   command=self._put_file).pack(side=tk.LEFT, padx=4)

        # --- log ---
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=6)
        self.log = scrolledtext.ScrolledText(log_frame, height=9, state=tk.DISABLED,
                                             font=("Consolas", 9))
        self.log.pack(fill=tk.BOTH, expand=True)

    # ----------------------------------------------------------------- log --

    def _log(self, msg: str) -> None:
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    # ----------------------------------------------------------- connection --

    def _toggle_connect(self) -> None:
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Erro", "Porta inválida.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True
            self.conn_btn.config(text="Desconectar")
            self.status_var.set(f"Conectado: {host}:{port}")
            self.status_lbl.config(foreground="green")
            self._log(f"[+] Conectado a {host}:{port}")
        except Exception as exc:
            messagebox.showerror("Erro de conexão", str(exc))
            if self.sock:
                self.sock.close()
                self.sock = None

    def _disconnect(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.connected = False
        self.conn_btn.config(text="Conectar")
        self.status_var.set("Desconectado")
        self.status_lbl.config(foreground="red")
        self._log("[-] Desconectado.")

    # ---------------------------------------------------- send / receive --

    def _send_recv(self, payload: dict) -> dict | None:
        if not self.connected or self.sock is None:
            messagebox.showerror("Erro", "Não conectado ao servidor.")
            return None
        try:
            raw = json.dumps(payload, ensure_ascii=False) + "\n"
            self.sock.sendall(raw.encode("utf-8"))

            buf = b""
            while b"\n" not in buf:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise ConnectionError("Conexão encerrada pelo servidor.")
                buf += chunk

            line, _ = buf.split(b"\n", 1)
            return json.loads(line.decode("utf-8"))

        except Exception as exc:
            self._log(f"[!] Erro de comunicação: {exc}")
            self._disconnect()
            return None

    # ----------------------------------------------------------- commands --

    def _list_files(self) -> None:
        def task():
            resp = self._send_recv({"cmd": "list_req"})
            if resp is None:
                return
            files = resp.get("files", [])
            self.root.after(0, self._update_list, files)
            self.root.after(0, self._log, f"[LIST] {len(files)} arquivo(s) no servidor.")

        threading.Thread(target=task, daemon=True).start()

    def _update_list(self, files: list) -> None:
        self.file_lb.delete(0, tk.END)
        for f in sorted(files):
            self.file_lb.insert(tk.END, f)

    def _get_file(self) -> None:
        sel = self.file_lb.curselection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um arquivo na lista.")
            return
        filename  = self.file_lb.get(sel[0])
        save_path = filedialog.asksaveasfilename(initialfile=filename, title="Salvar como")
        if not save_path:
            return

        def task():
            resp = self._send_recv({"cmd": "get_req", "file": filename})
            if resp is None:
                return

            if resp.get("status", "").startswith("error"):
                self.root.after(0, messagebox.showerror, "Erro", resp["status"])
                return

            value_b64   = resp.get("value", "")
            hash_server = resp.get("hash", "")

            try:
                data         = base64.b64decode(value_b64)
                hash_local   = sha256(data)

                if hash_local != hash_server:
                    msg = (f"Inconsistência de hash!\n"
                           f"Servidor : {hash_server}\n"
                           f"Calculado: {hash_local}")
                    self.root.after(0, messagebox.showerror, "Erro de Hash", msg)
                    self.root.after(0, self._log, f"[GET] ERRO de hash em '{filename}'")
                    return

                with open(save_path, "wb") as fh:
                    fh.write(data)

                self.root.after(0, self._log, f"[GET] '{filename}' salvo em '{save_path}' — hash OK.")
                self.root.after(0, messagebox.showinfo, "Sucesso", f"'{filename}' baixado com sucesso!")

            except Exception as exc:
                self.root.after(0, messagebox.showerror, "Erro", str(exc))

        threading.Thread(target=task, daemon=True).start()

    def _put_file(self) -> None:
        filepath = filedialog.askopenfilename(title="Selecionar arquivo para upload")
        if not filepath:
            return
        filename = os.path.basename(filepath)

        def task():
            try:
                with open(filepath, "rb") as fh:
                    data = fh.read()

                h       = sha256(data)
                encoded = base64.b64encode(data).decode("utf-8")

                self.root.after(0, self._log, f"[PUT] Enviando '{filename}' ({len(data)} bytes)…")

                resp = self._send_recv({
                    "cmd":   "put_req",
                    "file":  filename,
                    "hash":  h,
                    "value": encoded,
                })
                if resp is None:
                    return

                status = resp.get("status", "?")
                if status == "ok":
                    self.root.after(0, self._log, f"[PUT] '{filename}' enviado com sucesso.")
                    self.root.after(0, messagebox.showinfo, "Sucesso", f"'{filename}' enviado!")
                    self.root.after(0, self._list_files)
                else:
                    self.root.after(0, messagebox.showerror, "Erro no upload", status)
                    self.root.after(0, self._log, f"[PUT] Falha: {status}")

            except Exception as exc:
                self.root.after(0, messagebox.showerror, "Erro", str(exc))

        threading.Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app  = FTPClient(root)
    root.mainloop()
