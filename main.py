import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging
from datetime import datetime
from pathlib import Path

# Logging para ficheiro (pythonw nao tem consola)
_LOG_DIR = Path.home() / "ITInventory"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8")]
)
log = logging.getLogger("ITInventory")
log.info("Aplicacao a iniciar...")

import core.database as db
from core.discovery import DiscoveryEngine, PingMonitor
from core.network_monitor import NetworkMonitor, get_live_status
from core.switch_monitor import SwitchMonitor
from core.scheduler import JobScheduler

def _start_api_safe():
    """Arranca Flask API em background; erros vao para o log."""
    try:
        from api import start_api
        api_key = db.get_setting("web_api_key") or None
        start_api(host="0.0.0.0", port=5050, api_key=api_key if api_key else None)
        log.info("API REST iniciada em 0.0.0.0:5050")
    except Exception as e:
        log.error(f"Erro ao iniciar API: {e}")



# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ROLE_NAV = {
    "admin":           {"dashboard","assets","discovery","network","printers","alerts","consumables","ai","users","settings"},
    "printer_manager": {"dashboard","assets","network","printers","alerts","consumables"},
    "normal":          {"dashboard","assets","network","printers","alerts","consumables"},
}
ROLE_LABELS = {"admin": "Administrador", "printer_manager": "Printer Manager", "normal": "Visualizador"}

ACCENT  = "#4f7cff"
GREEN   = "#22c55e"
RED     = "#ef4444"
AMBER   = "#f59e0b"
BG      = "#0f1117"
BG2     = "#161b27"
BG3     = "#1e2535"
TEXT    = "#e8ecf4"
TEXT2   = "#8b95ab"

# ── Helpers ───────────────────────────────────────────────────────────────────

def status_color(status):
    return GREEN if status == "Online" else RED if status == "Offline" else AMBER

def confidence_color(c):
    try: c = float(c)
    except: return AMBER
    return GREEN if c >= 0.85 else AMBER if c >= 0.6 else RED

def badge_text(status):
    icons = {"Online": "●", "Offline": "○", "Manutenção": "◐"}
    return icons.get(status, "?") + " " + status

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class ITInventoryApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.init_db()

        self._role     = None
        self._user_id  = None
        self._username = None

        self.title("IT Inventory — SML Portugal")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)

        self._queue      = queue.Queue()
        self._monitor    = PingMonitor(status_callback=self._on_ping_cycle_done)
        self._netmon     = NetworkMonitor(sample_callback=self._on_network_sample)
        self._swmon      = SwitchMonitor()
        self._scheduler  = JobScheduler()
        self._engine     = None
        self._current_panel = "dashboard"

        self._stats_cache_ts = 0.0
        self.withdraw()  # esconde até ao login
        self._build_layout()

        threading.Thread(target=_start_api_safe, daemon=True).start()
        self.after(150, self._show_login)
        self.after(1500, self._process_queue)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=220, fg_color=BG2, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsw")
        self._sidebar.grid_propagate(False)
        self._build_sidebar()

        # Main area
        self._main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._main.grid(row=0, column=1, sticky="nsew")
        self._main.grid_rowconfigure(1, weight=1)
        self._main.grid_columnconfigure(0, weight=1)

        # Top bar
        self._topbar = ctk.CTkFrame(self._main, height=52, fg_color=BG2, corner_radius=0)
        self._topbar.grid(row=0, column=0, sticky="ew")
        self._topbar.grid_propagate(False)
        self._page_title = ctk.CTkLabel(self._topbar, text="Dashboard",
                                        font=ctk.CTkFont(size=16, weight="bold"),
                                        text_color=TEXT)
        self._page_title.pack(side="left", padx=20, pady=14)

        self._status_dot = ctk.CTkLabel(self._topbar, text="● Online",
                                        font=ctk.CTkFont(size=12), text_color=GREEN)
        self._status_dot.pack(side="right", padx=20)

        # Content frame
        self._content = ctk.CTkFrame(self._main, fg_color=BG, corner_radius=0)
        self._content.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        # Build all panels
        self._panels = {}
        for name, cls in [
            ("dashboard",    DashboardPanel),
            ("assets",       AssetsPanel),
            ("discovery",    DiscoveryPanel),
            ("network",      NetworkMonitorPanel),
            ("printers",     PrintersPanel),
            ("consumables",  ConsumablesPanel),
            ("alerts",       AlertsPanel),
            ("ai",           AIPanel),
            ("users",        UsersPanel),
            ("settings",     SettingsPanel),
        ]:
            panel = cls(self._content, app=self)
            panel.grid(row=0, column=0, sticky="nsew")
            self._panels[name] = panel

    def _build_sidebar(self):
        # Logo
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=60)
        logo_frame.pack(fill="x", padx=10, pady=(16,8))
        logo_icon = ctk.CTkFrame(logo_frame, width=32, height=32,
                                 fg_color=ACCENT, corner_radius=8)
        logo_icon.pack(side="left")
        logo_icon.pack_propagate(False)
        ctk.CTkLabel(logo_icon, text="IT", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="white").pack(expand=True)
        ctk.CTkLabel(logo_frame, text="IT Inventory\nSML Portugal",
                     font=ctk.CTkFont(size=12), text_color=TEXT,
                     justify="left").pack(side="left", padx=10)

        ctk.CTkFrame(self._sidebar, height=1, fg_color=BG3).pack(fill="x", padx=0)

        self._nav_items_def = [
            ("Geral", None),
            ("Dashboard",            "dashboard",   "⊞"),
            ("Ativos IT",            "assets",      "□"),
            ("Monitorização", None),
            ("Auto-Discovery",       "discovery",   "◉"),
            ("Monitorização de Rede","network",     "↕"),
            ("Impressoras / SNMP",   "printers",    "⊟"),
            ("Gestão", None),
            ("Alertas",              "alerts",      "△"),
            ("Consumíveis / Stock",  "consumables", "◻"),
            ("IA — Faturas & MACs",  "ai",          "✦"),
            ("Sistema", None),
            ("Utilizadores",         "users",       "◈"),
            ("Configurações",        "settings",    "⚙"),
        ]

        # Container que vai ser reconstruído no login (mantém a ordem correcta)
        self._nav_area = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        self._nav_area.pack(fill="x")
        self._nav_btns = {}
        self._rebuild_nav()  # constrói tudo inicialmente (antes do login)

        # User info at bottom
        ctk.CTkFrame(self._sidebar, height=1, fg_color=BG3).pack(fill="x", side="bottom", pady=(0,0))
        user_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent", height=52)
        user_frame.pack(fill="x", side="bottom", padx=10, pady=8)
        av = ctk.CTkFrame(user_frame, width=28, height=28, fg_color=ACCENT, corner_radius=14)
        av.pack(side="left")
        av.pack_propagate(False)
        ctk.CTkLabel(av, text="DG", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="white").pack(expand=True)
        user_info = ctk.CTkFrame(user_frame, fg_color="transparent")
        user_info.pack(side="left", padx=8)
        self._user_lbl = ctk.CTkLabel(user_info, text="—",
                                      font=ctk.CTkFont(size=11, weight="bold"),
                                      text_color=TEXT, justify="left")
        self._user_lbl.pack(anchor="w")
        self._role_lbl = ctk.CTkLabel(user_info, text="A autenticar...",
                                      font=ctk.CTkFont(size=10), text_color=TEXT2, justify="left")
        self._role_lbl.pack(anchor="w")

    # ── Login & Role ──────────────────────────────────────────────────────────

    def _show_login(self):
        dlg = LoginDialog(self, on_success=self._on_login_success)
        self.wait_window(dlg)
        if not self._role:
            self.destroy()
            return
        self._apply_role_to_sidebar()
        for panel in self._panels.values():
            if hasattr(panel, "_role_setup"):
                panel._role_setup(self._role)
        self.deiconify()
        self._show_panel("dashboard")
        self.after(2000, self._start_background_monitors)

    def _on_login_success(self, role, username, user_id):
        self._role     = role
        self._user_id  = user_id
        self._username = username
        self._user_lbl.configure(text=username)
        self._role_lbl.configure(text=ROLE_LABELS.get(role, role))

    def _rebuild_nav(self, allowed=None):
        """Reconstrói os itens de navegação do sidebar.
        Se allowed=None mostra tudo; caso contrário mostra só os keys permitidos.
        Secções (labels) só aparecem se tiverem pelo menos um item visível depois.
        """
        for w in self._nav_area.winfo_children():
            w.destroy()
        self._nav_btns = {}
        pending_section = None
        for item in self._nav_items_def:
            if item[1] is None:          # é um label de secção
                pending_section = item[0]
                continue
            label, key, icon = item
            if allowed is not None and key not in allowed:
                continue
            # Só cria o label de secção quando há um item visível após ele
            if pending_section is not None:
                ctk.CTkLabel(self._nav_area, text=pending_section.upper(),
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=TEXT2).pack(anchor="w", padx=14, pady=(12, 2))
                pending_section = None
            btn = ctk.CTkButton(
                self._nav_area, text=f"  {icon}  {label}",
                font=ctk.CTkFont(size=13), anchor="w",
                fg_color="transparent", text_color=TEXT2,
                hover_color=BG3, height=34, corner_radius=8,
                command=lambda k=key: self._show_panel(k))
            btn.pack(fill="x", padx=8, pady=1)
            self._nav_btns[key] = btn

    def _apply_role_to_sidebar(self):
        allowed = ROLE_NAV.get(self._role or "normal", set())
        self._rebuild_nav(allowed=allowed)

    def _show_panel(self, name):
        for k, btn in self._nav_btns.items():
            btn.configure(fg_color=ACCENT if k == name else "transparent",
                          text_color="white" if k == name else TEXT2)
        titles = {
            "dashboard":   "Dashboard",
            "assets":      "Ativos IT",
            "discovery":   "Auto-Discovery",
            "network":     "Monitorização de Rede",
            "printers":    "Impressoras / SNMP",
            "consumables": "Consumíveis & Stock",
            "alerts":      "Alertas & Notificações",
            "ai":          "IA — Faturas, MACs & Stock",
            "users":       "Gestão de Utilizadores",
            "settings":    "Configurações",
        }
        self._page_title.configure(text=titles.get(name, name))
        self._current_panel = name
        self._panels[name].tkraise()
        self._panels[name].refresh()

    def _start_background_monitors(self):
        self._monitor.start()
        self._netmon.start()
        self._swmon.start()
        if db.get_setting("scheduled_discovery", "1") == "1" or db.get_setting("scheduled_printer_poll", "1") == "1":
            self._scheduler.start(delay_first_discovery_s=300)

    def _on_ping_cycle_done(self):
        self._queue.put(("ping_done",))

    def _update_status_dot(self):
        stats = db.get_stats()
        pct = round(stats["online"] / max(stats["total"], 1) * 100)
        self._status_dot.configure(
            text=f"● {stats['online']} online  {stats['offline']} offline",
            text_color=GREEN if pct >= 90 else AMBER)

    def _process_queue(self):
        ping_pending = False
        network_pending = False
        try:
            while True:
                item = self._queue.get_nowait()
                if item[0] == "ping_done":
                    ping_pending = True
                elif item[0] == "network":
                    network_pending = True
        except queue.Empty:
            pass
        if ping_pending:
            self._update_status_dot()
            if self._current_panel == "dashboard":
                self._panels["dashboard"].refresh()
        if network_pending and self._current_panel == "network":
            self._panels["network"].refresh(light=True)
        self.after(2000, self._process_queue)

    def _on_network_sample(self, _data):
        self._queue.put(("network",))

    def on_closing(self):
        self._monitor.stop()
        self._netmon.stop()
        self._swmon.stop()
        self._scheduler.stop()
        if self._engine:
            self._engine.stop()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# PANELS
