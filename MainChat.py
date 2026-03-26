import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import socket
import json
import threading
from datetime import datetime
import ipaddress

class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multicast Chat Application")
        self.root.geometry("600x500")
        
        self.username = tk.StringVar()
        self.multicast_group = tk.StringVar(value="239.255.0.1")
        self.port = tk.IntVar(value=5000)
        self.socket = None
        self.running = False
        self.lock = threading.Lock()
        
        self.create_gui()
        
    def create_gui(self):
        # Configuration Frame
        config_frame = tk.Frame(self.root)
        config_frame.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Label(config_frame, text="Username:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(config_frame, textvariable=self.username, width=20).grid(row=0, column=1, padx=5)
        
        tk.Label(config_frame, text="Multicast Group:").grid(row=1, column=0, sticky=tk.W)
        tk.Entry(config_frame, textvariable=self.multicast_group, width=20).grid(row=1, column=1, padx=5)
        
        tk.Label(config_frame, text="Port:").grid(row=2, column=0, sticky=tk.W)
        tk.Entry(config_frame, textvariable=self.port, width=20).grid(row=2, column=1, padx=5)
        
        # Button Frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5, fill=tk.X, padx=10)
        
        self.connect_btn = tk.Button(button_frame, text="Connect", command=self.connect, bg="green", fg="white")
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = tk.Button(button_frame, text="Disconnect", command=self.disconnect, bg="red", fg="white", state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Chat Display
        tk.Label(self.root, text="Chat Messages:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.chat_display = scrolledtext.ScrolledText(self.root, height=15, width=70, state=tk.DISABLED)
        self.chat_display.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        # Message Input Frame
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10, padx=10, fill=tk.X)
        
        tk.Label(input_frame, text="Message:").pack(anchor=tk.W)
        self.message_input = tk.Entry(input_frame, width=70)
        self.message_input.pack(fill=tk.X, pady=5)
        self.message_input.bind("<Return>", lambda e: self.send_message())
        
        self.send_btn = tk.Button(input_frame, text="Send", command=self.send_message, state=tk.DISABLED)
        self.send_btn.pack()
        
    def display_message(self, msg):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, msg + "\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
    def connect(self):
        if not self.username.get():
            messagebox.showerror("Error", "Please enter a username")
            return
            
        try:
            ipaddress.ip_address(self.multicast_group.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid multicast group IP")
            return
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port.get()))
            
            group = ipaddress.ip_address(self.multicast_group.get())
            mreq = socket.inet_aton(self.multicast_group.get()) + socket.inet_aton("0.0.0.0")
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            self.running = True
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.username.config(state=tk.DISABLED)
            self.multicast_group.config(state=tk.DISABLED)
            self.port.config(state=tk.DISABLED)
            
            self.display_message(f"[SYSTEM] Connected to {self.multicast_group.get()}:{self.port.get()}")
            
            threading.Thread(target=self.receive_messages, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            
    def disconnect(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self.username.config(state=tk.NORMAL)
        self.multicast_group.config(state=tk.NORMAL)
        self.port.config(state=tk.NORMAL)
        
        self.display_message("[SYSTEM] Disconnected")
        
    def send_message(self):
        if not self.message_input.get() or not self.running:
            return
        
        try:
            now = datetime.now()
            payload = {
                "date": now.strftime("%d/%m/%Y"),
                "time": now.strftime("%H:%M:%S"),
                "username": self.username.get(),
                "message": self.message_input.get()
            }
            
            message_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.socket.sendto(message_json, (self.multicast_group.get(), self.port.get()))
            
            self.message_input.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Send Error", str(e))
            
    def receive_messages(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                payload = json.loads(data.decode('utf-8'))
                
                msg = f"[{payload['time']}] {payload['username']}: {payload['message']}"
                self.display_message(msg)
            except Exception as e:
                if self.running:
                    pass

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
