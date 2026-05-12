"""
Cliente IoT — protocolo JSON sobre UDP.
Interface gráfica com tkinter.
Suporta múltiplas filiais com polling automático.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import socket
import json
import threading
import time


# ------------------------------------------------------------------ model --

class Branch:
    """Representa uma filial (servidor IoT)."""

    def __init__(self, name: str, host: str, port: int, user: str, password: str):
        self.name     = name
        self.host     = host
        self.port     = port
        self.user     = user
        self.password = password
        self.ids:       list  = []
        self.state:     dict  = {}
        self.connected: bool  = False
        # UI references (set by IoTClient when tab is built)
        self.tab_frame: tk.Frame | None    = None
        self.device_frame: ttk.Frame | None = None
        self.widgets: dict                 = {}   # id_ -> {val_var, btn_on, btn_off}


# ------------------------------------------------------------------ client --

class IoTClient:
    TIMEOUT_S = 3.0

    def __init__(self, root: tk.Tk):
        self.root     = root
        self.root.title("Cliente IoT UDP — Monitoramento Remoto")
        self.root.geometry("960x700")
        self.root.resizable(True, True)

        self.branches:       list   = []
        self.polling_active: bool   = False
        self.poll_interval:  int    = 5
        self._poll_thread: threading.Thread | None = None

        self._build_ui()

    # ----------------------------------------------------------------- UI --

    def _build_ui(self) -> None:
        # --- add branch panel ---
        add_frame = ttk.LabelFrame(self.root, text="Adicionar Filial", padding=8)
        add_frame.pack(fill=tk.X, padx=10, pady=6)

        fields = [
            ("Nome:",    "branch_name", "Filial 1",   10),
            ("IP:",      "host",        "127.0.0.1",  14),
            ("Porta:",   "port",        "51000",        7),
            ("Usuário:", "user",        "admin",        9),
            ("Senha:",   "password",    "filial1",      9),
        ]
        self._vars: dict = {}
        col = 0
        for label, key, default, width in fields:
            ttk.Label(add_frame, text=label).grid(row=0, column=col,     sticky=tk.W, padx=(8 if col else 0, 2))
            var = tk.StringVar(value=default)
            self._vars[key] = var
            show = "*" if key == "password" else ""
            ttk.Entry(add_frame, textvariable=var, width=width, show=show).grid(row=0, column=col + 1, padx=2)
            col += 2

        ttk.Button(add_frame, text="Adicionar e Conectar",
                   command=self._add_branch).grid(row=0, column=col, padx=10)

        # --- polling panel ---
        poll_frame = ttk.LabelFrame(self.root, text="Polling Automático", padding=6)
        poll_frame.pack(fill=tk.X, padx=10, pady=4)

        ttk.Label(poll_frame, text="Intervalo (s):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="5")
        ttk.Entry(poll_frame, textvariable=self.interval_var, width=6).pack(side=tk.LEFT, padx=4)

        self.poll_btn = ttk.Button(poll_frame, text="Iniciar Polling", command=self._toggle_polling)
        self.poll_btn.pack(side=tk.LEFT, padx=6)

        ttk.Button(poll_frame, text="Atualizar Agora", command=self._poll_all_now).pack(side=tk.LEFT, padx=4)

        self.poll_status_var = tk.StringVar(value="Polling inativo.")
        ttk.Label(poll_frame, textvariable=self.poll_status_var).pack(side=tk.LEFT, padx=12)

        # --- notebook (tabs per branch) ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        # --- log ---
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=4)
        log_frame.pack(fill=tk.X, padx=10, pady=6)
        self.log = scrolledtext.ScrolledText(log_frame, height=7, state=tk.DISABLED,
                                             font=("Consolas", 9))
        self.log.pack(fill=tk.BOTH, expand=True)

    # ----------------------------------------------------------------- log --

    def _log(self, msg: str) -> None:
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    # ------------------------------------------------------------ UDP I/O --

    def _udp(self, branch: Branch, payload: dict) -> dict:
        payload["user"]     = branch.user
        payload["password"] = branch.password
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.TIMEOUT_S)
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            sock.sendto(raw, (branch.host, branch.port))
            data, _ = sock.recvfrom(65535)
            sock.close()
            return json.loads(data.decode("utf-8"))
        except socket.timeout:
            return {"cmd": "error", "message": "Timeout — servidor não respondeu."}
        except Exception as exc:
            return {"cmd": "error", "message": str(exc)}

    # ----------------------------------------------------------- add branch --

    def _add_branch(self) -> None:
        name     = self._vars["branch_name"].get().strip()
        host     = self._vars["host"].get().strip()
        port_str = self._vars["port"].get().strip()
        user     = self._vars["user"].get().strip()
        password = self._vars["password"].get()

        if not name or not host or not port_str:
            messagebox.showerror("Erro", "Preencha Nome, IP e Porta.")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Erro", "Porta inválida.")
            return

        branch = Branch(name, host, port, user, password)

        resp = self._udp(branch, {"cmd": "list_req"})
        if resp.get("cmd") == "error":
            messagebox.showerror("Falha na conexão",
                                 f"{name} — {resp.get('message')}")
            return

        branch.ids       = resp.get("id", [])
        branch.state     = {id_: False for id_ in branch.ids}
        branch.connected = True
        self.branches.append(branch)

        self._create_tab(branch)
        self._log(f"[+] {name} ({host}:{port}) conectado. {len(branch.ids)} dispositivo(s).")
        self._refresh_branch(branch)

    # -------------------------------------------------------- tab per branch --

    def _create_tab(self, branch: Branch) -> None:
        outer = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(outer, text=branch.name)
        branch.tab_frame = outer

        ttk.Label(outer,
                  text=f"Filial: {branch.name}   |   {branch.host}:{branch.port}",
                  font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))

        # Scrollable canvas for devices
        canvas = tk.Canvas(outer)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        branch.device_frame = ttk.Frame(canvas)
        branch.device_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=branch.device_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_device_rows(branch)

    def _build_device_rows(self, branch: Branch) -> None:
        for child in branch.device_frame.winfo_children():
            child.destroy()
        branch.widgets = {}

        # Header row
        headers = ["ID do Dispositivo", "Tipo", "Dispositivo", "Local", "Estado", "Ações"]
        for col, h in enumerate(headers):
            ttk.Label(branch.device_frame, text=h, font=("Arial", 9, "bold"),
                      relief="groove", padding=3).grid(row=0, column=col, sticky=tk.EW, padx=2, pady=2)

        for row, id_ in enumerate(branch.ids, start=1):
            parts    = id_.split("_", 2)
            type_    = parts[0] if len(parts) > 0 else "?"
            device   = parts[1] if len(parts) > 1 else "?"
            location = parts[2] if len(parts) > 2 else "?"

            ttk.Label(branch.device_frame, text=id_,      width=32, anchor=tk.W).grid(row=row, column=0, padx=4, pady=2, sticky=tk.W)
            ttk.Label(branch.device_frame, text=type_,    width=10, anchor=tk.W).grid(row=row, column=1, padx=4)
            ttk.Label(branch.device_frame, text=device,   width=8,  anchor=tk.W).grid(row=row, column=2, padx=4)
            ttk.Label(branch.device_frame, text=location, width=14, anchor=tk.W).grid(row=row, column=3, padx=4)

            val_var = tk.StringVar(value="--")
            val_lbl = ttk.Label(branch.device_frame, textvariable=val_var, width=8,
                                anchor=tk.CENTER, relief="sunken", padding=2)
            val_lbl.grid(row=row, column=4, padx=4)

            branch.widgets[id_] = {"val_var": val_var, "val_lbl": val_lbl}

            if type_ == "actuator":
                btn_on  = ttk.Button(branch.device_frame, text="Ligar",    width=8,
                                     command=lambda b=branch, i=id_: self._set_device(b, i, True))
                btn_off = ttk.Button(branch.device_frame, text="Desligar", width=8,
                                     command=lambda b=branch, i=id_: self._set_device(b, i, False))
                btn_on.grid( row=row, column=5, padx=2)
                btn_off.grid(row=row, column=6, padx=2)
                branch.widgets[id_]["btn_on"]  = btn_on
                branch.widgets[id_]["btn_off"] = btn_off
            else:
                ttk.Label(branch.device_frame, text="(somente leitura)", foreground="gray").grid(
                    row=row, column=5, columnspan=2, padx=4)

    # -------------------------------------------------------- set / refresh --

    def _set_device(self, branch: Branch, id_: str, value: bool) -> None:
        def task():
            resp = self._udp(branch, {"cmd": "set_req", "id": id_, "value": value})
            if resp.get("cmd") == "set_resp":
                new_val = resp.get("value")
                self.root.after(0, self._update_widget, branch, id_, new_val)
                self.root.after(0, self._log,
                                f"[SET] {branch.name}/{id_} = {new_val}")
            else:
                self.root.after(0, self._log,
                                f"[!] SET falhou ({branch.name}/{id_}): {resp.get('message')}")
        threading.Thread(target=task, daemon=True).start()

    def _refresh_branch(self, branch: Branch) -> None:
        def task():
            resp = self._udp(branch, {"cmd": "get_status"})
            if resp.get("cmd") == "get_resp":
                for id_ in branch.ids:
                    val = resp.get(id_)
                    if val is not None and id_ in branch.widgets:
                        self.root.after(0, self._update_widget, branch, id_, val)
            else:
                self.root.after(0, self._log,
                                f"[!] GET falhou ({branch.name}): {resp.get('message')}")
        threading.Thread(target=task, daemon=True).start()

    def _update_widget(self, branch: Branch, id_: str, value: bool) -> None:
        w = branch.widgets.get(id_)
        if w is None:
            return
        label = "LIGADO" if value else "DESLIGADO"
        color = "#2ecc71" if value else "#e74c3c"
        w["val_var"].set(label)
        w["val_lbl"].config(foreground=color)

    # ----------------------------------------------------------- polling --

    def _poll_all_now(self) -> None:
        for b in self.branches:
            if b.connected:
                self._refresh_branch(b)

    def _toggle_polling(self) -> None:
        if self.polling_active:
            self.polling_active = False
            self.poll_btn.config(text="Iniciar Polling")
            self.poll_status_var.set("Polling inativo.")
        else:
            try:
                interval = int(self.interval_var.get())
                if interval < 1:
                    raise ValueError
                self.poll_interval = interval
            except ValueError:
                messagebox.showerror("Erro", "Intervalo inválido (mínimo: 1 segundo).")
                return

            self.polling_active = True
            self.poll_btn.config(text="Parar Polling")
            self.poll_status_var.set(f"Polling ativo — a cada {self.poll_interval}s")
            self._poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
            self._poll_thread.start()

    def _polling_loop(self) -> None:
        while self.polling_active:
            self._poll_all_now()
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    root = tk.Tk()
    app  = IoTClient(root)
    root.mainloop()