# ═══════════════════════════════════════════════════════════════════════════════

class BasePanel(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
    def refresh(self): pass

    def _card(self, parent, title=None, icon=""):
        frame = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=10,
                             border_width=1, border_color=BG3)
        if title:
            hdr = ctk.CTkFrame(frame, fg_color=BG3, corner_radius=0, height=36)
            hdr.pack(fill="x")
            hdr.pack_propagate(False)
            ctk.CTkLabel(hdr, text=f"{icon}  {title}" if icon else title,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=TEXT).pack(side="left", padx=14, pady=8)
        return frame

    def _metric(self, parent, label, value, color=TEXT):
        f = ctk.CTkFrame(parent, fg_color=BG3, corner_radius=8)
        ctk.CTkLabel(f, text=str(value),
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=color).pack(pady=(12,2))
        ctk.CTkLabel(f, text=label,
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT2).pack(pady=(0,12))
        return f

    def _scrollable_table(self, parent, columns, col_widths=None, height=400):
        frame = ctk.CTkFrame(parent, fg_color=BG2)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("IT.Treeview",
                        background=BG2, foreground=TEXT,
                        rowheight=30, fieldbackground=BG2,
                        borderwidth=0, font=("Segoe UI", 12))
        style.configure("IT.Treeview.Heading",
                        background=BG3, foreground=TEXT2,
                        borderwidth=0, font=("Segoe UI", 11, "bold"))
        style.map("IT.Treeview",
                  background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])

        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            style="IT.Treeview", height=height)
        for i, col in enumerate(columns):
            w = col_widths[i] if col_widths and i < len(col_widths) else 120
            tree.heading(col, text=col, anchor="w")
            tree.column(col, width=w, anchor="w")

        vsb = ctk.CTkScrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return frame, tree


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._built = False
        self._metric_labels = []
        self._alerts_frame = None
        self._lifecycle_frame = None

    def _ensure_build(self):
        if self._built:
            return
        self._built = True
        outer = ctk.CTkScrollableFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        mf = ctk.CTkFrame(outer, fg_color="transparent")
        mf.pack(fill="x", pady=(0, 16))
        keys = [
            ("total", "Total Ativos", TEXT),
            ("online", "Online", GREEN),
            ("offline", "Offline", RED),
            ("alerts_open", "Alertas Ativos", AMBER),
            ("replace", "Para Substituir", RED),
            ("review", "Para Revisão", AMBER),
        ]
        self._metric_labels = []
        for i, (key, lbl, col) in enumerate(keys):
            f = ctk.CTkFrame(mf, fg_color=BG3, corner_radius=8)
            val_lbl = ctk.CTkLabel(f, text="0", font=ctk.CTkFont(size=26, weight="bold"),
                                   text_color=col)
            val_lbl.pack(pady=(12, 2))
            ctk.CTkLabel(f, text=lbl, font=ctk.CTkFont(size=11), text_color=TEXT2).pack(pady=(0, 12))
            f.grid(row=0, column=i, padx=6, sticky="ew")
            mf.grid_columnconfigure(i, weight=1)
            self._metric_labels.append((key, val_lbl, col))

        cols = ctk.CTkFrame(outer, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure((0, 1), weight=1)

        ac = self._card(cols, "Alertas Recentes", "△")
        ac.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._alerts_frame = ctk.CTkFrame(ac, fg_color="transparent")
        self._alerts_frame.pack(fill="both", expand=True)

        lc = self._card(cols, "Ciclo de Vida — PCs", "◑")
        lc.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._lifecycle_frame = ctk.CTkFrame(lc, fg_color="transparent")
        self._lifecycle_frame.pack(fill="both", expand=True)

    def refresh(self):
        self._ensure_build()
        stats = db.get_stats()
        for key, lbl, col in self._metric_labels:
            lbl.configure(text=str(stats.get(key, 0)), text_color=col)

        for w in self._alerts_frame.winfo_children():
            w.destroy()
        alerts = db.get_open_alerts()[:8]
        if not alerts:
            ctk.CTkLabel(self._alerts_frame, text="Sem alertas activos",
                         text_color=TEXT2, font=ctk.CTkFont(size=12)).pack(pady=20)
        for al in alerts:
            rf = ctk.CTkFrame(self._alerts_frame, fg_color="transparent")
            rf.pack(fill="x", padx=12, pady=3)
            sev_col = RED if al["severity"] == "Critical" else AMBER
            ctk.CTkLabel(rf, text="●", text_color=sev_col,
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(rf, text=al["title"], text_color=TEXT,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ts = al["created_at"][:16].replace("T", " ") if al["created_at"] else ""
            ctk.CTkLabel(rf, text=ts, text_color=TEXT2,
                         font=ctk.CTkFont(size=10)).pack(side="right")

        for w in self._lifecycle_frame.winfo_children():
            w.destroy()
        lifecycle = db.get_lifecycle_report()
        if not lifecycle:
            ctk.CTkLabel(self._lifecycle_frame, text="Sem dados de ciclo de vida",
                         text_color=TEXT2).pack(pady=20)
            return
        max_cnt = max(r["cnt"] for r in lifecycle)
        for row in lifecycle:
            yr, cnt, age = row["acquisition_year"], row["cnt"], row["age"]
            color = RED if age >= 4 else AMBER if age == 3 else GREEN
            lf = ctk.CTkFrame(self._lifecycle_frame, fg_color="transparent")
            lf.pack(fill="x", padx=14, pady=4)
            label = f"{yr}  ({age}.º ano)" + (" ⚠" if age >= 4 else "")
            ctk.CTkLabel(lf, text=label, text_color=color,
                         font=ctk.CTkFont(size=12), width=160,
                         anchor="w").pack(side="left")
            bar_w = min(int(cnt / max(max_cnt, 1) * 200), 200)
            ctk.CTkFrame(lf, width=bar_w, height=12,
                         fg_color=color, corner_radius=3).pack(side="left", padx=8)
            ctk.CTkLabel(lf, text=f"{cnt} PCs", text_color=TEXT2,
                         font=ctk.CTkFont(size=11)).pack(side="left")


# ── Assets ────────────────────────────────────────────────────────────────────

class AssetsPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._selected_id = None
        self._build()

    def _build(self):
        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=52)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self._search_var = ctk.StringVar()
        self._debounce_id = None
        self._search_var.trace_add("write", lambda *_: self._schedule_refresh())
        ctk.CTkEntry(tb, textvariable=self._search_var, placeholder_text="Pesquisar...",
                     width=220, height=32).pack(side="left", padx=10, pady=10)

        self._type_var = ctk.StringVar(value="Todos")
        types = ["Todos","Desktop","Laptop","Servidor","Switch","Impressora",
                 "Access Point","NAS","Firewall","Outro","Desconhecido"]
        ctk.CTkOptionMenu(tb, variable=self._type_var, values=types, width=140,
                          command=lambda _: self.refresh()).pack(side="left", padx=4)

        self._status_var = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(tb, variable=self._status_var,
                          values=["Todos","Online","Offline","Manutenção"],
                          width=120, command=lambda _: self.refresh()).pack(side="left", padx=4)

        self._review_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(tb, text="Só revisão", variable=self._review_var,
                        command=self.refresh, text_color=TEXT2).pack(side="left", padx=10)

        self._btn_new = ctk.CTkButton(tb, text="＋ Novo", width=80, height=32,
                                      fg_color=ACCENT, command=self._new_asset)
        self._btn_new.pack(side="right", padx=10)
        ctk.CTkButton(tb, text="⟳", width=36, height=32, command=self.refresh,
                      fg_color=BG3).pack(side="right", padx=4)
        self._btn_del_all = ctk.CTkButton(tb, text="🗑 Remover Tudo", width=120, height=32,
                                          fg_color="#3d1515", text_color=RED,
                                          command=self._delete_all)
        self._btn_del_all.pack(side="right", padx=4)

        # Table
        tf, self._tree = self._scrollable_table(self,
            columns=["Hostname","Tipo","IP","Fabricante","Modelo","Dep.","Estado","Conf.","Ano"],
            col_widths=[160, 120, 120, 150, 180, 110, 90, 60, 60])
        tf.pack(fill="both", expand=True, padx=14, pady=(8,0))
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Bottom bar
        bb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=40)
        bb.pack(fill="x", side="bottom")
        self._count_lbl = ctk.CTkLabel(bb, text="", text_color=TEXT2,
                                       font=ctk.CTkFont(size=11))
        self._count_lbl.pack(side="left", padx=14, pady=10)
        self._btn_edit = ctk.CTkButton(bb, text="✎ Editar", width=80, height=28, fg_color=BG3,
                                       command=self._edit_selected)
        self._btn_edit.pack(side="right", padx=4, pady=6)
        self._btn_del = ctk.CTkButton(bb, text="🗑 Eliminar", width=90, height=28,
                                      fg_color="#3d1515", text_color=RED,
                                      command=self._delete_selected)
        self._btn_del.pack(side="right", padx=4, pady=6)

    def _role_setup(self, role):
        state = "normal" if role == "admin" else "disabled"
        for btn in (self._btn_new, self._btn_del_all, self._btn_edit, self._btn_del):
            btn.configure(state=state)

    def _schedule_refresh(self):
        if self._debounce_id:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(400, self._do_refresh)

    def _do_refresh(self):
        self._debounce_id = None
        self.refresh()

    def refresh(self):
        search = self._search_var.get() if hasattr(self, "_search_var") else ""
        ftype  = self._type_var.get()   if hasattr(self, "_type_var")   else "Todos"
        fstatus= self._status_var.get() if hasattr(self, "_status_var") else "Todos"
        freview= self._review_var.get() if hasattr(self, "_review_var") else False

        assets = db.get_all_assets(
            filter_type=None if ftype == "Todos" else ftype,
            filter_status=None if fstatus == "Todos" else fstatus,
            search=search or None,
            needs_review=True if freview else None)

        self._tree.delete(*self._tree.get_children())
        for a in assets:
            sc = status_color(a["status"])
            self._tree.insert("", "end", iid=str(a["id"]),
                values=(a["hostname"], a["type"], a["ip_address"] or "—",
                        a["manufacturer"] or "—", a["model"] or "—",
                        a["department"] or "—",
                        badge_text(a["status"]),
                        f"{float(a['confidence'] or 1)*100:.0f}%",
                        a["acquisition_year"] or "—"),
                tags=(a["status"],))

        self._tree.tag_configure("Online",     foreground=TEXT)
        self._tree.tag_configure("Offline",    foreground=RED)
        self._tree.tag_configure("Manutenção", foreground=AMBER)
        if hasattr(self, "_count_lbl"):
            self._count_lbl.configure(text=f"{len(assets)} dispositivos")

    def _on_select(self, _):
        sel = self._tree.selection()
        self._selected_id = int(sel[0]) if sel else None

    def _on_double_click(self, _):
        self._edit_selected()

    def _edit_selected(self):
        if not self._selected_id: return
        asset = db.get_asset(self._selected_id)
        if asset: AssetEditWindow(self, asset, on_save=self.refresh)

    def _new_asset(self):
        AssetEditWindow(self, None, on_save=self.refresh)

    def _delete_selected(self):
        if not self._selected_id: return
        if messagebox.askyesno("Confirmar", "Eliminar este ativo?"):
            db.delete_asset(self._selected_id)
            self._selected_id = None
            self.refresh()

    def _delete_all(self):
        total = len(self._tree.get_children())
        if total == 0:
            messagebox.showinfo("Inventário", "Não há ativos para eliminar.")
            return
        if messagebox.askyesno(
                "Confirmar eliminação total",
                f"Tens a certeza que queres eliminar TODOS os {total} ativos do inventário?\n\n"
                "Esta acção não pode ser revertida.",
                icon="warning"):
            deleted = db.delete_all_assets()
            self._selected_id = None
            self.refresh()
            messagebox.showinfo("Concluído", f"{deleted} ativos eliminados.")


# ── Asset Edit Window ─────────────────────────────────────────────────────────

class AssetEditWindow(ctk.CTkToplevel):
    FIELDS = [
        ("hostname",        "Hostname *"),
        ("type",            "Tipo"),
        ("ip_address",      "Endereço IP"),
        ("mac_address",     "MAC Address"),
        ("manufacturer",    "Fabricante"),
        ("model",           "Modelo"),
        ("serial_number",   "Número de série"),
        ("department",      "Departamento"),
        ("assigned_user",   "Utilizador atribuído"),
        ("os_version",      "Sistema operativo"),
        ("acquisition_year","Ano de aquisição"),
        ("purchase_price",  "Preço de compra (€)"),
        ("purchase_date",   "Data de compra"),
        ("supplier",        "Fornecedor"),
        ("warranty_years",  "Garantia (anos)"),
        ("notes",           "Notas"),
    ]
    TYPES = ["Desktop","Laptop","Servidor","Switch","Impressora",
             "Access Point","NAS","Firewall","Câmara CCTV","Outro","Desconhecido"]

    def __init__(self, parent, asset, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.asset   = dict(asset) if asset else {}
        self.title("Editar Ativo" if asset else "Novo Ativo")
        self.geometry("560x680")
        self.configure(fg_color=BG)
        self._vars = {}
        self._build()

    def _build(self):
        sf = ctk.CTkScrollableFrame(self, fg_color=BG)
        sf.pack(fill="both", expand=True, padx=20, pady=16)

        for key, label in self.FIELDS:
            ctk.CTkLabel(sf, text=label, font=ctk.CTkFont(size=12),
                         text_color=TEXT2).pack(anchor="w", pady=(6,0))
            if key == "type":
                var = ctk.StringVar(value=self.asset.get(key, "Desktop"))
                ctk.CTkOptionMenu(sf, variable=var, values=self.TYPES,
                                  width=400).pack(anchor="w")
            else:
                var = ctk.StringVar(value=str(self.asset.get(key, "") or ""))
                ctk.CTkEntry(sf, textvariable=var, width=400,
                             placeholder_text=label).pack(anchor="w")
            self._vars[key] = var

        # Needs review toggle
        self._review_var = ctk.BooleanVar(value=bool(self.asset.get("needs_review", 0)))
        ctk.CTkCheckBox(sf, text="Requer revisão", variable=self._review_var,
                        text_color=AMBER).pack(anchor="w", pady=8)

        bf = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=52)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancelar", fg_color=BG3, width=100,
                      command=self.destroy).pack(side="right", padx=8, pady=10)
        ctk.CTkButton(bf, text="Guardar", fg_color=ACCENT, width=100,
                      command=self._save).pack(side="right", padx=4, pady=10)

    def _save(self):
        data = {k: (v.get() or None) for k, v in self._vars.items()}
        data["needs_review"] = 1 if self._review_var.get() else 0
        if self.asset.get("id"):
            data["id"] = self.asset["id"]
        db.upsert_asset(data)
        if self.on_save: self.on_save()
        self.destroy()


