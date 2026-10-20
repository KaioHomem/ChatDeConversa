"""ChatDeConversa: chat em grupo por UDP multicast, com interface no estilo WhatsApp.

A interface tem duas telas: a de entrada (nome, grupo e porta) e a conversa, com
balões de mensagem, horário e confirmação de entrega. A rede continua a mesma:
cada mensagem é um JSON enviado ao grupo multicast, e todo mundo no grupo recebe.
"""

import hashlib
import json
import queue
import socket
import struct
import threading
import tkinter as tk
import tkinter.font as tkfont
import uuid
from datetime import datetime
from tkinter import messagebox

# Paleta do WhatsApp (tema escuro).
BG = "#0b141a"
PANEL = "#202c33"
FIELD = "#2a3942"
OUT = "#005c4b"
IN = "#202c33"
TEXT = "#e9edef"
META = "#8696a0"
GREEN = "#00a884"
GREEN_DARK = "#008f6f"
BLUE_TICK = "#53bdeb"
CHIP = "#182229"

# Cores dos nomes nos grupos, escolhidas pelo hash do nome.
NAME_COLORS = ["#53bdeb", "#ff7eb6", "#ffd279", "#06cf9c", "#a5b337", "#fc9775", "#c4a0ff", "#5fb4ff"]

DEFAULT_GROUP = "239.255.0.1"
DEFAULT_PORT = 5000


def name_color(name):
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return NAME_COLORS[h % len(NAME_COLORS)]


