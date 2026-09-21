#!/usr/bin/env python3
"""Click points on an image and export them as a C array of coordinate pairs.

Usage: python3 point_picker.py <image>

Controls:
  Left click        add a point
  Right click       remove the nearest point
  Ctrl+Z            undo last point
  Mouse wheel       zoom
  Middle drag       pan
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    sys.exit("Pillow is required: pip install pillow")


class PointPicker:
    def __init__(self, root, path):
        self.root = root
        self.image = Image.open(path).convert("RGBA")
        self.points = []
        self.scale = 1.0
        self.offset = [0, 0]
        self.photo = None
        self.pan_start = None

        root.title(f"Point Picker - {path}")

        toolbar = tk.Frame(root)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(toolbar, text="Export to clipboard",
                  command=self.export).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(toolbar, text="Clear", command=self.clear).pack(side=tk.LEFT, padx=4)
        tk.Label(toolbar, text="Name:").pack(side=tk.LEFT, padx=(12, 2))
        self.name_var = tk.StringVar(value="points")
        tk.Entry(toolbar, textvariable=self.name_var, width=16).pack(side=tk.LEFT)
        self.status = tk.Label(toolbar, text="0 points")
        self.status.pack(side=tk.RIGHT, padx=8)

        self.canvas = tk.Canvas(root, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_add)
        self.canvas.bind("<Button-3>", self.on_remove)
        self.canvas.bind("<Button-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_move)
        self.canvas.bind("<Button-4>", self.on_wheel)
        self.canvas.bind("<Button-5>", self.on_wheel)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        root.bind("<Control-z>", lambda e: self.undo())

        self.fit()

    # --- coordinate helpers -------------------------------------------------
    def to_image(self, x, y):
        return ((x - self.offset[0]) / self.scale,
                (y - self.offset[1]) / self.scale)

    def to_canvas(self, x, y):
        return (x * self.scale + self.offset[0],
                y * self.scale + self.offset[1])

    def fit(self):
        self.root.update_idletasks()
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        self.scale = min(cw / self.image.width, ch / self.image.height, 8.0)
        if self.scale <= 0:
            self.scale = 1.0
        self.offset = [(cw - self.image.width * self.scale) / 2,
                       (ch - self.image.height * self.scale) / 2]
        self.redraw()

    # --- events -------------------------------------------------------------
    def on_add(self, event):
        ix, iy = self.to_image(event.x, event.y)
        if 0 <= ix < self.image.width and 0 <= iy < self.image.height:
            self.points.append((int(ix), int(iy)))
            self.redraw()

    def on_remove(self, event):
        if not self.points:
            return
        ix, iy = self.to_image(event.x, event.y)
        idx = min(range(len(self.points)),
                  key=lambda i: (self.points[i][0] - ix) ** 2 + (self.points[i][1] - iy) ** 2)
        del self.points[idx]
        self.redraw()

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y, self.offset[0], self.offset[1])

    def on_pan_move(self, event):
        if self.pan_start:
            x0, y0, ox, oy = self.pan_start
            self.offset = [ox + event.x - x0, oy + event.y - y0]
            self.redraw()

    def on_wheel(self, event):
        step = 1.25
        up = getattr(event, "delta", 0) > 0 or event.num == 4
        factor = step if up else 1 / step
        ix, iy = self.to_image(event.x, event.y)
        self.scale = max(0.05, min(self.scale * factor, 64.0))
        self.offset = [event.x - ix * self.scale, event.y - iy * self.scale]
        self.redraw()

    def undo(self):
        if self.points:
            self.points.pop()
            self.redraw()

    def clear(self):
        self.points.clear()
        self.redraw()

    # --- rendering ----------------------------------------------------------
    def redraw(self):
        self.canvas.delete("all")
        w = max(1, int(self.image.width * self.scale))
        h = max(1, int(self.image.height * self.scale))
        resample = Image.NEAREST if self.scale >= 1 else Image.LANCZOS
        self.photo = ImageTk.PhotoImage(self.image.resize((w, h), resample))
        self.canvas.create_image(self.offset[0], self.offset[1],
                                 image=self.photo, anchor=tk.NW)

        prev = None
        for i, (px, py) in enumerate(self.points):
            cx, cy = self.to_canvas(px + 0.5, py + 0.5)
            if prev is not None:
                self.canvas.create_line(prev[0], prev[1], cx, cy, fill="#00ffcc")
            prev = (cx, cy)
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                    outline="#ff2e63", width=2)
            self.canvas.create_text(cx + 8, cy - 8, text=str(i),
                                    fill="#ffffff", anchor=tk.W)
        self.status.config(text=f"{len(self.points)} points")

    # --- export -------------------------------------------------------------
    def format_c(self):
        name = self.name_var.get().strip() or "points"
        lines = [f"static const int {name}[][2] = {{"]
        for x, y in self.points:
            lines.append(f"\t{{{x}, {y}}},")
        lines.append("};")
        lines.append(f"static const int {name}_count = {len(self.points)};")
        return "\n".join(lines)

    def export(self):
        text = self.format_c()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        print(text)
        messagebox.showinfo("Exported",
                            f"{len(self.points)} points copied to clipboard.")


def main():
    root = tk.Tk()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = filedialog.askopenfilename(
            title="Open image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                       ("All files", "*.*")])
        if not path:
            return
    root.geometry("1000x700")
    PointPicker(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