# ── Discovery ─────────────────────────────────────────────────────────────────

class DiscoveryPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        outer = ctk.CTkScrollableFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True)
        self._outer = outer

        # Config card
        cc = self._card(outer, "Configuração do scan", "◉")
        cc.pack(fill="x", padx=20, pady=(20,10))
        row = ctk.CTkFrame(cc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)

        ctk.CTkLabel(row, text="Subnet:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,6), pady=4)
        self._subnet = ctk.CTkEntry(row, width=160)
        self._subnet.insert(0, db.get_setting("subnet", "192.168.163.0/24"))
        self._subnet.grid(row=0, column=1, padx=6, pady=4)

        ctk.CTkLabel(row, text="Community:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=(12,6))
        self._community = ctk.CTkEntry(row, width=100)
        self._community.insert(0, db.get_setting("snmp_community", "public"))
        self._community.grid(row=0, column=3, padx=6)

        self._scan_btn = ctk.CTkButton(row, text="▶  Iniciar scan", width=140,
                                       fg_color=ACCENT, command=self._start_scan)
        self._scan_btn.grid(row=0, column=4, padx=(20,0))
        self._stop_btn = ctk.CTkButton(row, text="■  Parar", width=80,
                                       fg_color="#3d1515", text_color=RED,
                                       command=self._stop_scan, state="disabled")
        self._stop_btn.grid(row=0, column=5, padx=6)

        # Progress
        self._phase_lbl = ctk.CTkLabel(outer, text="Pronto para scan.",
                                       text_color=TEXT2, font=ctk.CTkFont(size=12))
        self._phase_lbl.pack(padx=20, anchor="w")
        self._progress = ctk.CTkProgressBar(outer, height=8, progress_color=ACCENT)
        self._progress.pack(fill="x", padx=20, pady=(4,0))
        self._progress.set(0)

        # Log
        lc = self._card(outer, "Log do scan", "≡")
        lc.pack(fill="x", padx=20, pady=10)
        self._log_box = ctk.CTkTextbox(lc, height=140, fg_color=BG3,
                                       text_color=TEXT2, font=ctk.CTkFont(family="Courier New", size=11))
        self._log_box.pack(fill="x", padx=10, pady=10)

        # Results
        rc = self._card(outer, "Dispositivos descobertos", "□")
        rc.pack(fill="both", expand=True, padx=20, pady=(0,20))

        # Actions bar inside results
        ab = ctk.CTkFrame(rc, fg_color="transparent")
        ab.pack(fill="x", padx=12, pady=8)
        self._result_count = ctk.CTkLabel(ab, text="", text_color=TEXT2,
                                          font=ctk.CTkFont(size=11))
        self._result_count.pack(side="left")
        ctk.CTkButton(ab, text="Confirmar todos", width=120, height=28,
                      fg_color=GREEN, text_color="white",
                      command=self._confirm_all).pack(side="right", padx=4)
        ctk.CTkButton(ab, text="Importar seleccionados", width=140, height=28,
                      fg_color=ACCENT, command=self._import_selected).pack(side="right", padx=4)

        tf, self._result_tree = self._scrollable_table(rc,
            columns=["IP","MAC","Hostname","Tipo","Fabricante","Conf.","SNMP","Estado"],
            col_widths=[120,150,160,120,160,60,55,80])
        tf.pack(fill="both", expand=True, padx=10, pady=(0,10))

    def refresh(self): pass

    def _start_scan(self):
        subnet = self._subnet.get()
        comm   = self._community.get()
        db.set_setting("subnet",         subnet)
        db.set_setting("snmp_community", comm)

        self._log_box.delete("1.0", "end")
        self._result_tree.delete(*self._result_tree.get_children())
        self._scan_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress.set(0)

        engine = DiscoveryEngine(
            progress_callback=lambda pct, msg: self.after(0, self._update_progress, pct, msg),
            log_callback=lambda msg, level="info": self.after(0, self._log, msg, level))
        self.app._engine = engine

        def run():
            results = engine.run_full_discovery(subnet)
            self.after(0, self._show_results, results)
            self.after(0, lambda: self._scan_btn.configure(state="normal"))
            self.after(0, lambda: self._stop_btn.configure(state="disabled"))

        threading.Thread(target=run, daemon=True).start()

    def _stop_scan(self):
        if self.app._engine:
            self.app._engine.stop()
        self._scan_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")

    def _update_progress(self, pct, msg):
        self._progress.set(pct / 100)
        self._phase_lbl.configure(text=msg)

    def _log(self, msg, level="info"):
        colors = {"ok": GREEN, "warn": AMBER, "err": RED, "info": TEXT2}
        col = colors.get(level, TEXT2)
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _show_results(self, results):
        self._result_tree.delete(*self._result_tree.get_children())
        for d in results:
            conf = float(d.get("confidence", 0.5))
            snmp = "✓" if d.get("snmp") else "—"
            self._result_tree.insert("", "end",
                values=(d.get("ip_address",""), d.get("mac_address",""),
                        d.get("hostname",""), d.get("type",""),
                        d.get("manufacturer",""),
                        f"{conf*100:.0f}%", snmp,
                        "Novo" if d.get("is_new") else "Actualizado"),
                tags=("new" if d.get("is_new") else "existing",
                      "review" if conf < 0.7 else "ok"))
        self._result_tree.tag_configure("review", foreground=AMBER)
        self._result_tree.tag_configure("new",    foreground=GREEN)
        self._result_count.configure(text=f"{len(results)} dispositivos encontrados")
        if self.app:
            self.app._panels["assets"].refresh()
            self.app._panels["dashboard"].refresh()

    def _confirm_all(self):
        n = len(self._result_tree.get_children())
        if n == 0:
            messagebox.showinfo("Aviso", "Sem resultados para confirmar.")
            return
        with db.get_conn() as c:
            c.execute("UPDATE assets SET needs_review=0")
        messagebox.showinfo("OK", f"{n} dispositivos confirmados no inventário.")
        if self.app:
            self.app._panels["assets"].refresh()
            self.app._panels["dashboard"].refresh()

    def _import_selected(self):
        sel = self._result_tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona pelo menos um dispositivo na tabela.")
            return
        confirmed = 0
        for iid in sel:
            vals = self._result_tree.item(iid)["values"]
            ip   = vals[0]  # IP é a 1ª coluna
            with db.get_conn() as c:
                rows = c.execute(
                    "UPDATE assets SET needs_review=0 WHERE ip_address=?", (ip,)
                ).rowcount
                confirmed += rows
        messagebox.showinfo("Confirmado", f"{confirmed} dispositivo(s) confirmado(s).")
        if self.app:
            self.app._panels["assets"].refresh()
            self.app._panels["dashboard"].refresh()


# ── Network monitoring ────────────────────────────────────────────────────────

class NetworkMonitorPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._refresh_job  = None
        self._sw_frames    = {}   # asset_id → (card_frame, table_widget)
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        outer = ctk.CTkScrollableFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=20)
        self._outer = outer

        # ── Bandwidth card ───────────────────────────────────────────────────
        bw = self._card(outer, "Banda larga (esta estação)", "↕")
        bw.pack(fill="x", pady=(0, 12))
        br = ctk.CTkFrame(bw, fg_color="transparent")
        br.pack(fill="x", padx=14, pady=14)
        self._down_lbl = ctk.CTkLabel(
            br, text="—", font=ctk.CTkFont(size=32, weight="bold"), text_color=GREEN)
        self._down_lbl.grid(row=0, column=0, padx=20, pady=8)
        ctk.CTkLabel(br, text="Entrada (download) Mbps", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=1, column=0)
        self._up_lbl = ctk.CTkLabel(
            br, text="—", font=ctk.CTkFont(size=32, weight="bold"), text_color=ACCENT)
        self._up_lbl.grid(row=0, column=1, padx=20, pady=8)
        ctk.CTkLabel(br, text="Saída (upload) Mbps", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=1, column=1)
        self._bw_note = ctk.CTkLabel(bw, text="", text_color=TEXT2, font=ctk.CTkFont(size=11))
        self._bw_note.pack(anchor="w", padx=14, pady=(0, 10))

        # ── Ping card ────────────────────────────────────────────────────────
        pc = self._card(outer, "Ping — Router / Firewall", "◎")
        pc.pack(fill="x", pady=(0, 12))
        self._ping_frame = ctk.CTkFrame(pc, fg_color="transparent")
        self._ping_frame.pack(fill="x", padx=14, pady=12)

        # ── Switch ports card ─────────────────────────────────────────────────
        sc = self._card(outer, "Switches — Tráfego por porta (SNMP)", "⇄")
        sc.pack(fill="x", pady=(0, 12))
        self._sw_note = ctk.CTkLabel(
            sc,
            text="A aguardar primeiro poll (intervalo 60 s)…\n"
                 "Adiciona switches ao inventário para ver as portas aqui.",
            text_color=TEXT2, font=ctk.CTkFont(size=12))
        self._sw_note.pack(anchor="w", padx=14, pady=10)
        self._sw_container = ctk.CTkFrame(sc, fg_color="transparent")
        self._sw_container.pack(fill="x", padx=10, pady=(0, 10))

        # ── Bandwidth history ─────────────────────────────────────────────────
        hc = self._card(outer, "Histórico de banda (últimas 24 h)", "≡")
        hc.pack(fill="x", pady=(0, 12))
        tf, self._hist_tree = self._scrollable_table(
            hc,
            columns=["Hora", "Entrada Mbps", "Saída Mbps"],
            col_widths=[180, 140, 140], height=10)
        tf.pack(fill="x", padx=10, pady=10)

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self, light=False):
        if self.app and not self.app._netmon._started:
            self.app._netmon.start()
        if self.app and not self.app._swmon._started:
            self.app._swmon.start()
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(15000, lambda: self.refresh(light=False))

        self._refresh_bandwidth()
        if not light:
            self._refresh_pings()
            self._refresh_switch_ports()
            self._refresh_history()

    def _refresh_bandwidth(self):
        status = get_live_status()
        cfg = status.get("config", {})
        bw  = status.get("bandwidth")
        if not cfg.get("psutil_available"):
            self._down_lbl.configure(text="N/A", text_color=AMBER)
            self._up_lbl.configure(text="N/A", text_color=AMBER)
            self._bw_note.configure(
                text="Instala psutil: pip install psutil — depois reinicia a app.")
        elif bw:
            self._down_lbl.configure(text=f"{bw['down_mbps']:.2f}", text_color=GREEN)
            self._up_lbl.configure(text=f"{bw['up_mbps']:.2f}", text_color=ACCENT)
            ts = (bw.get("checked_at") or "")[:19].replace("T", " ")
            self._bw_note.configure(
                text=f"Última amostra: {ts}  ·  intervalo {cfg.get('interval_s', 30)} s")
        else:
            self._down_lbl.configure(text="…", text_color=TEXT2)
            self._up_lbl.configure(text="…", text_color=TEXT2)
            self._bw_note.configure(text="A aguardar primeira amostra…")
        return status

    def _refresh_pings(self):
        status = get_live_status()
        for w in self._ping_frame.winfo_children():
            w.destroy()
        pings   = {p["target_key"]: p for p in status.get("pings", [])}
        targets = status.get("targets") or []
        if not targets:
            ctk.CTkLabel(self._ping_frame,
                         text="Configura IP do router/firewall em Configurações.",
                         text_color=TEXT2).pack(anchor="w")
            return
        for entry in targets:
            key, label, ip = entry["key"], entry["label"], entry["ip"]
            p      = pings.get(key, {})
            online = bool(p.get("is_online")) if p else None
            ms     = p.get("ping_ms")         if p else None
            col    = GREEN if online else RED if online is False else TEXT2
            st     = "Online" if online else "Offline" if online is False else "—"
            row = ctk.CTkFrame(self._ping_frame, fg_color=BG3, corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=TEXT).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=ip, text_color=TEXT2,
                         font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(row,
                         text=f"{st}  {ms} ms" if ms else st,
                         text_color=col,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="right", padx=14)

    def _refresh_switch_ports(self):
        """Reconstrói a secção de switches com as portas SNMP actuais."""
        for w in self._sw_container.winfo_children():
            w.destroy()

        switches = db.get_all_switches_with_ports()
        if not switches:
            self._sw_note.configure(
                text="Nenhum switch no inventário ainda.\n"
                     "Corre o Auto-Discovery para detectar switches automaticamente.")
            return

        has_data = any(ports for _, ports in switches)
        if not has_data:
            self._sw_note.configure(
                text="Switches detectados. A aguardar primeiro poll SNMP (intervalo 60 s)…")
            return

        self._sw_note.configure(text="")

        for sw, ports in switches:
            if not ports:
                continue
            # ── Switch header ────────────────────────────────────────────────
            sw_frame = ctk.CTkFrame(self._sw_container, fg_color=BG2, corner_radius=10)
            sw_frame.pack(fill="x", pady=6)

            hdr = ctk.CTkFrame(sw_frame, fg_color="transparent")
            hdr.pack(fill="x", padx=12, pady=(10, 4))
            ctk.CTkLabel(hdr,
                         text=f"⇄  {sw['hostname']}",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=TEXT).pack(side="left")
            ctk.CTkLabel(hdr,
                         text=sw["ip_address"],
                         font=ctk.CTkFont(size=12),
                         text_color=TEXT2).pack(side="left", padx=10)
            up_count = sum(1 for p in ports if p["oper_status"] == 1)
            ctk.CTkLabel(hdr,
                         text=f"{up_count}/{len(ports)} portas UP",
                         font=ctk.CTkFont(size=12),
                         text_color=GREEN if up_count > 0 else TEXT2).pack(side="right")

            # ── Port table ───────────────────────────────────────────────────
            cols = ("Porta", "Alias", "Estado", "Speed", "In Mbps", "Out Mbps", "Actualizado")
            col_w = (130, 160, 70, 70, 90, 90, 150)
            tf, tree = self._scrollable_table(sw_frame, columns=list(cols),
                                              col_widths=list(col_w),
                                              height=min(len(ports), 16))
            tf.pack(fill="x", padx=10, pady=(4, 10))

            # Only show ports that are UP or have traffic — skip pure down-with-no-info ports
            shown = [p for p in ports if p["oper_status"] == 1
                     or (p["in_mbps"] is not None and p["in_mbps"] > 0)
                     or (p["out_mbps"] is not None and p["out_mbps"] > 0)]
            # Always show at least the first 8 ports regardless of status
            if not shown:
                shown = list(ports)[:8]

            for port in shown:
                status_icon = "●" if port["oper_status"] == 1 else "○"
                status_col  = GREEN if port["oper_status"] == 1 else TEXT2
                in_s  = f"{port['in_mbps']:.2f}"  if port["in_mbps"]  is not None else "—"
                out_s = f"{port['out_mbps']:.2f}" if port["out_mbps"] is not None else "—"
                spd_s = f"{port['speed_mbps']}" if port["speed_mbps"] else "—"
                ts    = (port["checked_at"] or "")[:19].replace("T", " ")
                alias = port["if_alias"] or ""
                iid = tree.insert("", "end", values=(
                    port["if_name"], alias,
                    f"{status_icon}", spd_s,
                    in_s, out_s, ts))
                # Colour the status cell
                tree.tag_configure("up",   foreground=GREEN)
                tree.tag_configure("down", foreground="#555e73")
                tag = "up" if port["oper_status"] == 1 else "down"
                tree.item(iid, tags=(tag,))

    def _refresh_history(self):
        self._hist_tree.delete(*self._hist_tree.get_children())
        for row in db.get_network_metrics_history(24, limit=48):
            ts = (row["checked_at"] or "")[:19].replace("T", " ")
            self._hist_tree.insert("", "end", values=(
                ts, f"{row['down_mbps']:.2f}", f"{row['up_mbps']:.2f}"))


