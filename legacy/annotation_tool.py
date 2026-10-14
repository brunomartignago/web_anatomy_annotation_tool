import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel
from PIL import Image, ImageTk
import json
import copy
import os

possible_values = {
    'Form': ['Typo', 'Image', 'Icon', 'Space'],
    'Function': ['Dropdown', 'Radio button', 'Checkbox', 'Text input', 'Label', 'Text', 'Breadcrumb',
                 'Button', 'Link', 'Ad', 'Tag', 'Heading', 'Illustration'],
    'Component': ['Carousel', 'Card', 'Table', 'Search bar', 'Banner', 'Menu', 'Filter', 'Tab',
                  'List item', 'Blank'],
    'Taxonomy': ['Header', 'Sub-header', 'Footer', 'Column 0', 'Column 1', 'Column 2',
                 'Column 3', 'Column 4', 'Left Panel', 'Right Panel', 'Left Menu', 'Right Menu']
}

class AnnotationApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Image Annotation Tool')
        self.root.option_add("*Font", "Helvetica 10")
        self.root.state('zoomed')

        self.history = []
        self.future = []
        self.selection_rects = []


        self.image = None
        self.display_image = None
        self.zoom = 1.0

        self.photo = None

        self.rubberband_start = None
        self.rubberband_rect_id = None

        self.canvas_frame = tk.Frame(root)
        self.canvas_frame.grid(row=1, column=0, sticky='nsew')

        self.canvas = tk.Canvas(self.canvas_frame, bg='grey')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar_y = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.scrollbar_x = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)

        self.canvas.config(cursor='crosshair')


        self.side_panel = tk.Frame(root, width=int(self.root.winfo_screenwidth() * 0.3), bg='#f9f9f9')
        self.side_panel.grid(row=1, column=1, sticky='ns')

        tk.Label(self.side_panel, text='Selections', font=('Helvetica', 12, 'bold'), bg='#f9f9f9').pack(anchor='w', padx=10, pady=(10, 5))

        self.selection_container = tk.Canvas(self.side_panel, borderwidth=0, bg='#f0f0f0')
        self.selection_frame = tk.Frame(self.selection_container, bg='#f0f0f0')
        self.selection_scrollbar = tk.Scrollbar(self.side_panel, orient="vertical", command=self.selection_container.yview)
        self.selection_container.configure(yscrollcommand=self.selection_scrollbar.set)

        self.selection_scrollbar.pack(side="right", fill="y")
        self.selection_container.pack(fill=tk.BOTH, expand=True, padx=5)
        self.selection_container.create_window((0, 0), window=self.selection_frame, anchor="nw")
        self.selection_frame.bind("<Configure>", lambda e: self.selection_container.configure(scrollregion=self.selection_container.bbox("all")))
        self.selection_container.bind_all("<MouseWheel>", self.on_selection_mouse_wheel)

        # Create TOP PANEL (header bar)
        self.top_panel = tk.Frame(root, bg='#f0f0f0')
        self.top_panel.grid(row=0, column=0, columnspan=2, sticky='ew', padx=5, pady=5)

        # First row: ACTION BUTTONS
        self.action_frame = tk.Frame(self.top_panel, bg='#f0f0f0')
        self.action_frame.pack(fill=tk.X)

        self.load_image_button = tk.Button(self.action_frame, text='Load Image', command=self.load_image, bg='#007acc', fg='white')
        self.load_image_button.pack(side='left', padx=5)

        self.load_button = tk.Button(self.action_frame, text='Load Annotations', command=self.load_annotations, bg='#17a2b8', fg='white')
        self.load_button.pack(side='left', padx=5)


        self.save_button = tk.Button(self.action_frame, text='Save Annotations', command=self.save_annotations, bg='#28a745', fg='white')
        self.save_button.pack(side='left', padx=5)

        self.set_attr_button = tk.Button(self.action_frame, text='Set Attributes', command=self.set_attributes, bg='#6c757d', fg='white')
        self.set_attr_button.pack(side='left', padx=5)

        self.set_partial_attr_button = tk.Button(self.action_frame, text='Set Selected Attributes', command=self.set_selected_attributes, bg='#6c757d', fg='white')
        self.set_partial_attr_button.pack(side='left', padx=5)

        self.del_button = tk.Button(self.action_frame, text='Delete Selection', command=self.delete_selection, bg='#dc3545', fg='white')
        self.del_button.pack(side='left', padx=5)

        self.zoom_in_button = tk.Button(self.action_frame, text='+ Zoom In', command=lambda: self.zoom_image(1.1))
        self.zoom_in_button.pack(side='left', padx=5)

        self.zoom_out_button = tk.Button(self.action_frame, text='- Zoom Out', command=lambda: self.zoom_image(0.9))
        self.zoom_out_button.pack(side='left', padx=5)

        self.undo_button = tk.Button(self.action_frame, text='Undo', command=self.undo)
        self.undo_button.pack(side='left', padx=5)

        self.redo_button = tk.Button(self.action_frame, text='Redo', command=self.redo)
        self.redo_button.pack(side='left', padx=5)

        # Second row: FILTERS (horizontal)
        self.filter_frame_top = tk.Frame(self.top_panel, bg='#f0f0f0')
        self.filter_frame_top.pack(fill=tk.X, pady=(5, 0))

        self.filter_vars = {}
        options = ['Unannotated', 'Form', 'Function', 'Component', 'Taxonomy']

        for opt in options:
            var = tk.IntVar()
            chk = tk.Checkbutton(self.filter_frame_top, text=opt, variable=var, command=self.apply_filter, bg='#f0f0f0')
            chk.pack(side='left', padx=5)
            self.filter_vars[opt] = var

        reset_btn = tk.Button(self.filter_frame_top, text='Show All', command=self.reset_filter)
        reset_btn.pack(side='left', padx=5)

        self.counter_label = tk.Label(self.filter_frame_top, text='Visible selections: 0', bg='#f0f0f0')
        self.counter_label.pack(side='left', padx=10)

        # Configure grid weights → so Canvas expands, side panel stays fixed
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)

        # Mode toggle
        self.mode = 'draw'

        self.toggle_button = tk.Button(
            self.side_panel,
            text="Mode: Draw Selections",
            command=self.toggle_mode,
            bg='#e0e0e0',
            relief='raised'
        )
        self.toggle_button.pack(fill='x', padx=10, pady=(10, 5))

        self.selection_vars = []
        self.selections = []

        self.history.append((copy.deepcopy(self.selections), []))

        self.counter_label.pack(anchor='w', pady=(5, 0))

        self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
        self.canvas.bind('<MouseWheel>', self.on_mouse_wheel)
        self.canvas.bind('<Shift-MouseWheel>', self.on_shift_mouse_wheel)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)

        self.start_x = None
        self.start_y = None

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[('Image Files', '*.png;*.jpg;*.jpeg;*.bmp;*.gif')])
        if file_path:
            try:
                self.image_path = file_path  # <<< Add this line!
                self.image = Image.open(file_path).convert('RGBA')
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                img_ratio = self.image.width / self.image.height
                screen_ratio = screen_width / screen_height

                if img_ratio > screen_ratio:
                    new_width = screen_width
                    new_height = int(screen_width / img_ratio)
                else:
                    new_height = screen_height
                    new_width = int(screen_height * img_ratio)

                self.zoom = new_width / self.image.width
                self.display_image = self.image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(self.display_image)
                self.canvas.config(scrollregion=(0, 0, new_width, new_height))
                self.redraw_canvas()
                self.apply_filter()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to load image: {e}')


    def load_annotations(self):
        file_path = filedialog.askopenfilename(filetypes=[('JSON Files', '*.json')])
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                loaded_data = json.load(f)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load JSON: {e}')
            return
        
        if 'selections' in loaded_data:
            self.selections = loaded_data['selections']
        else:
            self.selections = loaded_data

        for sel in self.selections:
            if 'expanded' not in sel:
                sel['expanded'] = False

        # Clear selection_vars and UI list
        self.selection_vars = []
        for widget in self.selection_frame.winfo_children():
            widget.destroy()

        # Rebuild selection_vars and side list
        for i, sel in enumerate(self.selections):
            var = tk.IntVar()

            outer_frame = tk.LabelFrame(self.selection_frame, relief=tk.GROOVE, bd=2)
            outer_frame.pack(fill='x', pady=2)

            title_frame = tk.Frame(outer_frame)
            title_frame.pack(fill='x')

            chevron = tk.Label(title_frame, text='▶', width=2)
            chevron.pack(side='left')

            marker_lbl = tk.Label(title_frame, text='○', fg='red', width=2)
            marker_lbl.pack(side='left')

            def on_check(idx=i):
                self.redraw_canvas()

            chk = tk.Checkbutton(title_frame, text=f'Selection {i+1} ({sel.get("Area", 0):.0f})', variable=var, command=lambda idx=i: on_check(idx))
            chk.pack(side='left', anchor='w')

            detail = tk.Frame(outer_frame)
            detail.pack(fill='x', anchor='w')

            form_lbl = tk.Label(detail, text=f'Form: {sel.get("Form", "")}')
            form_lbl.pack(anchor='w')
            form_lbl.bind('<Double-Button-1>', lambda e, i=i: self.edit_attribute(i, 'Form', form_lbl))

            func_lbl = tk.Label(detail, text=f'Function: {sel.get("Function", "")}')
            func_lbl.pack(anchor='w')
            func_lbl.bind('<Double-Button-1>', lambda e, i=i: self.edit_attribute(i, 'Function', func_lbl))

            comp_lbl = tk.Label(detail, text=f'Component: {sel.get("Component", "")}')
            comp_lbl.pack(anchor='w')
            comp_lbl.bind('<Double-Button-1>', lambda e, i=i: self.edit_attribute(i, 'Component', comp_lbl))

            tax_lbl = tk.Label(detail, text=f'Taxonomy: {sel.get("Taxonomy", "")}')
            tax_lbl.pack(anchor='w')
            tax_lbl.bind('<Double-Button-1>', lambda e, i=i: self.edit_attribute(i, 'Taxonomy', tax_lbl))

            def toggle(idx=i):
                sel = self.selections[idx]
                sel['expanded'] = not sel['expanded']
                chevron.config(text='▼' if sel['expanded'] else '▶')
                if sel['expanded']:
                    form_lbl.config(text=f'Form: {sel.get("Form", "")}')
                    func_lbl.config(text=f'Function: {sel.get("Function", "")}')
                    comp_lbl.config(text=f'Component: {sel.get("Component", "")}')
                    tax_lbl.config(text=f'Taxonomy: {sel.get("Taxonomy", "")}')
                    detail.pack(fill='x', anchor='w')
                else:
                    detail.pack_forget()

            chevron.bind('<Button-1>', lambda e, i=i: toggle(i))

            self.selection_vars.append((var, chk, outer_frame, chevron, marker_lbl, detail, form_lbl, func_lbl, comp_lbl, tax_lbl))
            self.update_marker(i)

        # FINAL: refresh canvas and side list
        self.redraw_canvas()
        self.apply_filter()          # <---- CRITICAL: refresh side list!
        self.update_all_highlights()




    
    def zoom_image(self, factor):
        self.zoom *= factor
        if self.image:
            size = (int(self.image.width * self.zoom), int(self.image.height * self.zoom))
            self.display_image = self.image.resize(size, Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(self.display_image)
            self.canvas.config(scrollregion=(0, 0, size[0], size[1]))
            self.redraw_canvas()

    def on_mouse_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def on_selection_mouse_wheel(self, event):
        self.selection_container.yview_scroll(int(-1*(event.delta/120)), "units")

    def on_shift_mouse_wheel(self, event):
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), 'units')

    def redraw_canvas(self):
        self.canvas.delete('all')
        self.selection_rects.clear()

        if self.photo:
            self.canvas.create_image(0, 0, anchor='nw', image=self.photo)

        for idx, sel in enumerate(self.selections):
            coords = sel.get('coords')
            if coords is None or len(coords) != 4:
                print(f"[WARNING] Skipping selection {idx}: invalid coords → {coords}")
                continue

            scaled_coords = tuple(c * self.zoom for c in coords)
            rect_id = self.canvas.create_rectangle(scaled_coords, outline='red', width=2)
            self.selection_rects.append(rect_id)
        
        self.update_all_highlights()



    def update_all_highlights(self):
        for idx in range(len(self.selections)):
            # Only proceed if index is valid for selection_vars and selection_rects
            if idx >= len(self.selection_vars):
                continue
            if idx >= len(self.selection_rects):
                continue

            sel = self.selections[idx]
            is_complete = all(sel[attr] != '' for attr in ['Form', 'Function', 'Component', 'Taxonomy'])

            if is_complete:
                color = 'green'
            elif self.selection_vars[idx][0].get() == 1:
                color = 'blue'
            else:
                color = 'red'

            self.canvas.itemconfig(self.selection_rects[idx], outline=color)

            self.selection_vars[idx][4].config(
                text='●' if is_complete else '○',
                fg='green' if is_complete else 'red'
            )





    def on_mouse_down(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

    def on_mouse_drag(self, event):
        self.redraw_canvas()
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.create_rectangle(self.start_x, self.start_y, cur_x, cur_y, outline='blue')

    def on_mouse_up(self, event):
        self.history.append((self.selections.copy(), self.selection_vars.copy()))
        self.future.clear()
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        coords = (self.start_x, self.start_y, end_x, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        area = width * height

        selection = {
            'coords': (coords[0]/self.zoom, coords[1]/self.zoom, coords[2]/self.zoom, coords[3]/self.zoom),
            'Form': '',
            'Function': '',
            'Component': '',
            'Taxonomy': '',
            'Area': area,
            'expanded': False
        }

        self.selections.append(selection)
        var = tk.IntVar()

        outer_frame = tk.LabelFrame(self.selection_frame, relief=tk.GROOVE, bd=2)
        outer_frame.pack(fill='x', pady=2)

        title_frame = tk.Frame(outer_frame)
        title_frame.pack(fill='x')

        chevron = tk.Label(title_frame, text='▶', width=2)
        chevron.pack(side='left')

        marker_lbl = tk.Label(title_frame, text='○', fg='red', width=2)  # NEW marker label
        marker_lbl.pack(side='left')

        def on_check():
            self.redraw_canvas()

        chk = tk.Checkbutton(title_frame, text=f'Selection {len(self.selections)} ({area})', variable=var, command=on_check)
        chk.pack(side='left', anchor='w')

        detail = tk.Frame(outer_frame)
        detail.pack(fill='x', anchor='w')

        form_lbl = tk.Label(detail, text=f'Form: {selection["Form"]}')
        form_lbl.pack(anchor='w')
        form_lbl.bind('<Double-Button-1>', lambda e, i=len(self.selections)-1: self.edit_attribute(i, 'Form', form_lbl))

        func_lbl = tk.Label(detail, text=f'Function: {selection["Function"]}')
        func_lbl.pack(anchor='w')
        func_lbl.bind('<Double-Button-1>', lambda e, i=len(self.selections)-1: self.edit_attribute(i, 'Function', func_lbl))

        comp_lbl = tk.Label(detail, text=f'Component: {selection["Component"]}')
        comp_lbl.pack(anchor='w')
        comp_lbl.bind('<Double-Button-1>', lambda e, i=len(self.selections)-1: self.edit_attribute(i, 'Component', comp_lbl))

        tax_lbl = tk.Label(detail, text=f'Taxonomy: {selection["Taxonomy"]}')
        tax_lbl.pack(anchor='w')
        tax_lbl.bind('<Double-Button-1>', lambda e, i=len(self.selections)-1: self.edit_attribute(i, 'Taxonomy', tax_lbl))

        def toggle(idx=len(self.selections)-1):
            sel = self.selections[idx]
            sel['expanded'] = not sel['expanded']
            chevron.config(text='▼' if sel['expanded'] else '▶')
            if sel['expanded']:
                form_lbl.config(text=f'Form: {sel["Form"]}')
                func_lbl.config(text=f'Function: {sel["Function"]}')
                comp_lbl.config(text=f'Component: {sel["Component"]}')
                tax_lbl.config(text=f'Taxonomy: {sel["Taxonomy"]}')
                detail.pack(fill='x', anchor='w')
            else:
                detail.pack_forget()

        chevron.bind('<Button-1>', lambda e, i=len(self.selections)-1: toggle(i))

        # Store marker_lbl at index 4
        self.selection_vars.append((var, chk, outer_frame, chevron, marker_lbl, detail, form_lbl, func_lbl, comp_lbl, tax_lbl))

        self.update_marker(len(self.selections)-1)  # NEW: update marker on creation
        self.redraw_canvas()


    def set_attributes(self):
        self.history.append((self.selections.copy(), self.selection_vars.copy()))
        self.future.clear()

        indices = [i for i, (var, *_rest) in enumerate(self.selection_vars) if var.get() == 1]
        if not indices:
            messagebox.showinfo('Info', 'No selections selected.')
            return

        new_attributes = {}
        for attr in possible_values:
            value = self.select_from_buttons(attr, possible_values[attr])
            if value:
                new_attributes[attr] = value

        for i in indices:
            sel = self.selections[i]
            for attr, value in new_attributes.items():
                if attr in sel:
                    sel[attr] = value

            # Uncheck the selection after updating attributes
            self.selection_vars[i][0].set(0)

            # Update all UI widgets for this selection
            self.update_selection_display(i)

        self.redraw_canvas()

    def set_selected_attributes(self):
        self.history.append((self.selections.copy(), self.selection_vars.copy()))
        self.future.clear()

        indices = [i for i, (var, *_rest) in enumerate(self.selection_vars) if var.get() == 1]
        if not indices:
            messagebox.showinfo('Info', 'No selections selected.')
            return

        # Step 1: Show dialog to select which attributes to update
        dialog = Toplevel(self.root)
        dialog.title("Select Attributes to Update")
        dialog.resizable(False, False)

        selected_attrs = {attr: tk.IntVar() for attr in possible_values}

        content_frame = tk.Frame(dialog, padx=20, pady=20)
        content_frame.pack()

        tk.Label(content_frame, text="Select which attributes to update:", font=('Helvetica', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        for attr in possible_values:
            chk = tk.Checkbutton(content_frame, text=attr, variable=selected_attrs[attr])
            chk.pack(anchor='w')

        button_frame = tk.Frame(content_frame)
        button_frame.pack(pady=(10, 0))

        def confirm():
            dialog.destroy()
            # Step 2: For selected attrs, show value selection and apply
            new_attributes = {}
            for attr, var in selected_attrs.items():
                if var.get() == 1:
                    value = self.select_from_buttons(attr, possible_values[attr])
                    if value:
                        new_attributes[attr] = value

            # Apply to selections
            for i in indices:
                sel = self.selections[i]
                for attr, value in new_attributes.items():
                    if attr in sel:
                        sel[attr] = value

                # Uncheck the selection after updating attributes
                self.selection_vars[i][0].set(0)
                self.update_selection_display(i)

            self.redraw_canvas()

        def cancel():
            dialog.destroy()

        tk.Button(button_frame, text='Confirm', command=confirm, width=15, bg='#28a745', fg='white').pack(side='left', padx=5)
        tk.Button(button_frame, text='Cancel', command=cancel, width=15).pack(side='left', padx=5)

        # Center dialog on screen
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        window_width = dialog.winfo_width()
        window_height = dialog.winfo_height()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        dialog.geometry(f'{window_width}x{window_height}+{x}+{y}')

        dialog.grab_set()
        dialog.wait_window()


    def update_selection_display(self, index):
        sel = self.selections[index]
        _, _, _, chevron, marker_lbl, detail_frame, form_lbl, func_lbl, comp_lbl, tax_lbl = self.selection_vars[index]

        form_lbl.config(text=f'Form: {sel.get("Form", "")}')
        func_lbl.config(text=f'Function: {sel.get("Function", "")}')
        comp_lbl.config(text=f'Component: {sel.get("Component", "")}')
        tax_lbl.config(text=f'Taxonomy: {sel.get("Taxonomy", "")}')
        
        self.update_marker(index)

        # ALSO re-apply visibility of detail_frame here
        is_complete = all(sel[attr] != '' for attr in ['Form', 'Function', 'Component', 'Taxonomy'])
        if is_complete:
            sel['expanded'] = False
            chevron.config(text='▶')
            detail_frame.pack_forget()
        else:
            if sel['expanded']:
                chevron.config(text='▼')
                detail_frame.pack(fill='x', anchor='w')
            else:
                chevron.config(text='▶')
                detail_frame.pack_forget()


    def toggle_mode(self):
        if self.mode == 'draw':
            self.mode = 'select'
            self.toggle_button.config(text="Mode: Select Selections")
            self.canvas.config(cursor='hand2')

            # Unbind draw mode handlers
            self.canvas.unbind('<ButtonPress-1>')
            self.canvas.unbind('<B1-Motion>')
            self.canvas.unbind('<ButtonRelease-1>')

            # Bind select mode handler
            self.canvas.bind('<ButtonPress-1>', self.on_select_mouse_down)
            self.canvas.bind('<B1-Motion>', self.on_select_mouse_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_select_mouse_up)

        else:
            self.mode = 'draw'
            self.toggle_button.config(text="Mode: Draw Selections")
            self.canvas.config(cursor='crosshair')

            # Unbind select mode handler
            self.canvas.unbind('<ButtonPress-1>')
            self.canvas.unbind('<B1-Motion>')
            self.canvas.unbind('<ButtonRelease-1>')

            # Bind draw mode handlers
            self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
            self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
            self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)


    def update_marker(self, index):
        # Check if index is valid for all lists you access
        if index < 0 or index >= len(self.selections):
            return
        if index >= len(self.selection_vars):
            return
        if index >= len(self.selection_rects):
            return

        sel = self.selections[index]
        marker_lbl = self.selection_vars[index][4]  # marker_lbl is at index 4
        chevron = self.selection_vars[index][3]     # chevron is at index 3
        detail_frame = self.selection_vars[index][5]  # detail frame

        is_complete = all(sel[attr] != '' for attr in ['Form', 'Function', 'Component', 'Taxonomy'])

        if is_complete:
            # Update marker color
            marker_lbl.config(text='●', fg='green')

            # Update canvas rectangle color
            self.canvas.itemconfig(self.selection_rects[index], outline='green', width=2)

            # Collapse listing if not already collapsed
            if sel['expanded']:
                sel['expanded'] = False
                chevron.config(text='▶')
                detail_frame.pack_forget()

        else:
            # Update marker color
            marker_lbl.config(text='○', fg='red')

            # Update canvas rectangle color
            self.canvas.itemconfig(self.selection_rects[index], outline='red', width=2)




    def select_from_buttons(self, attr, options):
        dialog = Toplevel(self.root)
        dialog.title(f"Select {attr}")

        # Optional: make the dialog not resizable (looks cleaner)
        dialog.resizable(False, False)

        # Set a consistent font
        dialog.option_add("*Font", "Helvetica 10")

        # Add some padding around the content
        content_frame = tk.Frame(dialog, padx=20, pady=20)
        content_frame.pack()

        selected = {'value': None}

        def select(option):
            selected['value'] = option
            dialog.destroy()

        # Label at the top
        tk.Label(content_frame, text=f"Select a value for '{attr}':", font=('Helvetica', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        # Buttons
        for option in options:
            tk.Button(content_frame, text=option, width=30, bg='#007acc', fg='white',
                    activebackground='#005f99', activeforeground='white',
                    command=lambda opt=option: select(opt)).pack(fill='x', pady=5)

        # Optional: Cancel button at the bottom
        tk.Button(content_frame, text='Cancel', width=30,
                command=dialog.destroy).pack(fill='x', pady=(10, 0))

        # Force geometry update so we can center it
        dialog.update_idletasks()

        # Centering logic
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        window_width = dialog.winfo_width()
        window_height = dialog.winfo_height()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        dialog.geometry(f'{window_width}x{window_height}+{x}+{y}')

        # Modal behavior
        dialog.grab_set()
        dialog.wait_window()

        return selected['value']

    def on_canvas_click(self, event):
        if self.mode == 'draw':
            # Start drawing a new rectangle
            self.start_x = self.canvas.canvasx(event.x)
            self.start_y = self.canvas.canvasy(event.y)
            self.current_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline='red', width=2
            )
        elif self.mode == 'select':
            # Try selecting an existing rectangle
            selection_index = self.find_selection_at_point(event.x, event.y)
            if selection_index is not None:
                self.highlight_rectangle(selection_index)
                self.selection_vars[selection_index][0].set(True)

    def find_selection_at_point(self, x, y):
        x_canvas = self.canvas.canvasx(x)
        y_canvas = self.canvas.canvasy(y)

        for i, sel in enumerate(self.selections):
            x0, y0, x1, y1 = [c * self.zoom for c in sel['coords']]
            if x0 <= x_canvas <= x1 and y0 <= y_canvas <= y1:
                return i
        return None
    
    def highlight_rectangle(self, selection_index):
        # Set this rectangle's checkbox ON
        self.selection_vars[selection_index][0].set(1)
        # Update all highlights according to current checkboxes
        self.update_all_highlights()

    def on_select_mouse_down(self, event):
        self.rubberband_start = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.rubberband_rect_id = self.canvas.create_rectangle(
            self.rubberband_start[0], self.rubberband_start[1],
            self.rubberband_start[0], self.rubberband_start[1],
            outline='blue', dash=(2, 2)
        )

    def on_select_mouse_drag(self, event):
        if self.rubberband_rect_id is not None:
            cur_x = self.canvas.canvasx(event.x)
            cur_y = self.canvas.canvasy(event.y)
            self.canvas.coords(
                self.rubberband_rect_id,
                self.rubberband_start[0], self.rubberband_start[1],
                cur_x, cur_y
            )

    def on_select_mouse_up(self, event):
        if self.rubberband_rect_id is not None:
            # Final rubberband area
            x0, y0 = self.rubberband_start
            x1 = self.canvas.canvasx(event.x)
            y1 = self.canvas.canvasy(event.y)

            x_min, x_max = sorted([x0, x1])
            y_min, y_max = sorted([y0, y1])

            # Check intersection with selections
            for i, sel in enumerate(self.selections):
                sx0, sy0, sx1, sy1 = [c * self.zoom for c in sel['coords']]
                # Simple rectangle intersection test
                if (sx1 >= x_min and sx0 <= x_max and
                    sy1 >= y_min and sy0 <= y_max):
                    self.selection_vars[i][0].set(1)  # Select it

            # Clean up rubberband rectangle
            self.canvas.delete(self.rubberband_rect_id)
            self.rubberband_rect_id = None
            self.rubberband_start = None

            # Update highlights
            self.update_all_highlights()


    def undo(self):
        if self.history:
            action = self.history.pop()
            self.future.append((self.selections.copy(), self.selection_vars.copy()))
            self.selections, self.selection_vars = action
            for _, _, frame, *_ in self.selection_vars:
                frame.pack_forget()
                frame.pack(fill='x', pady=2)
            self.redraw_canvas()

    def redo(self):
        if self.future:
            action = self.future.pop()
            self.history.append((self.selections.copy(), self.selection_vars.copy()))
            self.selections, self.selection_vars = action
            for _, _, frame, *_ in self.selection_vars:
                frame.pack_forget()
                frame.pack(fill='x', pady=2)
            self.redraw_canvas()

    def delete_selection(self):
        self.history.append((self.selections.copy(), self.selection_vars.copy()))
        self.future.clear()
        for i in reversed(range(len(self.selection_vars))):
            var, chk, frame, *_ = self.selection_vars[i]
            if var.get() == 1:
                frame.destroy()
                del self.selection_vars[i]
                del self.selections[i]
        self.redraw_canvas()

    def save_annotations(self):
        json_folder = r'C:/Users/bruno/Documents/Annotation tool/json'
        os.makedirs(json_folder, exist_ok=True)
        image_filename = os.path.basename(self.image_path)  # e.g. "myimage.png"
        json_filename = os.path.splitext(image_filename)[0] + '.json'
        save_path = os.path.join(json_folder, json_filename)
        with open(save_path, 'w') as f:
            json.dump({'selections': self.selections}, f, indent=2)
        messagebox.showinfo('Saved', f'Annotations saved to {save_path}')


    def apply_filter(self):
        active_filters = [key for key, var in self.filter_vars.items() if var.get() == 1]
        visible_count = 0

        for i, (var, chk, frame, *_rest) in enumerate(self.selection_vars):
            sel = self.selections[i]
            show = False

            if not active_filters:
                show = True
            else:
                for f in active_filters:
                    if f == 'Unannotated':
                        if all(sel[attr] == '' for attr in ['Form', 'Function', 'Component', 'Taxonomy']):
                            show = True
                            break
                    elif sel[f] != '':
                        show = True
                        break

            if show:
                frame.pack(fill='x', pady=2)
                visible_count += 1
            else:
                frame.pack_forget()

        self.counter_label.config(text=f'Visible selections: {visible_count}')

    def reset_filter(self):
        for var in self.filter_vars.values():
            var.set(0)
        self.apply_filter()

    def edit_attribute(self, index, attr, label_widget):
        sel = self.selections[index]
        new_val = self.select_from_buttons(attr, possible_values[attr])
        if new_val:
            sel[attr] = new_val
            label_widget.config(text=f'{attr}: {new_val}')
            self.update_marker(index)
            self.update_all_highlights()


root = tk.Tk()
app = AnnotationApp(root)
root.mainloop()