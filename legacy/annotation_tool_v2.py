"""
Annotation Tool v2 — Keyboard-first rewrite
============================================

KEYBOARD SHORTCUTS
------------------
  D            → Draw mode
  S            → Select mode
  Escape       → Deselect all / cancel draw

  Tab          → Cycle to next unannotated box
  Shift+Tab    → Cycle to previous unannotated box
  Enter        → Confirm label panel selection

  Delete / X   → Delete selected annotations

  Ctrl+Z       → Undo
  Ctrl+Shift+Z → Redo
  Ctrl+S       → Save annotations
  Ctrl+O       → Load image
  Ctrl+Shift+O → Load annotations

  +/-          → Zoom in / out
  Ctrl+0       → Reset zoom

  In label panel (Form / Function / Component / Taxonomy):
    1–9        → Quick-pick nth option in focused group
    Arrow keys → Move between options

  Shift+click  → Add/remove box from selection (multi-select)
  Drag (select mode) → Rubber-band multi-select
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import json, copy, os, math, time

# ── Taxonomy ────────────────────────────────────────────────────────────────
ATTRIBUTES = {
    'Form':      ['Typo', 'Image', 'Icon', 'Space'],
    'Function':  ['Dropdown', 'Radio button', 'Checkbox', 'Text input', 'Label',
                  'Text', 'Breadcrumb', 'Button', 'Link', 'Ad', 'Tag', 'Heading', 'Illustration'],
    'Component': ['Carousel', 'Card', 'Table', 'Search bar', 'Banner', 'Menu',
                  'Filter', 'Tab', 'List item', 'Blank'],
    'Taxonomy':  ['Header', 'Sub-header', 'Footer', 'Column 0', 'Column 1', 'Column 2',
                  'Column 3', 'Column 4', 'Left Panel', 'Right Panel', 'Left Menu', 'Right Menu'],
}
ATTR_ORDER = ['Form', 'Function', 'Component', 'Taxonomy']

# ── Palette ──────────────────────────────────────────────────────────────────
C = {
    'bg':          '#0e0f11',
    'surface':     '#16181c',
    'surface2':    '#1e2127',
    'border':      '#2a2d35',
    'border_hi':   '#3d4250',
    'text':        '#d4d8e2',
    'text_dim':    '#6b7280',
    'text_bright': '#f0f2f7',
    'accent':      '#4f8ef7',
    'accent_dim':  '#1e3a6e',
    'red':         '#f05252',
    'red_dim':     '#4a1515',
    'green':       '#34d399',
    'green_dim':   '#0d3325',
    'yellow':      '#fbbf24',
    'yellow_dim':  '#3d2d08',
}

BOX_COLORS = {
    'empty':    C['red'],
    'partial':  C['yellow'],
    'complete': C['green'],
    'selected': C['accent'],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_complete(sel):
    return all(sel.get(a, '') != '' for a in ATTR_ORDER)

def completion_color(sel):
    filled = sum(1 for a in ATTR_ORDER if sel.get(a, '') != '')
    if filled == 0: return BOX_COLORS['empty']
    if filled == len(ATTR_ORDER): return BOX_COLORS['complete']
    return BOX_COLORS['partial']


# ── Main App ──────────────────────────────────────────────────────────────────
class AnnotationApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Annotation Tool  v2')
        self.root.configure(bg=C['bg'])
        self.root.state('zoomed')

        # ── State ────────────────────────────────────────────────────────────
        self.image         = None
        self.photo         = None
        self.image_path    = None
        self.zoom          = 1.0
        self.selections    = []       # list of dicts with coords + attributes
        self.selected_ids  = set()   # indices of currently selected boxes
        self.rect_ids      = []       # canvas rect item ids (parallel to selections)
        self.label_ids     = []       # canvas label item ids (parallel to selections)
        self.history       = []
        self.future        = []
        self.mode          = 'draw'   # 'draw' | 'select'
        self._draw_start   = None
        self._draw_rect_id = None
        self._rubberband   = None
        self._rubberband_start = None
        self._last_autosave = 0
        self._focused_attr = 0        # index into ATTR_ORDER for keyboard nav
        self._pan_start    = None     # (x, y) screen coords when middle-drag began

        self._build_ui()
        self._bind_global_keys()
        self._push_history()

    # ── UI Construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # col 0 = left label panel, col 1 = canvas (expands), col 2 = right list panel
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=0)

        self._build_toolbar()
        self._build_left_panel()
        self._build_canvas()
        self._build_right_panel()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=C['surface'], height=48,
                       highlightthickness=1, highlightbackground=C['border'])
        bar.grid(row=0, column=0, columnspan=3, sticky='ew')
        bar.grid_propagate(False)

        def btn(parent, text, cmd, accent=False, danger=False, shortcut=None):
            bg  = C['accent'] if accent else (C['red'] if danger else C['surface2'])
            fg  = C['text_bright'] if (accent or danger) else C['text']
            tip = f'  {text}' + (f'  [{shortcut}]' if shortcut else '')
            b = tk.Button(parent, text=tip, command=cmd,
                          bg=bg, fg=fg, relief='flat',
                          activebackground=C['border_hi'], activeforeground=C['text_bright'],
                          font=('Helvetica', 9), padx=10, pady=6, cursor='hand2')
            b.pack(side='left', padx=2, pady=6)
            return b

        btn(bar, 'Load Image',       self.load_image,       shortcut='Ctrl+O')
        btn(bar, 'Load Annotations', self.load_annotations, shortcut='Ctrl+Shift+O')
        btn(bar, 'Save',             self.save_annotations, accent=True, shortcut='Ctrl+S')

        tk.Frame(bar, bg=C['border'], width=1).pack(side='left', fill='y', padx=8, pady=8)

        self.mode_btn = tk.Button(bar, text='  ✏  Draw  [D]',
                                  command=self.toggle_mode,
                                  bg=C['accent'], fg=C['text_bright'], relief='flat',
                                  activebackground=C['border_hi'], activeforeground=C['text_bright'],
                                  font=('Helvetica', 9, 'bold'), padx=12, pady=6, cursor='hand2')
        self.mode_btn.pack(side='left', padx=2, pady=6)

        tk.Frame(bar, bg=C['border'], width=1).pack(side='left', fill='y', padx=8, pady=8)

        btn(bar, 'Undo',   self.undo, shortcut='Ctrl+Z')
        btn(bar, 'Redo',   self.redo, shortcut='Ctrl+⇧Z')
        btn(bar, 'Delete', self.delete_selected, danger=True, shortcut='Del')

        tk.Frame(bar, bg=C['border'], width=1).pack(side='left', fill='y', padx=8, pady=8)

        btn(bar, '+ Zoom', lambda: self.zoom_image(1.15), shortcut='+')
        btn(bar, '− Zoom', lambda: self.zoom_image(0.87), shortcut='-')

        # Zoom label
        self.zoom_label = tk.Label(bar, text='100%', bg=C['surface'],
                                   fg=C['text_dim'], font=('Helvetica', 9))
        self.zoom_label.pack(side='left', padx=6)

        # Right-side: autosave indicator
        self.autosave_label = tk.Label(bar, text='● saved', bg=C['surface'],
                                       fg=C['green'], font=('Helvetica', 8))
        self.autosave_label.pack(side='right', padx=12)

    def _build_canvas(self):
        frame = tk.Frame(self.root, bg=C['bg'])
        frame.grid(row=1, column=1, sticky='nsew')
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(frame, bg='#1a1a1a', highlightthickness=0, cursor='crosshair')
        self.canvas.grid(row=0, column=0, sticky='nsew')

        sy = tk.Scrollbar(frame, orient='vertical',   command=self.canvas.yview,
                          bg=C['border'], troughcolor=C['surface'],
                          activebackground=C['border_hi'], highlightthickness=0,
                          relief='flat', bd=0)
        sx = tk.Scrollbar(frame, orient='horizontal', command=self.canvas.xview,
                          bg=C['border'], troughcolor=C['surface'],
                          activebackground=C['border_hi'], highlightthickness=0,
                          relief='flat', bd=0)
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        # Canvas bindings
        self.canvas.bind('<ButtonPress-1>',      self._on_canvas_press)
        self.canvas.bind('<B1-Motion>',          self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>',    self._on_canvas_release)
        self.canvas.bind('<MouseWheel>',         self._on_mousewheel)
        self.canvas.bind('<Shift-MouseWheel>',   self._on_shift_mousewheel)
        self.canvas.bind('<Control-MouseWheel>', self._on_ctrl_mousewheel)
        # Linux scroll wheel
        self.canvas.bind('<Button-4>',           self._on_linux_scroll_up)
        self.canvas.bind('<Button-5>',           self._on_linux_scroll_down)
        self.canvas.bind('<Control-Button-4>',   lambda e: self.zoom_image(1.1))
        self.canvas.bind('<Control-Button-5>',   lambda e: self.zoom_image(0.9))
        # Middle-click pan (Button-2 = wheel click on Windows/Linux/Mac)
        self.canvas.bind('<ButtonPress-2>',      self._on_pan_start)
        self.canvas.bind('<B2-Motion>',          self._on_pan_drag)
        self.canvas.bind('<ButtonRelease-2>',    self._on_pan_end)

    def _build_left_panel(self):
        """Left panel: label controls for Form / Function / Component / Taxonomy."""
        lp = tk.Frame(self.root, bg=C['surface'], width=300,
                      highlightthickness=1, highlightbackground=C['border'])
        lp.grid(row=1, column=0, sticky='nsew')
        lp.grid_propagate(False)
        lp.grid_rowconfigure(1, weight=1)
        lp.grid_columnconfigure(0, weight=1)

        # Header
        header = tk.Frame(lp, bg=C['surface2'])
        header.grid(row=0, column=0, sticky='ew')
        self.label_panel_title = tk.Label(header, text='LABEL PANEL',
                                          bg=C['surface2'], fg=C['text_dim'],
                                          font=('Helvetica', 8, 'bold'), padx=12, pady=7)
        self.label_panel_title.pack(side='left')
        tk.Label(header, text='1–9 quick-pick', bg=C['surface2'],
                 fg=C['text_dim'], font=('Helvetica', 7), padx=8).pack(side='right')

        # Scrollable area for attribute groups
        scroll_outer = tk.Frame(lp, bg=C['surface'])
        scroll_outer.grid(row=1, column=0, sticky='nsew')
        scroll_outer.grid_rowconfigure(0, weight=1)
        scroll_outer.grid_columnconfigure(0, weight=1)

        lp_canvas = tk.Canvas(scroll_outer, bg=C['surface'], highlightthickness=0)
        lp_scroll = tk.Scrollbar(scroll_outer, orient='vertical', command=lp_canvas.yview,
                                 bg=C['border'], troughcolor=C['surface'],
                                 activebackground=C['border_hi'], highlightthickness=0,
                                 relief='flat', bd=0)
        lp_canvas.configure(yscrollcommand=lp_scroll.set)
        lp_scroll.grid(row=0, column=1, sticky='ns')
        lp_canvas.grid(row=0, column=0, sticky='nsew')

        self.label_panel = tk.Frame(lp_canvas, bg=C['surface'])
        lp_win = lp_canvas.create_window((0, 0), window=self.label_panel, anchor='nw')

        def _lp_configure(e):
            lp_canvas.configure(scrollregion=lp_canvas.bbox('all'))
            lp_canvas.itemconfig(lp_win, width=lp_canvas.winfo_width())
        self.label_panel.bind('<Configure>', _lp_configure)
        lp_canvas.bind('<Configure>', lambda e: lp_canvas.itemconfig(lp_win, width=e.width))
        lp_canvas.bind('<MouseWheel>', lambda e:
            lp_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        self._build_label_panel()

    def _build_right_panel(self):
        """Right panel: selections list + progress dashboard."""
        rp = tk.Frame(self.root, bg=C['surface'], width=280,
                      highlightthickness=1, highlightbackground=C['border'])
        rp.grid(row=1, column=2, sticky='nsew')
        rp.grid_propagate(False)
        rp.grid_rowconfigure(2, weight=1)
        rp.grid_columnconfigure(0, weight=1)

        # Header row
        list_header = tk.Frame(rp, bg=C['surface2'])
        list_header.grid(row=0, column=0, sticky='ew')
        tk.Label(list_header, text='SELECTIONS', bg=C['surface2'],
                 fg=C['text_dim'], font=('Helvetica', 8, 'bold'),
                 padx=12, pady=7).pack(side='left')
        self.sel_count_label = tk.Label(list_header, text='0', bg=C['surface2'],
                                        fg=C['accent'], font=('Helvetica', 8, 'bold'))
        self.sel_count_label.pack(side='right', padx=12)

        # Filter chips
        filter_frame = tk.Frame(rp, bg=C['surface'])
        filter_frame.grid(row=1, column=0, sticky='ew', padx=8, pady=4)
        self.filter_var = tk.StringVar(value='all')
        for val, label in [('all','All'),('empty','Empty'),('partial','Partial'),('complete','Done')]:
            rb = tk.Radiobutton(filter_frame, text=label, variable=self.filter_var, value=val,
                                command=self._refresh_list,
                                bg=C['surface'], fg=C['text_dim'], selectcolor=C['surface2'],
                                activebackground=C['surface'], activeforeground=C['text'],
                                font=('Helvetica', 8), relief='flat', indicatoron=0,
                                padx=6, pady=2)
            rb.pack(side='left', padx=1)

        # Scrollable selections list
        list_outer = tk.Frame(rp, bg=C['surface'])
        list_outer.grid(row=2, column=0, sticky='nsew')
        list_outer.grid_rowconfigure(0, weight=1)
        list_outer.grid_columnconfigure(0, weight=1)

        self.list_canvas = tk.Canvas(list_outer, bg=C['surface'], highlightthickness=0)
        list_scroll = tk.Scrollbar(list_outer, orient='vertical', command=self.list_canvas.yview,
                                   bg=C['border'], troughcolor=C['surface'],
                                   activebackground=C['border_hi'], highlightthickness=0,
                                   relief='flat', bd=0)
        self.list_canvas.configure(yscrollcommand=list_scroll.set)
        list_scroll.grid(row=0, column=1, sticky='ns')
        self.list_canvas.grid(row=0, column=0, sticky='nsew')

        self.list_frame = tk.Frame(self.list_canvas, bg=C['surface'])
        self.list_frame_id = self.list_canvas.create_window((0,0), window=self.list_frame, anchor='nw')
        self.list_frame.bind('<Configure>', lambda e: (
            self.list_canvas.configure(scrollregion=self.list_canvas.bbox('all')),
            self.list_canvas.itemconfig(self.list_frame_id, width=self.list_canvas.winfo_width())
        ))
        self.list_canvas.bind('<Configure>', lambda e:
            self.list_canvas.itemconfig(self.list_frame_id, width=e.width))
        self.list_canvas.bind('<MouseWheel>', lambda e:
            self.list_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # Progress dashboard pinned at bottom
        self._build_progress_dashboard(rp)

    def _build_label_panel(self):
        """Inline label panel — shows attribute buttons without any popup."""
        for w in self.label_panel.winfo_children():
            w.destroy()

        self.attr_frames    = {}
        self.attr_btn_vars  = {}

        for attr in ATTR_ORDER:
            outer = tk.Frame(self.label_panel, bg=C['surface'], pady=0)
            outer.pack(fill='x', padx=0)

            head = tk.Frame(outer, bg=C['surface2'])
            head.pack(fill='x')
            tk.Label(head, text=attr.upper(), bg=C['surface2'],
                     fg=C['text_dim'], font=('Helvetica', 7, 'bold'),
                     padx=12, pady=3).pack(side='left')

            # Current value label
            val_lbl = tk.Label(head, text='—', bg=C['surface2'],
                               fg=C['accent'], font=('Helvetica', 7, 'bold'), padx=8)
            val_lbl.pack(side='right')

            btn_frame = tk.Frame(outer, bg=C['surface'], padx=8, pady=4)
            btn_frame.pack(fill='x')

            btns = []
            COLS = 3  # buttons per row
            for idx, opt in enumerate(ATTRIBUTES[attr]):
                num = str(idx + 1) if idx < 9 else ''
                display = f'{num}· {opt}' if num else opt
                row_i = idx // COLS
                col_i = idx % COLS
                b = tk.Button(btn_frame, text=display,
                              bg=C['surface2'], fg=C['text_dim'],
                              relief='flat', font=('Helvetica', 8),
                              padx=4, pady=4, cursor='hand2',
                              anchor='w',
                              activebackground=C['accent_dim'],
                              activeforeground=C['text_bright'],
                              command=lambda a=attr, o=opt: self._set_attr_from_panel(a, o))
                b.grid(in_=btn_frame, row=row_i, column=col_i,
                       sticky='ew', padx=2, pady=1)
                btns.append((opt, b, val_lbl))
            # Make all columns equal width and expandable
            for c in range(COLS):
                btn_frame.grid_columnconfigure(c, weight=1)

            self.attr_frames[attr]   = outer
            self.attr_btn_vars[attr] = btns   # list of (opt, button_widget, val_label)

    def _build_progress_dashboard(self, parent):
        dash = tk.Frame(parent, bg=C['surface2'],
                        highlightthickness=1, highlightbackground=C['border'])
        dash.grid(row=3, column=0, sticky='ew', padx=0, pady=0)

        tk.Label(dash, text='PROGRESS', bg=C['surface2'],
                 fg=C['text_dim'], font=('Helvetica', 7, 'bold'),
                 padx=12, pady=5).pack(anchor='w')

        self.progress_bars = {}
        self.progress_labels = {}

        for attr in ATTR_ORDER:
            row = tk.Frame(dash, bg=C['surface2'])
            row.pack(fill='x', padx=10, pady=2)

            tk.Label(row, text=attr, bg=C['surface2'], fg=C['text_dim'],
                     font=('Helvetica', 7), width=10, anchor='w').pack(side='left')

            bar_bg = tk.Frame(row, bg=C['border'], height=6)
            bar_bg.pack(side='left', fill='x', expand=True, padx=4)
            bar_bg.pack_propagate(False)

            bar_fill = tk.Frame(bar_bg, bg=C['accent'], height=6, width=0)
            bar_fill.place(x=0, y=0, relheight=1, width=0)

            pct_lbl = tk.Label(row, text='0%', bg=C['surface2'],
                               fg=C['text_dim'], font=('Helvetica', 7), width=4)
            pct_lbl.pack(side='left')

            self.progress_bars[attr]   = (bar_bg, bar_fill)
            self.progress_labels[attr] = pct_lbl

        # Overall summary row
        sumrow = tk.Frame(dash, bg=C['surface2'])
        sumrow.pack(fill='x', padx=10, pady=(4, 8))
        self.summary_label = tk.Label(sumrow, text='0 / 0 complete',
                                      bg=C['surface2'], fg=C['text'],
                                      font=('Helvetica', 8, 'bold'))
        self.summary_label.pack(side='left')

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C['surface2'], height=24,
                       highlightthickness=1, highlightbackground=C['border'])
        bar.grid(row=2, column=0, columnspan=3, sticky='ew')
        bar.grid_propagate(False)

        self.status_label = tk.Label(bar, text='Ready  —  D: draw  S: select  Tab: next unannotated  Ctrl+S: save',
                                     bg=C['surface2'], fg=C['text_dim'], font=('Helvetica', 8), padx=10)
        self.status_label.pack(side='left', fill='y')

        self.coord_label = tk.Label(bar, text='', bg=C['surface2'],
                                    fg=C['text_dim'], font=('Helvetica', 8), padx=10)
        self.coord_label.pack(side='right', fill='y')

        self.canvas.bind('<Motion>', self._on_mouse_move)

    # ── Global Key Bindings ───────────────────────────────────────────────────
    def _bind_global_keys(self):
        r = self.root
        r.bind('<d>',               lambda e: self._set_mode('draw'))
        r.bind('<D>',               lambda e: self._set_mode('draw'))
        r.bind('<s>',               lambda e: self._set_mode('select'))
        r.bind('<S>',               lambda e: self._set_mode('select'))
        r.bind('<Escape>',          lambda e: self._deselect_all())
        r.bind('<Control-z>',       lambda e: self.undo())
        r.bind('<Control-Z>',       lambda e: self.redo())
        r.bind('<Control-s>',       lambda e: self.save_annotations())
        r.bind('<Control-o>',       lambda e: self.load_image())
        r.bind('<Control-O>',       lambda e: self.load_annotations())
        r.bind('<Delete>',          lambda e: self.delete_selected())
        r.bind('<x>',               lambda e: self.delete_selected())
        r.bind('<plus>',            lambda e: self.zoom_image(1.15))
        r.bind('<equal>',           lambda e: self.zoom_image(1.15))
        r.bind('<minus>',           lambda e: self.zoom_image(0.87))
        r.bind('<Control-0>',       lambda e: self._reset_zoom())
        r.bind('<Tab>',             lambda e: (self._next_unannotated(1),  'break'))
        r.bind('<Shift-Tab>',       lambda e: (self._next_unannotated(-1), 'break'))

        # Number keys → quick-pick in focused attribute group
        for n in range(1, 10):
            r.bind(str(n), lambda e, n=n: self._quickpick(n))

    # ── Mode ──────────────────────────────────────────────────────────────────
    def _set_mode(self, mode):
        self.mode = mode
        if mode == 'draw':
            self.canvas.config(cursor='crosshair')
            self.mode_btn.config(text='  ✏  Draw  [D]', bg=C['accent'])
            self.status_label.config(text='Draw mode — click and drag to create annotation boxes')
        else:
            self.canvas.config(cursor='hand2')
            self.mode_btn.config(text='  ↖  Select  [S]', bg=C['yellow'])
            self.status_label.config(text='Select mode — click a box or rubber-band drag. Shift+click to multi-select')

    def toggle_mode(self):
        self._set_mode('select' if self.mode == 'draw' else 'draw')

    # ── Canvas Events ─────────────────────────────────────────────────────────
    def _on_canvas_press(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.mode == 'draw':
            self._draw_start = (cx, cy)
            self._draw_rect_id = self.canvas.create_rectangle(
                cx, cy, cx, cy, outline=C['accent'], width=2, dash=(4, 3))

        elif self.mode == 'select':
            hit = self._hit_test(cx, cy)
            if hit is not None:
                shift = (event.state & 0x0001)
                if shift:
                    if hit in self.selected_ids:
                        self.selected_ids.discard(hit)
                    else:
                        self.selected_ids.add(hit)
                else:
                    if hit not in self.selected_ids:
                        self.selected_ids = {hit}
                    # else: keep multi selection, allow drag in future
                self._refresh_canvas()
                self._update_label_panel_for_selection()
            else:
                # Start rubber-band
                self._rubberband_start = (cx, cy)
                self._rubberband = self.canvas.create_rectangle(
                    cx, cy, cx, cy, outline=C['accent'], width=1, dash=(4,3))
                if not (event.state & 0x0001):
                    self.selected_ids.clear()
                    self._refresh_canvas()

    def _on_canvas_drag(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.mode == 'draw' and self._draw_start:
            self.canvas.coords(self._draw_rect_id,
                               self._draw_start[0], self._draw_start[1], cx, cy)

        elif self.mode == 'select' and self._rubberband is not None:
            self.canvas.coords(self._rubberband,
                               self._rubberband_start[0], self._rubberband_start[1], cx, cy)

    def _on_canvas_release(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.mode == 'draw' and self._draw_start:
            x0, y0 = self._draw_start
            x1, y1 = cx, cy
            self.canvas.delete(self._draw_rect_id)
            self._draw_rect_id = None
            self._draw_start   = None

            if abs(x1 - x0) > 4 and abs(y1 - y0) > 4:
                self._push_history()
                # Normalize coords
                nx0, nx1 = sorted([x0 / self.zoom, x1 / self.zoom])
                ny0, ny1 = sorted([y0 / self.zoom, y1 / self.zoom])
                w, h = abs(x1-x0), abs(y1-y0)
                sel = {
                    'coords': (nx0, ny0, nx1, ny1),
                    'Form': '', 'Function': '', 'Component': '', 'Taxonomy': '',
                    'Area': round(w * h / (self.zoom ** 2), 1),
                }
                self.selections.append(sel)
                new_idx = len(self.selections) - 1
                self.selected_ids = {new_idx}
                self._refresh_canvas()
                self._refresh_list()
                self._update_label_panel_for_selection()
                self._update_progress()
                self._autosave()

        elif self.mode == 'select' and self._rubberband is not None:
            x0, y0 = self._rubberband_start
            x1, y1 = cx, cy
            self.canvas.delete(self._rubberband)
            self._rubberband       = None
            self._rubberband_start = None

            xmin, xmax = sorted([x0, x1])
            ymin, ymax = sorted([y0, y1])

            for i, sel in enumerate(self.selections):
                sx0, sy0, sx1, sy1 = [c * self.zoom for c in sel['coords']]
                if sx1 >= xmin and sx0 <= xmax and sy1 >= ymin and sy0 <= ymax:
                    self.selected_ids.add(i)

            self._refresh_canvas()
            self._update_label_panel_for_selection()

    def _on_mousewheel(self, event):
        # Only scroll if Ctrl is NOT held
        if event.state & 0x0004:
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _on_ctrl_mousewheel(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_image(factor)

    def _on_linux_scroll_up(self, event):
        if event.state & 0x0004:
            self.zoom_image(1.1)
        else:
            self.canvas.yview_scroll(-1, 'units')

    def _on_linux_scroll_down(self, event):
        if event.state & 0x0004:
            self.zoom_image(0.9)
        else:
            self.canvas.yview_scroll(1, 'units')

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)
        self.canvas.config(cursor='fleur')   # four-arrow "grab" cursor

    def _on_pan_drag(self, event):
        if self._pan_start is None:
            return
        dx = event.x - self._pan_start[0]
        dy = event.y - self._pan_start[1]
        self._pan_start = (event.x, event.y)
        # xview/yview work in fractions of total scrollregion
        sr = self.canvas.cget('scrollregion').split() if self.canvas.cget('scrollregion') else None
        if not sr or len(sr) < 4:
            return
        total_w = float(sr[2]) - float(sr[0])
        total_h = float(sr[3]) - float(sr[1])
        if total_w > 0:
            self.canvas.xview_moveto(self.canvas.xview()[0] - dx / total_w)
        if total_h > 0:
            self.canvas.yview_moveto(self.canvas.yview()[0] - dy / total_h)

    def _on_pan_end(self, event):
        self._pan_start = None
        # Restore cursor based on current mode
        self.canvas.config(cursor='crosshair' if self.mode == 'draw' else 'hand2')

    def _on_mouse_move(self, event):
        if self.image:
            cx = self.canvas.canvasx(event.x) / self.zoom
            cy = self.canvas.canvasy(event.y) / self.zoom
            self.coord_label.config(text=f'x:{int(cx)}  y:{int(cy)}')

    # ── Hit Test ──────────────────────────────────────────────────────────────
    def _hit_test(self, cx, cy):
        """Return index of topmost box at canvas point (cx, cy), or None."""
        result = None
        smallest = float('inf')
        for i, sel in enumerate(self.selections):
            x0, y0, x1, y1 = [c * self.zoom for c in sel['coords']]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                area = (x1-x0) * (y1-y0)
                if area < smallest:
                    smallest = area
                    result = i
        return result

    # ── Canvas Rendering ──────────────────────────────────────────────────────
    def _refresh_canvas(self):
        self.canvas.delete('boxes')
        self.rect_ids  = []
        self.label_ids = []

        if self.photo:
            self.canvas.create_image(0, 0, anchor='nw', image=self.photo, tags='img')

        for i, sel in enumerate(self.selections):
            x0, y0, x1, y1 = [c * self.zoom for c in sel['coords']]

            if i in self.selected_ids:
                color = BOX_COLORS['selected']
                width = 2
            else:
                color = completion_color(sel)
                width = 1

            rid = self.canvas.create_rectangle(x0, y0, x1, y1,
                                               outline=color, width=width, tags='boxes')
            # Mini index label on box
            lid = self.canvas.create_text(x0+4, y0+3, text=str(i+1), anchor='nw',
                                          fill=color, font=('Helvetica', 7, 'bold'), tags='boxes')
            self.rect_ids.append(rid)
            self.label_ids.append(lid)

        self.canvas.tag_lower('img', 'boxes')
        self.sel_count_label.config(text=str(len(self.selections)))

    # ── Sidebar: Selection List ───────────────────────────────────────────────
    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        flt = self.filter_var.get()
        visible = 0

        for i, sel in enumerate(self.selections):
            filled = sum(1 for a in ATTR_ORDER if sel.get(a,'') != '')
            if flt == 'empty'    and filled != 0:            continue
            if flt == 'partial'  and (filled == 0 or filled == len(ATTR_ORDER)): continue
            if flt == 'complete' and filled != len(ATTR_ORDER): continue

            visible += 1
            is_sel   = i in self.selected_ids
            color    = completion_color(sel)
            bg       = C['accent_dim'] if is_sel else C['surface']
            bg_head  = C['accent_dim'] if is_sel else C['surface2']

            item = tk.Frame(self.list_frame, bg=bg,
                            highlightthickness=1,
                            highlightbackground=C['accent'] if is_sel else C['border'])
            item.pack(fill='x', padx=4, pady=2)

            head = tk.Frame(item, bg=bg_head)
            head.pack(fill='x')

            # Color dot
            tk.Label(head, text='●', bg=bg_head, fg=color,
                     font=('Helvetica', 9), padx=4).pack(side='left')

            lbl_text = f'#{i+1}  —  {sel.get("Area",0):.0f}px²'
            lbl = tk.Label(head, text=lbl_text, bg=bg_head, fg=C['text'],
                           font=('Helvetica', 8, 'bold'), pady=4, cursor='hand2')
            lbl.pack(side='left')
            lbl.bind('<Button-1>', lambda e, idx=i: self._select_item(idx, e))

            # Attribute chips
            chips = tk.Frame(item, bg=bg)
            chips.pack(fill='x', padx=6, pady=3)
            for attr in ATTR_ORDER:
                val = sel.get(attr, '')
                chip_bg  = C['green_dim']  if val else C['red_dim']
                chip_fg  = C['green']      if val else C['red']
                chip_txt = f'{attr[0]}:{val}' if val else f'{attr[0]}:—'
                tk.Label(chips, text=chip_txt, bg=chip_bg, fg=chip_fg,
                         font=('Helvetica', 7), padx=4, pady=1).pack(side='left', padx=1)

        self.sel_count_label.config(text=str(len(self.selections)))

    def _select_item(self, idx, event):
        if event.state & 0x0001:   # Shift
            if idx in self.selected_ids:
                self.selected_ids.discard(idx)
            else:
                self.selected_ids.add(idx)
        else:
            self.selected_ids = {idx}
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()
        # Scroll canvas to show box
        self._scroll_to(idx)

    def _scroll_to(self, idx):
        if not self.image or idx >= len(self.selections):
            return
        sel = self.selections[idx]
        x0, y0, x1, y1 = [c * self.zoom for c in sel['coords']]
        cx = (x0 + x1) / 2
        cy = (y0 + y1) / 2
        sw = int(self.image.width  * self.zoom)
        sh = int(self.image.height * self.zoom)
        if sw > 0:
            self.canvas.xview_moveto(max(0, (cx - 200) / sw))
        if sh > 0:
            self.canvas.yview_moveto(max(0, (cy - 200) / sh))

    # ── Label Panel Logic ─────────────────────────────────────────────────────
    def _update_label_panel_for_selection(self):
        """Highlight current values in the label panel based on selection."""
        if not self.selected_ids:
            # Clear highlights
            for attr, btns in self.attr_btn_vars.items():
                for opt, b, val_lbl in btns:
                    b.config(bg=C['surface2'], fg=C['text_dim'])
                val_lbl.config(text='—')
            title = f'LABEL PANEL  —  {len(self.selected_ids)} selected' if self.selected_ids else 'LABEL PANEL'
            self.label_panel_title.config(text=title)
            return

        # For mixed selection, show common values
        indices = list(self.selected_ids)
        title   = f'LABEL  —  {len(indices)} box{"es" if len(indices)>1 else ""} selected'
        self.label_panel_title.config(text=title)

        for attr in ATTR_ORDER:
            vals  = [self.selections[i].get(attr, '') for i in indices]
            common = vals[0] if len(set(vals)) == 1 else None
            btns  = self.attr_btn_vars[attr]

            for opt, b, val_lbl in btns:
                if common == opt:
                    b.config(bg=C['accent'], fg=C['text_bright'])
                else:
                    b.config(bg=C['surface2'], fg=C['text_dim'])

            # Update val label (first entry in the list — they all share the same val_lbl ref)
            if btns:
                _, _, val_lbl = btns[0]
                val_lbl.config(text=common if common else ('mixed' if len(set(vals))>1 and any(vals) else '—'))

    def _set_attr_from_panel(self, attr, value):
        """Apply an attribute value to all selected boxes."""
        if not self.selected_ids:
            return
        self._push_history()
        for i in self.selected_ids:
            self.selections[i][attr] = value
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()
        self._update_progress()
        self._autosave()

    def _quickpick(self, n):
        """Number key quick-pick: pick nth option for the focused attribute group."""
        if not self.selected_ids:
            return
        # Cycle through attrs in order; focused_attr tracks which group is "active"
        attr    = ATTR_ORDER[self._focused_attr % len(ATTR_ORDER)]
        options = ATTRIBUTES[attr]
        if n <= len(options):
            self._set_attr_from_panel(attr, options[n-1])
            # Auto-advance focus to next attr
            self._focused_attr = (self._focused_attr + 1) % len(ATTR_ORDER)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _next_unannotated(self, direction=1):
        if not self.selections:
            return
        if not self.selected_ids:
            start = -1 if direction == 1 else len(self.selections)
        else:
            start = max(self.selected_ids) if direction == 1 else min(self.selected_ids)

        n = len(self.selections)
        for step in range(1, n + 1):
            idx = (start + direction * step) % n
            if not is_complete(self.selections[idx]):
                self.selected_ids = {idx}
                self._focused_attr = 0
                self._refresh_canvas()
                self._refresh_list()
                self._update_label_panel_for_selection()
                self._scroll_to(idx)
                return

    def _deselect_all(self):
        self.selected_ids.clear()
        self._focused_attr = 0
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()

    # ── Progress Dashboard ────────────────────────────────────────────────────
    def _update_progress(self):
        n = len(self.selections)
        if n == 0:
            for attr in ATTR_ORDER:
                bg, fill = self.progress_bars[attr]
                fill.place(width=0)
                self.progress_labels[attr].config(text='0%')
            self.summary_label.config(text='0 / 0 complete')
            return

        complete_count = sum(1 for s in self.selections if is_complete(s))
        self.summary_label.config(text=f'{complete_count} / {n} complete')

        for attr in ATTR_ORDER:
            filled = sum(1 for s in self.selections if s.get(attr, '') != '')
            pct    = filled / n
            bg, fill = self.progress_bars[attr]
            # Update after geometry is settled
            self.root.update_idletasks()
            bar_w = bg.winfo_width()
            fill.place(x=0, y=0, relheight=1, width=int(bar_w * pct))
            col = C['green'] if pct == 1.0 else (C['yellow'] if pct > 0 else C['red'])
            fill.config(bg=col)
            self.progress_labels[attr].config(text=f'{int(pct*100)}%')

    # ── Zoom ──────────────────────────────────────────────────────────────────
    def zoom_image(self, factor):
        if not self.image:
            return
        self.zoom = max(0.05, min(10.0, self.zoom * factor))
        w = int(self.image.width  * self.zoom)
        h = int(self.image.height * self.zoom)
        self.canvas.config(scrollregion=(0, 0, w, h))
        resized = self.image.resize((w, h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized)
        self._refresh_canvas()
        self.zoom_label.config(text=f'{int(self.zoom*100)}%')

    def _reset_zoom(self):
        if not self.image:
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        ratio = min(sw / self.image.width, sh / self.image.height, 1.0)
        self.zoom = ratio
        self.zoom_image(1.0)

    # ── File Operations ───────────────────────────────────────────────────────
    def load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[('Image Files', '*.png *.jpg *.jpeg *.bmp *.gif *.webp')])
        if not path:
            return
        try:
            self.image_path = path
            self.image = Image.open(path).convert('RGBA')
            self._reset_zoom()
            self.status_label.config(text=f'Loaded: {os.path.basename(path)}')
            # Check for autosave
            as_path = self._autosave_path()
            if as_path and os.path.exists(as_path):
                if messagebox.askyesno('Autosave found',
                    f'An autosave exists for this image.\nRestore it?'):
                    self._load_json(as_path)
                    return
            self.selections.clear()
            self.selected_ids.clear()
            self._refresh_canvas()
            self._refresh_list()
            self._update_label_panel_for_selection()
            self._update_progress()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load image:\n{e}')

    def load_annotations(self):
        path = filedialog.askopenfilename(filetypes=[('JSON Files', '*.json')])
        if path:
            self._load_json(path)

    def _load_json(self, path):
        try:
            with open(path) as f:
                data = json.load(f)
            sels = data.get('selections', data) if isinstance(data, dict) else data
            self.selections = []
            for s in sels:
                s.setdefault('Form',      '')
                s.setdefault('Function',  '')
                s.setdefault('Component', '')
                s.setdefault('Taxonomy',  '')
                s.setdefault('Area',      0)
                self.selections.append(s)
            self.selected_ids.clear()
            self._refresh_canvas()
            self._refresh_list()
            self._update_label_panel_for_selection()
            self._update_progress()
            self.status_label.config(text=f'Loaded {len(self.selections)} annotations from {os.path.basename(path)}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load JSON:\n{e}')

    def save_annotations(self):
        if not self.image_path:
            messagebox.showwarning('No image', 'Load an image first.')
            return
        default_dir  = os.path.dirname(self.image_path)
        default_name = os.path.splitext(os.path.basename(self.image_path))[0] + '.json'
        path = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=default_name,
            defaultextension='.json',
            filetypes=[('JSON Files', '*.json')])
        if path:
            self._write_json(path)
            self.autosave_label.config(text='● saved', fg=C['green'])
            self.status_label.config(text=f'Saved to {os.path.basename(path)}')

    def _write_json(self, path):
        with open(path, 'w') as f:
            json.dump({'selections': self.selections,
                       'image': os.path.basename(self.image_path) if self.image_path else ''}, f, indent=2)

    def _autosave_path(self):
        if not self.image_path:
            return None
        base = os.path.splitext(self.image_path)[0]
        return base + '.autosave.json'

    def _autosave(self):
        path = self._autosave_path()
        if not path:
            return
        try:
            self._write_json(path)
            self.autosave_label.config(text='● autosaved', fg=C['green'])
        except Exception:
            self.autosave_label.config(text='● save error', fg=C['red'])

    # ── Edit Operations ───────────────────────────────────────────────────────
    def delete_selected(self):
        if not self.selected_ids:
            return
        self._push_history()
        for i in sorted(self.selected_ids, reverse=True):
            self.selections.pop(i)
        self.selected_ids.clear()
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()
        self._update_progress()
        self._autosave()

    def _push_history(self):
        self.history.append(copy.deepcopy(self.selections))
        self.future.clear()
        if len(self.history) > 60:
            self.history.pop(0)

    def undo(self):
        if not self.history:
            return
        self.future.append(copy.deepcopy(self.selections))
        self.selections = self.history.pop()
        self.selected_ids.clear()
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()
        self._update_progress()

    def redo(self):
        if not self.future:
            return
        self.history.append(copy.deepcopy(self.selections))
        self.selections = self.future.pop()
        self.selected_ids.clear()
        self._refresh_canvas()
        self._refresh_list()
        self._update_label_panel_for_selection()
        self._update_progress()


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    root = tk.Tk()
    app  = AnnotationApp(root)
    root.mainloop()