# ── Printers ──────────────────────────────────────────────────────────────────

class PrintersPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        tb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=46)
        tb.pack(fill="x")
        self._btn_poll = ctk.CTkButton(tb, text="⟳  Polling SNMP agora", fg_color=ACCENT,
                                       command=self._poll_now, height=30)
        self._btn_poll.pack(side="left", padx=10, pady=8)
        tf, self._tree = self._scrollable_table(self,
            columns=["Impressora","IP","Toner K","Toner C","Toner M","Toner Y","Pág/mês","Total","Último poll"],
            col_widths=[200,120,90,90,90,90,80,90,140])
        tf.pack(fill="both", expand=True, padx=14, pady=10)

    def _role_setup(self, role):
        state = "normal" if role in ("admin", "printer_manager") else "disabled"
        self._btn_poll.configure(state=state)

    def refresh(self):
        self._tree.delete(*self._tree.get_children())
        assets = db.get_all_assets(filter_type="Impressora")
        for a in assets:
            tk_val  = a["toner_black"]   if a["toner_black"]   is not None else -1
            tc_val  = a["toner_cyan"]    if a["toner_cyan"]    is not None else -1
            tm_val  = a["toner_magenta"] if a["toner_magenta"] is not None else -1
            ty_val  = a["toner_yellow"]  if a["toner_yellow"]  is not None else -1
            def fmt(v): return f"{v}%" if v >= 0 else "N/A"
            poll = (a["last_poll"] or "")[:16].replace("T"," ")
            self._tree.insert("", "end",
                values=(a["hostname"], a["ip_address"] or "—",
                        fmt(tk_val), fmt(tc_val), fmt(tm_val), fmt(ty_val),
                        a["monthly_pages"] or 0, a["total_pages"] or 0, poll),
                tags=("critical" if any(0 <= v <= 15 for v in [tk_val,tc_val,tm_val,ty_val]) else "ok",))
        self._tree.tag_configure("critical", foreground=RED)

    def _poll_now(self):
        def do():
            from core.jobs import run_printer_snmp_poll
            run_printer_snmp_poll()
            self.after(0, self.refresh)
        threading.Thread(target=do, daemon=True).start()


