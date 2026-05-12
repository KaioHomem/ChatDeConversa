import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import struct
import threading
import json
from datetime import datetime


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Multicast UDP")
        self.root.geometry("720x580")
        self.root.resizable(True, True)

        self.sock = None
        self.recv_thread = None
        self.running = False
        self.current_group = None
        self.current_port = None

        self._build_ui()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        config_frame = ttk.LabelFrame(self.root, text="Configuração de Conexão", padding=8)
        config_frame.pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(config_frame, text="Usuário:").grid(row=0, column=0, sticky=tk.W)
        self.username_var = tk.StringVar(value="Usuário")
        ttk.Entry(config_frame, textvariable=self.username_var, width=18).grid(row=0, column=1, padx=4)

        ttk.Label(config_frame, text="Grupo Multicast:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.group_var = tk.StringVar(value="239.255.0.1")
        ttk.Entry(config_frame, textvariable=self.group_var, width=16).grid(row=0, column=3, padx=4)

        ttk.Label(config_frame, text="Porta:").grid(row=0, column=4, sticky=tk.W, padx=(10, 0))
        self.port_var = tk.StringVar(value="5000")
        ttk.Entry(config_frame, textvariable=self.port_var, width=7).grid(row=0, column=5, padx=4)

        btn_row = ttk.Frame(config_frame)
        btn_row.grid(row=1, column=0, columnspan=6, pady=(6, 0))

        self.join_btn = ttk.Button(btn_row, text="Entrar no Grupo", command=self._join_group)
        self.join_btn.pack(side=tk.LEFT, padx=4)

        self.leave_btn = ttk.Button(btn_row, text="Sair do Grupo", command=self._leave_group, state=tk.DISABLED)
        self.leave_btn.pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="Desconectado")
        self.status_lbl = ttk.Label(btn_row, textvariable=self.status_var, foreground="red")
        self.status_lbl.pack(side=tk.LEFT, padx=12)

        chat_frame = ttk.LabelFrame(self.root, text="Mensagens", padding=6)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        self.chat_area = scrolledtext.ScrolledText(chat_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 10))
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        self.chat_area.tag_config("own",    foreground="#0055cc", font=("Consolas", 10, "bold"))
        self.chat_area.tag_config("other",  foreground="#1a1a1a")
        self.chat_area.tag_config("system", foreground="#888888", font=("Consolas", 9, "italic"))

        send_frame = ttk.Frame(self.root, padding=(10, 4))
        send_frame.pack(fill=tk.X)

        self.msg_entry = ttk.Entry(send_frame, font=("Consolas", 10))
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.msg_entry.bind("<Return>", lambda _: self._send_message())

        self.send_btn = ttk.Button(send_frame, text="Enviar", command=self._send_message, state=tk.DISABLED)
        self.send_btn.pack(side=tk.RIGHT)

    # ---------------------------------------------------------- Group join/leave --

    def _join_group(self):
        username = self.username_var.get().strip()
        group    = self.group_var.get().strip()
        port_str = self.port_var.get().strip()

        if not username:
            messagebox.showerror("Erro", "Informe o nome de usuário.")
            return

        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Porta inválida (1–65535).")
            return

        try:
            parts = list(map(int, group.split(".")))
            if len(parts) != 4 or not (224 <= parts[0] <= 239):
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Endereço multicast inválido.\nFaixa permitida: 224.0.0.0 – 239.255.255.255")
            return

        if self.running:
            self._leave_group()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", port))

            mreq = struct.pack("4sL", socket.inet_aton(group), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            sock.settimeout(1.0)

            self.sock          = sock
            self.current_group = group
            self.current_port  = port
            self.running       = True

            self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self.recv_thread.start()

            self.join_btn.config(state=tk.DISABLED)
            self.leave_btn.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.status_var.set(f"Conectado: {group}:{port}")
            self.status_lbl.config(foreground="green")
            self._append("[Sistema] Entrou no grupo %s:%s" % (group, port), "system")

        except OSError as exc:
            messagebox.showerror("Erro de rede", str(exc))
            try:
                sock.close()
            except Exception:
                pass

    def _leave_group(self):
        if not self.running:
            return

        self.running = False

        if self.sock:
            try:
                mreq = struct.pack("4sL", socket.inet_aton(self.current_group), socket.INADDR_ANY)
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        self.join_btn.config(state=tk.NORMAL)
        self.leave_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self.status_var.set("Desconectado")
        self.status_lbl.config(foreground="red")
        self._append("[Sistema] Saiu do grupo %s:%s" % (self.current_group, self.current_port), "system")

    # -------------------------------------------------- Send / receive --

    def _send_message(self):
        if not self.running:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return

        now = datetime.now()
        payload = {
            "date":     now.strftime("%d/%m/%Y"),
            "time":     now.strftime("%H:%M:%S"),
            "username": self.username_var.get(),
            "message":  text,
        }
        try:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.sock.sendto(raw, (self.current_group, self.current_port))
            self.msg_entry.delete(0, tk.END)
        except OSError as exc:
            messagebox.showerror("Erro ao enviar", str(exc))

    def _recv_loop(self):
        """Runs in a dedicated daemon thread – receives and displays messages."""
        while self.running:
            try:
                raw, _addr = self.sock.recvfrom(65535)
                payload = json.loads(raw.decode("utf-8"))

                username = payload.get("username", "?")
                message  = payload.get("message",  "")
                date     = payload.get("date",     "")
                time_    = payload.get("time",     "")

                line = "[%s %s] %s: %s" % (date, time_, username, message)
                tag  = "own" if username == self.username_var.get() else "other"

                self.root.after(0, self._append, line, tag)

            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    self.root.after(0, self._append, "[Sistema] Erro na recepção.", "system")
                break

    def _append(self, text, tag="other"):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, text + "\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.config(state=tk.DISABLED)

    def on_close(self):
        if self.running:
            self._leave_group()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app  = ChatApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