def pick_family(root, *names):
    available = set(tkfont.families(root))
    for n in names:
        if n in available:
            return n
    return "TkDefaultFont"


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ChatDeConversa")
        # Fator de escala da tela (1.0 em 96 dpi): mantém as medidas em pixel proporcionais às fontes.
        self.s = max(1.0, root.winfo_fpixels("1i") / 96)
        self.root.geometry(f"{self.px(460)}x{self.px(720)}")
        self.root.minsize(self.px(380), self.px(560))
        self.root.configure(bg=BG)

        family = pick_family(root, "Segoe UI", "Helvetica Neue", "Helvetica", "Arial")
        self.f_text = tkfont.Font(family=family, size=11)
        self.f_small = tkfont.Font(family=family, size=8)
        self.f_name = tkfont.Font(family=family, size=10, weight="bold")
        self.f_title = tkfont.Font(family=family, size=12, weight="bold")
        self.f_big = tkfont.Font(family=family, size=20, weight="bold")

        self.client_id = uuid.uuid4().hex
        self.sock = None
        self.running = False
        self.current_group = None
        self.current_port = None
        self.inbox = queue.Queue()
        self.pending = {}  # id da mensagem -> (canvas, item do check) até o eco chegar
        self.last_date = None

        self.username_var = tk.StringVar()
        self.group_var = tk.StringVar(value=DEFAULT_GROUP)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))

        self.login = self._build_login()
        self.chat = self._build_chat()
        self.login.pack(fill=tk.BOTH, expand=True)
        self.root.after(50, self._drain_inbox)

    def px(self, n):
        return int(round(n * self.s))

    # ------------------------------------------------------------ Telas --

    def _build_login(self):
        frame = tk.Frame(self.root, bg=BG)
        card = tk.Frame(frame, bg=BG)
        card.place(relx=0.5, rely=0.46, anchor="center")

        logo = tk.Canvas(card, width=self.px(96), height=self.px(96), bg=BG, highlightthickness=0)
        logo.create_oval(4, 4, 92, 92, fill=GREEN, outline="")
        logo.create_polygon(30, 66, 24, 78, 40, 70, fill=TEXT, outline="")
        logo.create_oval(24, 26, 72, 70, fill=TEXT, outline="")
        for x in (38, 48, 58):
            logo.create_oval(x - 3, 45, x + 3, 51, fill=GREEN, outline="")
        logo.scale("all", 0, 0, self.s, self.s)
        logo.pack(pady=(0, 18))

        tk.Label(card, text="ChatDeConversa", font=self.f_big, fg=TEXT, bg=BG).pack()
        tk.Label(card, text="Chat em grupo na rede local, sem servidor.\nAs mensagens vão direto por UDP multicast.",
                 font=self.f_text, fg=META, bg=BG, justify="center").pack(pady=(6, 26))

        def field(label, var):
            tk.Label(card, text=label, font=self.f_small, fg=GREEN, bg=BG, anchor="w").pack(fill=tk.X, padx=4)
            e = tk.Entry(card, textvariable=var, font=self.f_text, bg=FIELD, fg=TEXT, insertbackground=TEXT,
                         relief=tk.FLAT, highlightthickness=2, highlightbackground=FIELD, highlightcolor=GREEN, width=30)
            e.pack(fill=tk.X, ipady=8, pady=(4, 14))
            return e

        self.name_entry = field("SEU NOME", self.username_var)
        field("GRUPO MULTICAST", self.group_var)
        field("PORTA", self.port_var)
        self.name_entry.bind("<Return>", lambda e: self._join_group())

        btn = tk.Button(card, text="Entrar no grupo", command=self._join_group, font=self.f_name,
                        bg=GREEN, fg=BG, activebackground=GREEN_DARK, activeforeground=BG,
                        relief=tk.FLAT, cursor="hand2", bd=0)
        btn.pack(fill=tk.X, ipady=10, pady=(6, 0))

        tk.Label(frame, text="Projeto de Ciência da Computação · IFSC", font=self.f_small, fg=META, bg=BG).pack(
            side=tk.BOTTOM, pady=16)
        self.root.after(100, self.name_entry.focus_set)
        return frame

    def _build_chat(self):
        frame = tk.Frame(self.root, bg=BG)

        # Cabeçalho: avatar do grupo, nome, status e botão de sair.
        head = tk.Frame(frame, bg=PANEL, height=self.px(60))
        head.pack(fill=tk.X)
        head.pack_propagate(False)
        self.avatar = tk.Canvas(head, width=self.px(40), height=self.px(40), bg=PANEL, highlightthickness=0)
        self.avatar.pack(side=tk.LEFT, padx=(14, 10))
        info = tk.Frame(head, bg=PANEL)
        info.pack(side=tk.LEFT, fill=tk.Y, pady=9)
        self.title_lbl = tk.Label(info, text="", font=self.f_title, fg=TEXT, bg=PANEL, anchor="w")
        self.title_lbl.pack(fill=tk.X)
        self.sub_lbl = tk.Label(info, text="", font=self.f_small, fg=META, bg=PANEL, anchor="w")
        self.sub_lbl.pack(fill=tk.X)
        leave = tk.Button(head, text="Sair", command=self._leave_group, font=self.f_small, bg=PANEL, fg=META,
                          activebackground=FIELD, activeforeground=TEXT, relief=tk.FLAT, bd=0, cursor="hand2")
        leave.pack(side=tk.RIGHT, padx=14, ipadx=8, ipady=4)

        # Barra de digitação.
        bar = tk.Frame(frame, bg=PANEL)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.msg_entry = tk.Entry(bar, font=self.f_text, bg=FIELD, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT,
                                  highlightthickness=0)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 8), pady=10, ipady=9)
        self.msg_entry.bind("<Return>", lambda e: self._send_message())
        self.placeholder = "Mensagem"
        self._show_placeholder()
        self.msg_entry.bind("<FocusIn>", lambda e: self._hide_placeholder())
        self.msg_entry.bind("<FocusOut>", lambda e: self._show_placeholder())

        send = tk.Canvas(bar, width=self.px(44), height=self.px(44), bg=PANEL, highlightthickness=0, cursor="hand2")
        send.create_oval(2, 2, 42, 42, fill=GREEN, outline="")
        send.create_polygon(15, 13, 32, 22, 15, 31, 18, 22, fill=BG, outline="")
        send.scale("all", 0, 0, self.s, self.s)
        send.pack(side=tk.RIGHT, padx=(0, 12))
        send.bind("<Button-1>", lambda e: self._send_message())

        # Área das mensagens: um Canvas com um Frame rolável dentro.
        wrap = tk.Frame(frame, bg=BG)
        wrap.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.list = tk.Frame(self.canvas, bg=BG)
        self.list_id = self.canvas.create_window(0, 0, window=self.list, anchor="nw")
        self.list.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.list_id, width=e.width))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        return frame

    def _show_placeholder(self):
        if not self.msg_entry.get():
            self.msg_entry.insert(0, self.placeholder)
            self.msg_entry.config(fg=META)

    def _hide_placeholder(self):
        if self.msg_entry.cget("fg") == META:
            self.msg_entry.delete(0, tk.END)
            self.msg_entry.config(fg=TEXT)

    def _draw_avatar(self, label):
        c = self.avatar
        c.delete("all")
        c.create_oval(0, 0, self.px(40), self.px(40), fill="#6a7175", outline="")
        c.create_text(self.px(20), self.px(20), text=label, fill=TEXT, font=self.f_name)

    # ------------------------------------------------------- Mensagens --

    def _scroll_to_end(self):
        self.root.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _date_chip(self, date):
        if date == self.last_date:
            return
        self.last_date = date
        label = "HOJE" if date == datetime.now().strftime("%d/%m/%Y") else date
        self._chip(label)

    def _chip(self, text):
        row = tk.Frame(self.list, bg=BG)
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=text, font=self.f_small, fg=META, bg=CHIP, padx=10, pady=4).pack()
        self._scroll_to_end()

    def _bubble(self, text, time_, own, name=None):
        """Desenha um balão com cantos arredondados e a pontinha do lado de quem enviou."""
        row = tk.Frame(self.list, bg=BG)
        row.pack(fill=tk.X, padx=10, pady=2)

        width = max(self.canvas.winfo_width(), self.px(380))
        max_w = int(width * 0.72)
        pad_x, pad_y, tail = self.px(10), self.px(7), self.px(8)
        fill = OUT if own else IN

        c = tk.Canvas(row, bg=BG, highlightthickness=0, width=10, height=10)
        y = pad_y
        if name:
            c.create_text(tail + pad_x, y, text=name, fill=name_color(name), font=self.f_name, anchor="nw")
            y += self.f_name.metrics("linespace") + 1
        body = c.create_text(tail + pad_x, y, text=text, fill=TEXT, font=self.f_text, anchor="nw",
                             width=max_w - 2 * pad_x - tail)
        x1, _, x2, y2 = c.bbox(body)
        tick_w = self.f_small.measure("✓✓") + self.px(4)
        meta_w = self.f_small.measure(time_) + (tick_w + self.px(4) if own else self.px(6))
        content_w = max(x2 - (tail + pad_x), meta_w + 10)
        if name:
            content_w = max(content_w, self.f_name.measure(name))
        # O horário fica embaixo à direita; se a última linha for curta, cabe ao lado dela.
        line_h = self.f_text.metrics("linespace")
        last_line_w = self._last_line_width(text, max_w - 2 * pad_x - tail)
        if last_line_w + meta_w + 12 <= content_w or (y2 - y <= line_h and last_line_w + meta_w + 12 <= max_w - 2 * pad_x - tail):
            content_w = max(content_w, last_line_w + meta_w + 12)
            meta_y = y2 - self.f_small.metrics("linespace") - 1
            h = y2 + pad_y
        else:
            meta_y = y2 + 1
            h = meta_y + self.f_small.metrics("linespace") + pad_y
        w = content_w + 2 * pad_x + tail

        # Para quem envia, o balão fica à direita: espelha a posição.
        bx1, bx2 = (0, w - tail) if own else (tail, w)
        c.configure(width=w, height=h)
        self._round_rect(c, bx1, 0, bx2, h, self.px(9), fill)
        if own:
            c.create_polygon(bx2 - self.px(6), 0, w, 0, bx2, self.px(10), fill=fill, outline="")
            c.move(body, -tail, 0)
        else:
            c.create_polygon(bx1 + self.px(6), 0, 0, 0, bx1, self.px(10), fill=fill, outline="")
        c.tag_raise(body)
        if name:
            for item in c.find_all():
                if c.type(item) == "text" and item != body:
                    c.tag_raise(item)

        right = bx2 - pad_x
        tick = None
        if own:
            tick = c.create_text(right, meta_y, text="✓", fill=META, font=self.f_small, anchor="ne")
            right -= tick_w
        c.create_text(right, meta_y, text=time_, fill="#a6c4bd" if own else META, font=self.f_small, anchor="ne")

        c.pack(side=tk.RIGHT if own else tk.LEFT)
        self._scroll_to_end()
        return c, tick

    def _last_line_width(self, text, wrap_w):
        last = text.split("\n")[-1]
        line, width = "", 0
        for word in last.split(" "):
            trial = (line + " " + word).strip()
            if self.f_text.measure(trial) > wrap_w and line:
                line = word
            else:
                line = trial
        width = self.f_text.measure(line)
        return width

    @staticmethod
    def _round_rect(c, x1, y1, x2, y2, r, fill):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        c.create_polygon(pts, smooth=True, fill=fill, outline="")

    # ------------------------------------------------------------- Rede --

    def _join_group(self):
        username = self.username_var.get().strip()
        group = self.group_var.get().strip()
        port_str = self.port_var.get().strip()

        if not username:
            messagebox.showerror("Erro", "Informe seu nome.")
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

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", port))
            mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            sock.settimeout(1.0)
        except OSError as exc:
            messagebox.showerror("Erro de rede", str(exc))
            if sock:
                sock.close()
            return

        self.sock, self.current_group, self.current_port, self.running = sock, group, port, True
        threading.Thread(target=self._recv_loop, daemon=True).start()

        self.login.pack_forget()
        self.chat.pack(fill=tk.BOTH, expand=True)
        self._draw_avatar(group.split(".")[-1])
        self.title_lbl.config(text=f"Grupo {group}")
        self.sub_lbl.config(text=f"porta {port} · você entrou como {username}")
        self._date_chip(datetime.now().strftime("%d/%m/%Y"))
        self._chip(f"Você entrou no grupo como {username}")
        self.msg_entry.focus_set()
        self._hide_placeholder()

    def _leave_group(self):
        if not self.running:
            return
        self.running = False
        if self.sock:
            try:
                mreq = struct.pack("=4sl", socket.inet_aton(self.current_group), socket.INADDR_ANY)
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            except OSError:
                pass
            self.sock.close()
            self.sock = None
        for child in self.list.winfo_children():
            child.destroy()
        self.pending.clear()
        self.last_date = None
        self.chat.pack_forget()
        self.login.pack(fill=tk.BOTH, expand=True)

    def _send_message(self):
        if not self.running or self.msg_entry.cget("fg") == META:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        now = datetime.now()
        mid = uuid.uuid4().hex
        payload = {
            "date": now.strftime("%d/%m/%Y"),
            "time": now.strftime("%H:%M:%S"),
            "username": self.username_var.get().strip(),
            "message": text,
            "id": mid,
            "client": self.client_id,
        }
        try:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.sock.sendto(raw, (self.current_group, self.current_port))
        except OSError as exc:
            messagebox.showerror("Erro ao enviar", str(exc))
            return
        self.msg_entry.delete(0, tk.END)
        self._date_chip(payload["date"])
        canvas, tick = self._bubble(text, now.strftime("%H:%M"), own=True)
        self.pending[mid] = (canvas, tick)

    def _recv_loop(self):
        """Roda numa thread separada; entrega o que chega para a thread da interface pela fila."""
        while self.running:
            try:
                raw, _addr = self.sock.recvfrom(65535)
                self.inbox.put(json.loads(raw.decode("utf-8")))
            except socket.timeout:
                continue
            except (OSError, ValueError):
                if not self.running:
                    break

    def _drain_inbox(self):
        while True:
            try:
                payload = self.inbox.get_nowait()
            except queue.Empty:
                break
            self._on_payload(payload)
        self.root.after(50, self._drain_inbox)

    def _on_payload(self, payload):
        if not self.running:
            return
        if payload.get("client") == self.client_id:
            # Eco da própria mensagem: chegou ao grupo, vira "entregue" (dois checks azuis).
            canvas, tick = self.pending.pop(payload.get("id"), (None, None))
            if canvas and tick:
                canvas.itemconfigure(tick, text="✓✓", fill=BLUE_TICK)
            return
        name = payload.get("username", "?")
        date = payload.get("date", datetime.now().strftime("%d/%m/%Y"))
        time_ = payload.get("time", "")[:5]
        self._date_chip(date)
        self._bubble(payload.get("message", ""), time_, own=False, name=name)

    def on_close(self):
        self._leave_group()
        self.root.destroy()


def enable_dpi_awareness():
    """No Windows com escala de tela, evita que a janela saia borrada."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    app = ChatApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