# ── Consumables ───────────────────────────────────────────────────────────────

class ConsumablesPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        tb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=46)
        tb.pack(fill="x")
        self._btn_add = ctk.CTkButton(tb, text="＋ Adicionar", fg_color=ACCENT, height=30,
                                      command=self._add)
        self._btn_add.pack(side="left", padx=10, pady=8)
        self._btn_in = ctk.CTkButton(tb, text="▲ Entrada stock", fg_color=BG3, height=30,
                                     text_color=GREEN, command=lambda: self._quick_stock(+1))
        self._btn_in.pack(side="left", padx=4, pady=8)
        self._btn_out = ctk.CTkButton(tb, text="▼ Saída stock", fg_color=BG3, height=30,
                                      text_color=AMBER, command=lambda: self._quick_stock(-1))
        self._btn_out.pack(side="left", padx=4, pady=8)
        self._btn_ai = ctk.CTkButton(tb, text="✦ Agente IA — gerar encomenda", fg_color="#1a1a3e",
                                     text_color="#a5b4fc", border_color=ACCENT, border_width=1,
                                     height=30, command=self._run_stock_agent)
        self._btn_ai.pack(side="left", padx=6, pady=8)
        ctk.CTkButton(tb, text="⟳", width=36, height=30, fg_color=BG3,
                      command=self.refresh).pack(side="right", padx=10, pady=8)

        tf, self._tree = self._scrollable_table(self,
            columns=["Referência", "Tipo", "Compatível com", "Stock", "Mínimo", "Estado"],
            col_widths=[180, 150, 240, 65, 65, 110])
        tf.pack(fill="both", expand=True, padx=14, pady=10)
        self._tree.bind("<Double-1>", lambda _: self._edit_selected())

    def refresh(self):
        self._tree.delete(*self._tree.get_children())
        for c in db.get_all_consumables():
            is_low = c["stock_qty"] < c["stock_min"]
            is_out = c["stock_qty"] == 0
            status = "⊗ Sem stock" if is_out else "⚠ Stock baixo" if is_low else "✓ OK"
            tag    = "out" if is_out else "low" if is_low else "ok"
            self._tree.insert("", "end",
                values=(c["reference"], c["type"] or "—",
                        c["compatible_with"] or "—",
                        c["stock_qty"], c["stock_min"], status),
                tags=(tag,))
        self._tree.tag_configure("out", foreground=RED)
        self._tree.tag_configure("low", foreground=AMBER)
        self._tree.tag_configure("ok",  foreground=GREEN)

    def _role_setup(self, role):
        state = "normal" if role in ("admin", "printer_manager") else "disabled"
        for btn in (self._btn_add, self._btn_in, self._btn_out, self._btn_ai):
            btn.configure(state=state)

    def _add(self):
        ConsumableEditWindow(self, None, on_save=self.refresh)

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        ref = self._tree.item(sel[0])["values"][0]
        with db.get_conn() as c:
            row = c.execute("SELECT * FROM consumables WHERE reference=?", (ref,)).fetchone()
        if row:
            ConsumableEditWindow(self, dict(row), on_save=self.refresh)

    def _quick_stock(self, delta: int):
        """Ajuste rápido de +1/-1 no consumível seleccionado."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona um consumível primeiro.")
            return
        ref = self._tree.item(sel[0])["values"][0]
        with db.get_conn() as c:
            row = c.execute("SELECT * FROM consumables WHERE reference=?", (ref,)).fetchone()
            if not row:
                return
            new_qty = max(0, int(row["stock_qty"]) + delta)
            c.execute(
                "UPDATE consumables SET stock_qty=?, updated_at=datetime('now') WHERE reference=?",
                (new_qty, ref))
        action = "entrada" if delta > 0 else "saída"
        log.info("Stock manual %s: %s → %d", action, ref, new_qty)
        self.refresh()

    def _run_stock_agent(self):
        low = db.get_low_stock_consumables()
        if not low:
            messagebox.showinfo("Stock", "Sem consumíveis em stock baixo.")
            return
        def do():
            try:
                from core.ai_engine import run_stock_agent
                result = run_stock_agent(
                    [dict(i) for i in low],
                    vendor_pref="PC Diga / Staples / Amazon PT",
                    email_to=db.get_setting("email_to", "it@empresa.pt"))
                self.after(0, lambda: StockAgentResultWindow(self, result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro IA", str(e)))
        threading.Thread(target=do, daemon=True).start()


class ConsumableEditWindow(ctk.CTkToplevel):
    """
    Janela de edição de consumível.

    O campo 'Compatível com' aceita o hostname da impressora (ex: PRINTER-HP-01).
    Quando o sistema deteta que o toner foi substituído nessa impressora,
    desconta automaticamente 1 unidade deste consumível.
    """
    _TYPES = [
        "Toner Preto", "Toner Cyan", "Toner Magenta", "Toner Amarelo",
        "Tambor / Drum Preto", "Tambor / Drum Colorido",
        "Fusor", "Papel A4", "Papel A3", "Outro",
    ]

    def __init__(self, parent, item, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.item    = item or {}
        self.title("Consumível")
        self.geometry("500x500")
        self.configure(fg_color=BG)
        self._vars = {}

        sf = ctk.CTkScrollableFrame(self, fg_color=BG)
        sf.pack(fill="both", expand=True, padx=20, pady=16)

        # Referência
        ctk.CTkLabel(sf, text="Referência *  (ex: CF258A)", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(6,0))
        ref_var = ctk.StringVar(value=str(self.item.get("reference", "") or ""))
        ctk.CTkEntry(sf, textvariable=ref_var, width=420).pack(anchor="w")
        self._vars["reference"] = ref_var

        # Tipo — dropdown
        ctk.CTkLabel(sf, text="Tipo", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10,0))
        type_var = ctk.StringVar(value=str(self.item.get("type", "Toner Preto") or "Toner Preto"))
        ctk.CTkOptionMenu(sf, variable=type_var, values=self._TYPES,
                          fg_color=BG3, button_color=ACCENT, width=420).pack(anchor="w")
        self._vars["type"] = type_var

        # Compatível com — com sugestões de impressoras
        ctk.CTkLabel(sf,
                     text="Compatível com  (hostname da impressora — usado para desconto automático)",
                     text_color=TEXT2, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10,0))
        compat_var = ctk.StringVar(value=str(self.item.get("compatible_with", "") or ""))
        ctk.CTkEntry(sf, textvariable=compat_var, width=420).pack(anchor="w")
        self._vars["compatible_with"] = compat_var

        # Sugestões de hostnames de impressoras
        try:
            printers = db.get_all_assets(filter_type="Impressora")
            if printers:
                hints = "  Impressoras: " + "  |  ".join(
                    p["hostname"] for p in printers if p["hostname"])
                ctk.CTkLabel(sf, text=hints, text_color=TEXT2,
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(2,0))
        except Exception:
            pass

        # Stock e mínimo
        row2 = ctk.CTkFrame(sf, fg_color="transparent")
        row2.pack(fill="x", pady=(10,0))
        for col, (key, label, default) in enumerate([
            ("stock_qty", "Stock actual", "0"),
            ("stock_min", "Stock mínimo (alerta)", "2"),
        ]):
            ctk.CTkLabel(row2, text=label, text_color=TEXT2,
                         font=ctk.CTkFont(size=12)).grid(row=0, column=col, padx=(0,20), sticky="w")
            var = ctk.StringVar(value=str(self.item.get(key, default) or "0"))
            ctk.CTkEntry(row2, textvariable=var, width=160).grid(row=1, column=col, padx=(0,20))
            self._vars[key] = var

        # Botões +/- stock rápido
        sq_frame = ctk.CTkFrame(sf, fg_color="transparent")
        sq_frame.pack(anchor="w", pady=(6,0))
        ctk.CTkLabel(sq_frame, text="Ajuste rápido de stock:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,8))
        for delta, label in [(-5,"−5"),(-1,"−1"),(+1,"+1"),(+5,"+5"),(+10,"+10")]:
            ctk.CTkButton(sq_frame, text=label, width=40, height=26, fg_color=BG3,
                          text_color=GREEN if delta > 0 else AMBER,
                          command=lambda d=delta: self._adjust_stock(d)).pack(side="left", padx=2)

        bf = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=48)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancelar", fg_color=BG3,
                      command=self.destroy).pack(side="right", padx=8, pady=10)
        ctk.CTkButton(bf, text="Guardar", fg_color=ACCENT,
                      command=self._save).pack(side="right", padx=4, pady=10)

    def _adjust_stock(self, delta: int):
        try:
            current = int(self._vars["stock_qty"].get() or 0)
            self._vars["stock_qty"].set(str(max(0, current + delta)))
        except ValueError:
            self._vars["stock_qty"].set("0")

    def _save(self):
        data = {k: (v.get() or None) for k, v in self._vars.items()}
        for k in ("stock_qty", "stock_min"):
            try:
                data[k] = int(data[k] or 0)
            except (TypeError, ValueError):
                data[k] = 0
        if not data.get("reference"):
            messagebox.showwarning("Aviso", "Referência é obrigatória.")
            return
        try:
            db.upsert_consumable(data)
        except Exception as e:
            messagebox.showerror("Erro ao guardar", str(e))
            return
        if self.on_save:
            self.on_save()
        self.destroy()


class StockAgentResultWindow(ctk.CTkToplevel):
    def __init__(self, parent, result):
        super().__init__(parent)
        self.result = result
        self.title("Resultado do Agente IA — Encomenda")
        self.geometry("640x560")
        self.configure(fg_color=BG)
        sf = ctk.CTkScrollableFrame(self, fg_color=BG)
        sf.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(sf, text=f"Total estimado: {result.get('total_order',0):.2f} €",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=GREEN).pack(anchor="w")
        ctk.CTkLabel(sf, text=f"Assunto: {result.get('email_subject','')}",
                     font=ctk.CTkFont(size=12), text_color=TEXT2).pack(anchor="w", pady=4)
        ctk.CTkLabel(sf, text="Email gerado:", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(12,4))
        tb = ctk.CTkTextbox(sf, height=280, fg_color=BG3, text_color=TEXT,
                            font=ctk.CTkFont(family="Segoe UI", size=12))
        tb.pack(fill="both")
        tb.insert("1.0", result.get("email_body", ""))
        tb.configure(state="disabled")
        bf = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=48)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="✉  Enviar Email", fg_color=ACCENT,
                      command=self._send).pack(side="right", padx=8, pady=10)
        ctk.CTkButton(bf, text="Fechar", fg_color=BG3,
                      command=self.destroy).pack(side="right", padx=4, pady=10)

    def _send(self):
        try:
            from core.ai_engine import send_email
            send_email(self.result.get("email_subject","Encomenda consumíveis"),
                       self.result.get("email_body",""))
            messagebox.showinfo("Email", "Email enviado com sucesso.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erro", str(e))


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertsPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        tb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=46)
        tb.pack(fill="x")
        self._btn_resolve = ctk.CTkButton(tb, text="✓  Resolver seleccionado", height=30,
                                          fg_color=BG3, command=self._resolve)
        self._btn_resolve.pack(side="left", padx=10, pady=8)
        ctk.CTkButton(tb, text="⟳", width=36, height=30, fg_color=BG3,
                      command=self.refresh).pack(side="right", padx=10, pady=8)
        tf, self._tree = self._scrollable_table(self,
            columns=["Prioridade","Tipo","Título","Equipamento","Data","Estado"],
            col_widths=[90,100,300,160,140,90])
        tf.pack(fill="both", expand=True, padx=14, pady=10)

    def _role_setup(self, role):
        state = "normal" if role == "admin" else "disabled"
        self._btn_resolve.configure(state=state)

    def refresh(self):
        self._tree.delete(*self._tree.get_children())
        for al in db.get_open_alerts():
            tag = "critical" if al["severity"] == "Critical" else "warning"
            self._tree.insert("", "end", iid=str(al["id"]),
                values=(al["severity"], al["type"], al["title"],
                        al["hostname"] or "—",
                        (al["created_at"] or "")[:16].replace("T"," "),
                        al["status"]),
                tags=(tag,))
        self._tree.tag_configure("critical", foreground=RED)
        self._tree.tag_configure("warning",  foreground=AMBER)

    def _resolve(self):
        sel = self._tree.selection()
        if not sel: return
        db.resolve_alert(int(sel[0]))
        self.refresh()


# ── AI Panel ──────────────────────────────────────────────────────────────────

class AIPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        outer = ctk.CTkScrollableFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        # Invoice reader
        ic = self._card(outer, "Leitor de Faturas", "✦")
        ic.pack(fill="x", pady=(0,14))
        ib = ctk.CTkFrame(ic, fg_color="transparent")
        ib.pack(fill="x", padx=14, pady=12)

        self._invoice_path = ctk.StringVar()
        ctk.CTkEntry(ib, textvariable=self._invoice_path, width=340,
                     placeholder_text="Caminho do ficheiro PDF/imagem...").pack(side="left")
        ctk.CTkButton(ib, text="Escolher ficheiro", width=130,
                      command=self._pick_invoice).pack(side="left", padx=6)
        ctk.CTkButton(ib, text="✦  Analisar", fg_color=ACCENT, width=100,
                      command=self._analyze_invoice).pack(side="left", padx=6)

        ctk.CTkLabel(ic, text="Ou cola texto da fatura:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=14)
        self._invoice_text = ctk.CTkTextbox(ic, height=80, fg_color=BG3, text_color=TEXT)
        self._invoice_text.pack(fill="x", padx=14, pady=(4,10))

        self._invoice_result = ctk.CTkTextbox(ic, height=160, fg_color=BG3, text_color=GREEN,
                                              font=ctk.CTkFont(family="Courier New", size=11))
        self._invoice_result.pack(fill="x", padx=14, pady=(0,10))
        self._invoice_result.configure(state="disabled")

        ctk.CTkButton(ic, text="Adicionar ao inventário ▶", fg_color=GREEN,
                      text_color="white", command=self._add_from_invoice).pack(padx=14, pady=(0,12))

        # MAC Classifier
        mc = self._card(outer, "Classificação por MAC Address", "◈")
        mc.pack(fill="x", pady=(0,14))
        mb = ctk.CTkFrame(mc, fg_color="transparent")
        mb.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(mb, text="MACs (um por linha):", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self._mac_box = ctk.CTkTextbox(mb, height=100, fg_color=BG3, text_color=TEXT)
        self._mac_box.pack(fill="x", pady=6)
        self._mac_box.insert("1.0", "ec:67:94:35:9f:54\n68:4f:64:a7:e5:98\n24:5e:be:6c:6c:cb")
        ctk.CTkButton(mb, text="✦  Classificar MACs", fg_color=ACCENT,
                      command=self._classify_macs).pack(anchor="w", pady=4)
        self._mac_result = ctk.CTkTextbox(mb, height=140, fg_color=BG3, text_color=GREEN,
                                          font=ctk.CTkFont(family="Courier New", size=11))
        self._mac_result.pack(fill="x")
        self._mac_result.configure(state="disabled")

    def refresh(self): pass

    def _pick_invoice(self):
        path = filedialog.askopenfilename(
            filetypes=[("Faturas","*.pdf *.png *.jpg *.jpeg *.webp"),("Todos","*.*")])
        if path:
            self._invoice_path.set(path)

    def _analyze_invoice(self):
        path = self._invoice_path.get()
        text = self._invoice_text.get("1.0","end").strip()
        if not path and not text:
            messagebox.showwarning("Aviso","Escolhe um ficheiro ou cola o texto da fatura.")
            return
        def do():
            try:
                from core.ai_engine import read_invoice
                result = read_invoice(file_path=path or None, text=text or None)
                self._invoice_data = result
                lines = [f"{k:20s}: {v}" for k, v in result.items() if k != "missing_fields"]
                if result.get("missing_fields"):
                    lines.append(f"{'Campos em falta':20s}: {', '.join(result['missing_fields'])}")
                self.after(0, self._show_invoice_result, "\n".join(lines))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro IA", str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _show_invoice_result(self, text):
        self._invoice_result.configure(state="normal")
        self._invoice_result.delete("1.0","end")
        self._invoice_result.insert("1.0", text)
        self._invoice_result.configure(state="disabled")

    def _add_from_invoice(self):
        if not hasattr(self, "_invoice_data") or not self._invoice_data:
            messagebox.showwarning("Aviso","Analisa uma fatura primeiro.")
            return
        data = {k: v for k, v in self._invoice_data.items()
                if k not in ("missing_fields","confidence")}
        data["confidence"] = self._invoice_data.get("confidence", 0.9)
        db.upsert_asset(data)
        messagebox.showinfo("OK","Ativo adicionado ao inventário com dados da fatura.")
        if self.app:
            self.app._panels["assets"].refresh()

    def _classify_macs(self):
        macs = [m.strip() for m in self._mac_box.get("1.0","end").split("\n") if m.strip()]
        if not macs:
            messagebox.showwarning("Aviso","Introduz pelo menos um MAC address.")
            return
        def do():
            try:
                from core.ai_engine import classify_macs
                results = classify_macs(macs)
                lines = []
                for r in results:
                    lines.append(f"MAC: {r.get('mac','')}")
                    lines.append(f"  Fabricante : {r.get('manufacturer','?')}")
                    lines.append(f"  Tipo       : {r.get('type','?')}")
                    lines.append(f"  Hostname   : {r.get('hostname','?')}")
                    lines.append(f"  Confiança  : {float(r.get('confidence',0))*100:.0f}%")
                    if r.get("notes"): lines.append(f"  Notas      : {r.get('notes')}")
                    lines.append("")
                self.after(0, self._show_mac_result, "\n".join(lines))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro IA", str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _show_mac_result(self, text):
        self._mac_result.configure(state="normal")
        self._mac_result.delete("1.0","end")
        self._mac_result.insert("1.0", text)
        self._mac_result.configure(state="disabled")


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsPanel(BasePanel):
    FIELDS = [
        ("Rede", [
            ("subnet",          "Subnet a fazer scan",      "192.168.163.0/24"),
            ("snmp_community",  "SNMP Community String",    "public"),
            ("snmp_timeout_ms", "SNMP Timeout (ms)",        "3000"),
            ("discovery_use_ai","IA no discovery (1=sim)",  "1"),
            ("scheduled_discovery", "Discovery automático (1=sim)", "1"),
            ("discovery_interval_hours", "Intervalo discovery (horas)", "24"),
            ("scheduled_printer_poll", "Polling SNMP impressoras (1=sim)", "1"),
            ("printer_poll_interval_min", "Intervalo SNMP impressoras (min)", "15"),
            ("ping_interval_s", "Intervalo ping ativos (seg.)", "300"),
            ("ping_max_workers", "Threads ping simultâneas", "8"),
            ("background_monitors", "Monitores em background (1=sim)", "1"),
            ("offline_alert_min","Alerta offline após (min)","15"),
            ("toner_alert_pct", "Alerta toner abaixo (%)",  "15"),
        ]),
        ("Monitorização de Rede", [
            ("network_gateway_ip", "IP Router / Gateway (vazio = auto)", ""),
            ("network_firewall_ip","IP Firewall",                         ""),
            ("network_monitor_interval_s", "Intervalo rede (seg.)", "120"),
        ]),
        ("Active Directory", [
            ("dc_host",     "DC Host / IP",           "192.168.163.12"),
            ("ad_domain",   "Domínio",                "sml.com"),
            ("ad_user",     "Service Account",        "svc_inventory@..."),
            ("ad_password", "Password (AD)",          ""),
            ("ad_sync_enabled", "Sync AD/LDAP (1=sim)", "1"),
            ("ad_sync_interval_hours", "Intervalo sync AD (horas)", "6"),
        ]),
        ("Email / SMTP", [
            ("smtp_host",     "SMTP Host",      ""),
            ("smtp_port",     "Porta SMTP",     "587"),
            ("smtp_user",     "Email remetente",""),
            ("smtp_password", "Password SMTP",  ""),
            ("email_to",      "Enviar alertas para",""),
            ("alert_email_enabled", "Email automático em alertas (1=sim)", "1"),
        ]),
        ("Inteligência Artificial — Ollama (local, gratuito)", [
            ("ollama_host",         "Ollama URL",                    "http://localhost:11434"),
            ("ollama_model",        "Modelo de texto",               "llama3.2"),
            ("ollama_vision_model", "Modelo com visão (faturas)",    "llava"),
            ("ollama_num_ctx",      "Contexto Ollama (num_ctx)",     "2048"),
            ("ollama_num_threads",  "Threads CPU Ollama (vazio=auto)", ""),
        ]),
        ("Inteligência Artificial — Anthropic (opcional, requer key)", [
            ("ai_backend",    "Backend activo (ollama ou anthropic)", "ollama"),
            ("anthropic_key", "Anthropic API Key (sk-ant-...)",       ""),
        ]),
        ("Interface Web (Somente Leitura)", [
            ("web_api_key", "API Key para interface web (vazio = sem auth)", ""),
            ("web_cors_origins", "CORS origens (vírgulas)", "http://localhost:5050,http://127.0.0.1:5050,null"),
        ]),
    ]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._vars = {}
        self._build()

    def _build(self):
        outer = ctk.CTkScrollableFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        for section, fields in self.FIELDS:
            sc = self._card(outer, section)
            sc.pack(fill="x", pady=(0,14))
            sf = ctk.CTkFrame(sc, fg_color="transparent")
            sf.pack(fill="x", padx=14, pady=12)
            for key, label, placeholder in fields:
                ctk.CTkLabel(sf, text=label, text_color=TEXT2,
                             font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(6,0))
                var = ctk.StringVar(value=db.get_setting(key, placeholder))
                show = "*" if "password" in key.lower() or "key" in key.lower() else ""
                entry = ctk.CTkEntry(sf, textvariable=var, width=460,
                                     show=show, placeholder_text=placeholder)
                entry.pack(anchor="w")
                self._vars[key] = var

        bf = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=52)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Guardar todas as configurações",
                      fg_color=ACCENT, width=240,
                      command=self._save).pack(side="right", padx=14, pady=12)
        ctk.CTkButton(bf, text="Testar SMTP",
                      fg_color=BG3, width=120,
                      command=self._test_smtp).pack(side="right", padx=6, pady=12)
        ctk.CTkButton(bf, text="Testar IA (Ollama)",
                      fg_color=BG3, width=150,
                      command=self._test_ollama).pack(side="right", padx=6, pady=12)
        ctk.CTkButton(bf, text="Sync AD agora",
                      fg_color=BG3, width=120,
                      command=self._test_ad_sync).pack(side="right", padx=6, pady=12)

    def refresh(self):
        for key, var in self._vars.items():
            var.set(db.get_setting(key, ""))

    def _save(self):
        for key, var in self._vars.items():
            db.set_setting(key, var.get())
        db.invalidate_caches()
        messagebox.showinfo("OK", "Configurações guardadas.")

    def _test_ad_sync(self):
        self._save()
        def do():
            try:
                from core.ad_sync import sync_ad_to_inventory
                s = sync_ad_to_inventory()
                self.after(0, lambda: messagebox.showinfo(
                    "AD Sync",
                    f"Computadores no AD: {s.get('ad_total', 0)}\n"
                    f"Correspondências: {s.get('matched', 0)}\n"
                    f"Campos actualizados: {s.get('updated', 0)}\n"
                    f"Sem match no inventário: {s.get('not_found', 0)}",
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("AD Sync", str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _test_ollama(self):
        self._save()
        def do():
            try:
                from core.ai_engine import check_ollama_status
                s = check_ollama_status()
                if s["running"]:
                    models = ", ".join(s["models"]) if s["models"] else "nenhum instalado"
                    self.after(0, lambda: messagebox.showinfo(
                        "Ollama OK",
                        f"Ollama a correr em {s['host']}\n\n"
                        f"Modelos instalados:\n{models}\n\n"
                        f"Se o teu modelo nao aparece, corre no terminal:\n"
                        f"ollama pull {self._vars.get('ollama_model', type('',(),{'get':lambda s,d='':d})()).get('llama3.2')}"
                    ))
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "Ollama nao encontrado",
                        f"Nao foi possivel ligar a {s['host']}\n\n"
                        f"Para instalar:\n"
                        f"1. Vai a ollama.com/download\n"
                        f"2. Instala o Ollama\n"
                        f"3. Abre um terminal e corre: ollama pull llama3.2\n"
                        f"4. Ollama fica a correr automaticamente"
                    ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erro", str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _test_smtp(self):
        self._save()
        try:
            send_email("Teste IT Inventory",
                       "Este é um email de teste do sistema IT Inventory.")
            messagebox.showinfo("OK", "Email de teste enviado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro SMTP", str(e))


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_success=None):
        super().__init__(parent)
        self._on_success = on_success
        self.title("IT Inventory — Autenticação")
        self.geometry("400x320")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build()
        self.after(100, self._focus)

    def _focus(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=BG3, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        logo = ctk.CTkFrame(hdr, width=36, height=36, fg_color=ACCENT, corner_radius=8)
        logo.pack(side="left", padx=16, pady=14)
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="IT", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white").pack(expand=True)
        ctk.CTkLabel(hdr, text="IT Inventory — SML Portugal",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=8)

        frm = ctk.CTkFrame(self, fg_color="transparent")
        frm.pack(fill="both", expand=True, padx=32, pady=20)

        ctk.CTkLabel(frm, text="Utilizador", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self._user_var = ctk.StringVar()
        ctk.CTkEntry(frm, textvariable=self._user_var, width=336,
                     placeholder_text="username").pack(anchor="w", pady=(2, 10))

        ctk.CTkLabel(frm, text="Palavra-passe", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w")
        self._pass_var = ctk.StringVar()
        pe = ctk.CTkEntry(frm, textvariable=self._pass_var, width=336,
                          show="*", placeholder_text="password")
        pe.pack(anchor="w", pady=(2, 6))
        pe.bind("<Return>", lambda _: self._login())

        self._err = ctk.CTkLabel(frm, text="", text_color=RED,
                                  font=ctk.CTkFont(size=11))
        self._err.pack(anchor="w", pady=(0, 6))

        ctk.CTkButton(frm, text="Entrar", fg_color=ACCENT, width=336,
                      command=self._login).pack()

    def _login(self):
        user   = self._user_var.get().strip()
        passwd = self._pass_var.get()
        if not user or not passwd:
            self._err.configure(text="Preenche utilizador e palavra-passe.")
            return
        result = db.verify_user(user, passwd)
        if result:
            self.grab_release()
            if self._on_success:
                self._on_success(result["role"], result["username"], result["id"])
            self.destroy()
        else:
            self._err.configure(text="Credenciais inválidas.")
            self._pass_var.set("")

    def _cancel(self):
        self.grab_release()
        self.destroy()


# ── Users Panel ───────────────────────────────────────────────────────────────

class UsersPanel(BasePanel):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._build()

    def _build(self):
        tb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=46)
        tb.pack(fill="x")
        ctk.CTkButton(tb, text="＋ Novo Utilizador", fg_color=ACCENT, height=30,
                      command=self._add).pack(side="left", padx=10, pady=8)
        ctk.CTkButton(tb, text="⟳", width=36, height=30, fg_color=BG3,
                      command=self.refresh).pack(side="right", padx=10, pady=8)

        tf, self._tree = self._scrollable_table(self,
            columns=["Utilizador", "Perfil", "Último login", "Criado em"],
            col_widths=[220, 180, 160, 160])
        tf.pack(fill="both", expand=True, padx=14, pady=10)
        self._tree.bind("<Double-1>", lambda _: self._edit_selected())

        bb = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=40)
        bb.pack(fill="x", side="bottom")
        ctk.CTkButton(bb, text="🗑 Eliminar", width=90, height=28, fg_color="#3d1515",
                      text_color=RED, command=self._delete_selected).pack(side="right", padx=4, pady=6)
        ctk.CTkButton(bb, text="✎ Editar", width=80, height=28, fg_color=BG3,
                      command=self._edit_selected).pack(side="right", padx=4, pady=6)

    def refresh(self):
        self._tree.delete(*self._tree.get_children())
        for u in db.get_all_users():
            self._tree.insert("", "end", iid=str(u["id"]),
                values=(u["username"],
                        ROLE_LABELS.get(u["role"], u["role"]),
                        (u["last_login"] or "—")[:16].replace("T", " "),
                        (u["created_at"] or "—")[:16].replace("T", " ")),
                tags=("admin" if u["role"] == "admin" else "user",))
        self._tree.tag_configure("admin", foreground=ACCENT)
        self._tree.tag_configure("user",  foreground=TEXT)

    def _add(self):
        UserEditWindow(self, None, on_save=self.refresh)

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        with db.get_conn() as c:
            row = c.execute("SELECT id, username, role FROM users WHERE id=?", (uid,)).fetchone()
        if row:
            UserEditWindow(self, dict(row), on_save=self.refresh)

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        if self.app and uid == self.app._user_id:
            messagebox.showwarning("Aviso", "Não podes eliminar a tua própria conta.")
            return
        with db.get_conn() as c:
            row = c.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
        if row and messagebox.askyesno("Confirmar", f"Eliminar utilizador '{row['username']}'?"):
            db.delete_user(uid)
            self.refresh()


class UserEditWindow(ctk.CTkToplevel):
    _ROLES = [("Administrador", "admin"), ("Printer Manager", "printer_manager"), ("Visualizador", "normal")]

    def __init__(self, parent, user, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.user    = user or {}
        title_suffix = f" — {user['username']}" if user else " — Novo"
        self.title(f"Utilizador{title_suffix}")
        self.geometry("460x400")
        self.configure(fg_color=BG)
        self._build()
        self.after(100, lambda: (self.lift(), self.focus_force()))

    def _build(self):
        bf = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0, height=48)
        bf.pack(fill="x", side="bottom")
        ctk.CTkButton(bf, text="Cancelar", fg_color=BG3,
                      command=self.destroy).pack(side="right", padx=8, pady=10)
        ctk.CTkButton(bf, text="Guardar", fg_color=ACCENT,
                      command=self._save).pack(side="right", padx=4, pady=10)

        sf = ctk.CTkScrollableFrame(self, fg_color=BG)
        sf.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(sf, text="Utilizador *", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(4, 0))
        self._user_var = ctk.StringVar(value=self.user.get("username", ""))
        ctk.CTkEntry(sf, textvariable=self._user_var, width=400,
                     state="disabled" if self.user else "normal").pack(anchor="w")

        ctk.CTkLabel(sf, text="Perfil", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10, 0))
        current_role    = self.user.get("role", "normal")
        current_display = next((d for d, v in self._ROLES if v == current_role), "Visualizador")
        self._role_var  = ctk.StringVar(value=current_display)
        ctk.CTkOptionMenu(sf, variable=self._role_var,
                          values=[d for d, _ in self._ROLES],
                          fg_color=BG3, button_color=ACCENT, width=400).pack(anchor="w")

        lbl_pw = ("Nova p" if self.user else "P") + "alavra-passe" + (" *" if not self.user else "")
        ctk.CTkLabel(sf, text=lbl_pw, text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10, 0))
        if self.user:
            ctk.CTkLabel(sf, text="(deixar em branco para não alterar)",
                         text_color=TEXT2, font=ctk.CTkFont(size=10)).pack(anchor="w")
        self._pass_var = ctk.StringVar()
        ctk.CTkEntry(sf, textvariable=self._pass_var, width=400,
                     show="*").pack(anchor="w")

        ctk.CTkLabel(sf, text="Confirmar palavra-passe" + (" *" if not self.user else ""),
                     text_color=TEXT2, font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(10, 0))
        self._pass2_var = ctk.StringVar()
        ctk.CTkEntry(sf, textvariable=self._pass2_var, width=400,
                     show="*").pack(anchor="w")

    def _save(self):
        username = self._user_var.get().strip()
        password = self._pass_var.get()
        password2 = self._pass2_var.get()
        role = next((v for d, v in self._ROLES if d == self._role_var.get()), "normal")

        if not self.user:
            if not username:
                messagebox.showwarning("Aviso", "Nome de utilizador é obrigatório.")
                return
            if not password:
                messagebox.showwarning("Aviso", "Palavra-passe é obrigatória.")
                return
            if password != password2:
                messagebox.showwarning("Aviso", "As palavras-passe não coincidem.")
                return
            try:
                db.create_user(username, password, role)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível criar utilizador: {e}")
                return
        else:
            uid = self.user["id"]
            if password and password != password2:
                messagebox.showwarning("Aviso", "As palavras-passe não coincidem.")
                return
            try:
                db.update_user_role(uid, role)
                if password:
                    db.update_user_password(uid, password)
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível guardar: {e}")
                return

        if self.on_save:
            self.on_save()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = ITInventoryApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
