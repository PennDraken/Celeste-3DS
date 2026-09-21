#!/usr/bin/env python3
"""Tilemap editor for the Celeste 3DS port.

Loads data/gfx.bmp as the tile palette and the tilemap_data array from
tilemap.h, lets you paint tiles, and writes the array back to tilemap.h.

Controls:
  Left click / drag    paint selected tile (brush) or flood fill (bucket)
  Right click / drag   erase (tile 0)
  Ctrl + left click    pick tile under cursor
  Middle drag          pan
  Mouse wheel          zoom (map) / scroll (palette)
  B / G                brush / paint bucket
  Ctrl+Z / Ctrl+Y      undo / redo
  Ctrl+S               save
"""

import os
import re
import sys

import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    sys.exit("Pillow is required: pip install pillow")

ROOT = os.path.dirname(os.path.abspath(__file__))
TILEMAP_H = os.path.join(ROOT, "tilemap.h")
GFX_CANDIDATES = [os.path.join(ROOT, "data", "gfx.bmp"), os.path.join(ROOT, "data", "gfx.png")]

TILE_SIZE = 15
MAP_TILE_WIDTH = 256
MAP_TILE_HEIGHT = 64
ROOM_TILE_STRIDE = 32
ROOM_TILE_COUNT = 16
SHEET_COLUMNS = 16

ZOOM_LEVELS = [1, 2, 3, 4, 6, 8]
PALETTE_ZOOM = 2

TILEMAP_RE = re.compile(
    r"(static\s+unsigned\s+char\s+tilemap_data\s*\[[^\]]*\]\s*=\s*\{)(.*?)(\})",
    re.DOTALL,
)


def load_tilemap(path):
    with open(path, "r") as f:
        text = f.read()
    match = TILEMAP_RE.search(text)
    if not match:
        raise ValueError("could not find tilemap_data array in %s" % path)
    values = [int(v, 0) for v in re.findall(r"0x[0-9a-fA-F]+|\d+", match.group(2))]
    expected = MAP_TILE_WIDTH * MAP_TILE_HEIGHT
    if len(values) != expected:
        raise ValueError("expected %d tiles, found %d" % (expected, len(values)))
    return values


def save_tilemap(path, data):
    with open(path, "r") as f:
        text = f.read()
    match = TILEMAP_RE.search(text)
    if not match:
        raise ValueError("could not find tilemap_data array in %s" % path)
    body = ",".join("0x%02x" % v for v in data)
    text = text[: match.start(2)] + body + text[match.end(2) :]
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


class TileSheet:
    def __init__(self, image):
        self.image = image.convert("RGB")
        self.columns = SHEET_COLUMNS
        self.rows = self.image.height // TILE_SIZE
        self.count = self.columns * self.rows
        self._cache = {}

    def scaled(self, size):
        """Return the whole sheet scaled so each tile is `size` pixels."""
        cached = self._cache.get(size)
        if cached is None:
            cached = self.image.resize(
                (self.columns * size, self.rows * size), Image.NEAREST
            )
            self._cache[size] = cached
        return cached

    def tile_box(self, index, size):
        col = index % self.columns
        row = index // self.columns
        return (col * size, row * size, (col + 1) * size, (row + 1) * size)

    def valid(self, index):
        return 0 <= index < self.count


class MapEditor(tk.Tk):
    def __init__(self, sheet, data):
        super().__init__()
        self.title("Celeste tilemap editor")
        self.geometry("1280x760")

        self.sheet = sheet
        self.data = data
        self.selected = 0
        self.zoom_index = ZOOM_LEVELS.index(2)
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.stroke = None
        self.show_grid = tk.BooleanVar(value=True)
        self.tool = tk.StringVar(value="brush")
        self.fill_room_only = tk.BooleanVar(value=False)
        self._pan_origin = None
        self._map_photo = None
        self._palette_photo = None

        self._build_ui()
        self.after(50, self.redraw_all)

    # ---------------------------------------------------------------- UI

    def _build_ui(self):
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(toolbar, text="Save (Ctrl+S)", command=self.save).pack(side=tk.LEFT, padx=4, pady=4)
        tk.Button(toolbar, text="Reload", command=self.reload).pack(side=tk.LEFT, padx=4)
        tk.Button(toolbar, text="-", width=3, command=lambda: self.zoom(-1)).pack(side=tk.LEFT, padx=(12, 2))
        tk.Button(toolbar, text="+", width=3, command=lambda: self.zoom(1)).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(toolbar, text="Room grid", variable=self.show_grid,
                       command=self.draw_map).pack(side=tk.LEFT, padx=12)
        tk.Radiobutton(toolbar, text="Brush (B)", variable=self.tool, value="brush",
                       command=self.update_status).pack(side=tk.LEFT, padx=(12, 2))
        tk.Radiobutton(toolbar, text="Bucket (G)", variable=self.tool, value="bucket",
                       command=self.update_status).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(toolbar, text="Fill within room",
                       variable=self.fill_room_only).pack(side=tk.LEFT, padx=8)

        body = tk.Frame(self)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = tk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y)
        palette_width = self.sheet.columns * TILE_SIZE * PALETTE_ZOOM
        self.palette_canvas = tk.Canvas(left, width=palette_width, highlightthickness=0,
                                        background="#101018")
        self.palette_canvas.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        self.palette_canvas.bind("<Button-1>", self.on_palette_click)
        self.palette_canvas.bind("<Motion>", self.on_palette_motion)

        tk.Frame(body, width=4, background="#303040").pack(side=tk.LEFT, fill=tk.Y)

        self.map_canvas = tk.Canvas(body, highlightthickness=0, background="#181820")
        self.map_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.map_canvas.bind("<Configure>", lambda e: self.draw_map())
        self.map_canvas.bind("<Button-1>", self.on_paint)
        self.map_canvas.bind("<B1-Motion>", self.on_paint)
        self.map_canvas.bind("<ButtonRelease-1>", self.end_stroke)
        self.map_canvas.bind("<Button-3>", self.on_erase)
        self.map_canvas.bind("<B3-Motion>", self.on_erase)
        self.map_canvas.bind("<ButtonRelease-3>", self.end_stroke)
        self.map_canvas.bind("<Button-2>", self.on_pan_start)
        self.map_canvas.bind("<B2-Motion>", self.on_pan_move)
        self.map_canvas.bind("<Motion>", self.on_map_motion)
        self.map_canvas.bind("<Button-4>", lambda e: self.zoom(1, e))
        self.map_canvas.bind("<Button-5>", lambda e: self.zoom(-1, e))
        self.map_canvas.bind("<MouseWheel>", lambda e: self.zoom(1 if e.delta > 0 else -1, e))

        self.status = tk.Label(self, anchor="w", padx=6)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        self.bind("<b>", lambda e: self.set_tool("brush"))
        self.bind("<g>", lambda e: self.set_tool("bucket"))
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------ drawing

    @property
    def tile_px(self):
        return TILE_SIZE * ZOOM_LEVELS[self.zoom_index]

    def redraw_all(self):
        self.draw_palette()
        self.draw_map()
        self.update_status()

    def draw_palette(self):
        size = TILE_SIZE * PALETTE_ZOOM
        image = self.sheet.scaled(size).copy()
        draw = ImageDraw.Draw(image)
        for col in range(1, self.sheet.columns):
            draw.line([(col * size, 0), (col * size, image.height)], fill=(60, 60, 80))
        for row in range(1, self.sheet.rows):
            draw.line([(0, row * size), (image.width, row * size)], fill=(60, 60, 80))
        if self.sheet.valid(self.selected):
            box = self.sheet.tile_box(self.selected, size)
            draw.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], outline=(255, 80, 80), width=2)
        self._palette_photo = ImageTk.PhotoImage(image)
        self.palette_canvas.delete("all")
        self.palette_canvas.create_image(0, 0, anchor="nw", image=self._palette_photo)
        self.palette_canvas.configure(scrollregion=(0, 0, image.width, image.height))

    def clamp_pan(self):
        px = self.tile_px
        view_w = max(1, self.map_canvas.winfo_width())
        view_h = max(1, self.map_canvas.winfo_height())
        max_x = max(0, MAP_TILE_WIDTH * px - view_w)
        max_y = max(0, MAP_TILE_HEIGHT * px - view_h)
        self.pan_x = min(max(self.pan_x, 0), max_x)
        self.pan_y = min(max(self.pan_y, 0), max_y)

    def draw_map(self):
        view_w = self.map_canvas.winfo_width()
        view_h = self.map_canvas.winfo_height()
        if view_w <= 1 or view_h <= 1:
            return
        self.clamp_pan()
        px = self.tile_px
        sheet = self.sheet.scaled(px)

        ox, oy = int(self.pan_x), int(self.pan_y)
        first_col = ox // px
        first_row = oy // px
        cols = min(view_w // px + 2, MAP_TILE_WIDTH - first_col)
        rows = min(view_h // px + 2, MAP_TILE_HEIGHT - first_row)

        frame = Image.new("RGB", (view_w, view_h), (24, 24, 32))
        for row in range(rows):
            ty = first_row + row
            dy = ty * px - oy
            base = ty * MAP_TILE_WIDTH
            for col in range(cols):
                tx = first_col + col
                tile = self.data[base + tx]
                if tile == 0 or not self.sheet.valid(tile):
                    continue
                frame.paste(sheet.crop(self.sheet.tile_box(tile, px)), (tx * px - ox, dy))

        if self.show_grid.get():
            draw = ImageDraw.Draw(frame)
            room_w = ROOM_TILE_STRIDE * px
            room_h = ROOM_TILE_COUNT * px
            start = (first_col * px - ox) - (first_col % ROOM_TILE_STRIDE) * px
            x = start
            while x < view_w:
                if x >= 0:
                    draw.line([(x, 0), (x, view_h)], fill=(80, 120, 160))
                x += room_w
            start = (first_row * px - oy) - (first_row % ROOM_TILE_COUNT) * px
            y = start
            while y < view_h:
                if y >= 0:
                    draw.line([(0, y), (view_w, y)], fill=(80, 120, 160))
                y += room_h

        self._map_photo = ImageTk.PhotoImage(frame)
        self.map_canvas.delete("all")
        self.map_canvas.create_image(0, 0, anchor="nw", image=self._map_photo)

    # ------------------------------------------------------------- events

    def tile_at_event(self, event):
        px = self.tile_px
        tx = int((event.x + self.pan_x) // px)
        ty = int((event.y + self.pan_y) // px)
        if 0 <= tx < MAP_TILE_WIDTH and 0 <= ty < MAP_TILE_HEIGHT:
            return tx, ty
        return None

    def on_palette_click(self, event):
        size = TILE_SIZE * PALETTE_ZOOM
        index = (event.y // size) * self.sheet.columns + (event.x // size)
        if self.sheet.valid(index):
            self.selected = index
            self.draw_palette()
            self.update_status()

    def on_palette_motion(self, event):
        size = TILE_SIZE * PALETTE_ZOOM
        index = (event.y // size) * self.sheet.columns + (event.x // size)
        if self.sheet.valid(index):
            self.update_status("palette tile %d (0x%02x)" % (index, index))

    def set_tool(self, name):
        self.tool.set(name)
        self.update_status()

    def on_paint(self, event):
        if event.state & 0x0004:  # Ctrl: pick tile
            pos = self.tile_at_event(event)
            if pos:
                self.selected = self.data[pos[0] + pos[1] * MAP_TILE_WIDTH]
                self.draw_palette()
                self.update_status()
            return
        self.apply_tool(event, self.selected)

    def on_erase(self, event):
        self.apply_tool(event, 0)

    def apply_tool(self, event, value):
        if self.tool.get() == "bucket":
            if event.type == tk.EventType.ButtonPress:
                self.flood_fill(event, value)
        else:
            self.put_tile(event, value)

    def flood_fill(self, event, value):
        pos = self.tile_at_event(event)
        if not pos:
            return
        start_x, start_y = pos
        target = self.data[start_x + start_y * MAP_TILE_WIDTH]
        if target == value:
            return
        if self.fill_room_only.get():
            room_x = (start_x // ROOM_TILE_STRIDE) * ROOM_TILE_STRIDE
            room_y = (start_y // ROOM_TILE_COUNT) * ROOM_TILE_COUNT
            bounds = (room_x, room_y, room_x + ROOM_TILE_STRIDE, room_y + ROOM_TILE_COUNT)
        else:
            bounds = (0, 0, MAP_TILE_WIDTH, MAP_TILE_HEIGHT)
        min_x, min_y, max_x, max_y = bounds

        changes = []
        pending = [(start_x, start_y)]
        self.data[start_x + start_y * MAP_TILE_WIDTH] = value
        changes.append((start_x + start_y * MAP_TILE_WIDTH, target))
        while pending:
            x, y = pending.pop()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if not (min_x <= nx < max_x and min_y <= ny < max_y):
                    continue
                index = nx + ny * MAP_TILE_WIDTH
                if self.data[index] != target:
                    continue
                self.data[index] = value
                changes.append((index, target))
                pending.append((nx, ny))

        self.undo_stack.append(changes)
        self.redo_stack.clear()
        self.dirty = True
        self.draw_map()
        self.update_status("filled %d tiles" % len(changes))

    def put_tile(self, event, value):
        pos = self.tile_at_event(event)
        if not pos:
            return
        index = pos[0] + pos[1] * MAP_TILE_WIDTH
        if self.data[index] == value:
            return
        if self.stroke is None:
            self.stroke = []
        self.stroke.append((index, self.data[index]))
        self.data[index] = value
        self.dirty = True
        self.draw_map()
        self.update_status()

    def end_stroke(self, _event=None):
        if self.stroke:
            self.undo_stack.append(self.stroke)
            self.redo_stack.clear()
        self.stroke = None

    def on_pan_start(self, event):
        self._pan_origin = (event.x, event.y, self.pan_x, self.pan_y)

    def on_pan_move(self, event):
        if not self._pan_origin:
            return
        sx, sy, px0, py0 = self._pan_origin
        self.pan_x = px0 - (event.x - sx)
        self.pan_y = py0 - (event.y - sy)
        self.draw_map()

    def on_map_motion(self, event):
        self.update_status()

    def zoom(self, direction, event=None):
        new_index = min(max(self.zoom_index + direction, 0), len(ZOOM_LEVELS) - 1)
        if new_index == self.zoom_index:
            return
        old_px = self.tile_px
        anchor_x = event.x if event else self.map_canvas.winfo_width() / 2
        anchor_y = event.y if event else self.map_canvas.winfo_height() / 2
        map_x = (self.pan_x + anchor_x) / old_px
        map_y = (self.pan_y + anchor_y) / old_px
        self.zoom_index = new_index
        self.pan_x = map_x * self.tile_px - anchor_x
        self.pan_y = map_y * self.tile_px - anchor_y
        self.draw_map()
        self.update_status()

    def undo(self):
        if not self.undo_stack:
            return
        stroke = self.undo_stack.pop()
        redo = [(i, self.data[i]) for i, _ in stroke]
        for index, value in stroke:
            self.data[index] = value
        self.redo_stack.append(redo)
        self.dirty = True
        self.draw_map()

    def redo(self):
        if not self.redo_stack:
            return
        stroke = self.redo_stack.pop()
        undo = [(i, self.data[i]) for i, _ in stroke]
        for index, value in stroke:
            self.data[index] = value
        self.undo_stack.append(undo)
        self.dirty = True
        self.draw_map()

    # -------------------------------------------------------------- files

    def save(self):
        try:
            save_tilemap(TILEMAP_H, self.data)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.dirty = False
        self.update_status("saved to %s" % os.path.basename(TILEMAP_H))

    def reload(self):
        if self.dirty and not messagebox.askokcancel("Reload", "Discard unsaved changes?"):
            return
        try:
            self.data = load_tilemap(TILEMAP_H)
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
            return
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self.redraw_all()

    def on_close(self):
        if self.dirty and not messagebox.askokcancel("Quit", "Discard unsaved changes?"):
            return
        self.destroy()

    def update_status(self, message=None):
        pointer = self.map_canvas.winfo_pointerxy()
        origin = (self.map_canvas.winfo_rootx(), self.map_canvas.winfo_rooty())
        px = self.tile_px
        tx = int((pointer[0] - origin[0] + self.pan_x) // px)
        ty = int((pointer[1] - origin[1] + self.pan_y) // px)
        parts = [self.tool.get(),
                 "tile %d (0x%02x)" % (self.selected, self.selected),
                 "zoom %dx" % ZOOM_LEVELS[self.zoom_index]]
        if 0 <= tx < MAP_TILE_WIDTH and 0 <= ty < MAP_TILE_HEIGHT:
            value = self.data[tx + ty * MAP_TILE_WIDTH]
            parts.append("map %d,%d = 0x%02x" % (tx, ty, value))
            parts.append("room %d,%d" % (tx // ROOM_TILE_STRIDE, ty // ROOM_TILE_COUNT))
        if self.dirty:
            parts.append("*modified*")
        if message:
            parts.append(message)
        self.status.configure(text="   |   ".join(parts))


def main():
    sheet_path = next((p for p in GFX_CANDIDATES if os.path.exists(p)), None)
    if not sheet_path:
        sys.exit("spritesheet not found (looked for %s)" % ", ".join(GFX_CANDIDATES))
    sheet = TileSheet(Image.open(sheet_path))
    data = load_tilemap(TILEMAP_H)
    MapEditor(sheet, data).mainloop()


if __name__ == "__main__":
    main()
