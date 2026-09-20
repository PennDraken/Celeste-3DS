from PIL import Image

INPUT = "data/gfx.png"
OUTPUT = "data/gfx.bmp"

# PICO-8 palette, in the exact index order expected by the game.
PICO8 = [
    (0x00, 0x00, 0x00),  # 0
    (0x1d, 0x2b, 0x53),  # 1
    (0x7e, 0x25, 0x53),  # 2
    (0x00, 0x87, 0x51),  # 3
    (0xab, 0x52, 0x36),  # 4
    (0x5f, 0x57, 0x4f),  # 5
    (0xc2, 0xc3, 0xc7),  # 6
    (0xff, 0xf1, 0xe8),  # 7
    (0xff, 0x00, 0x4d),  # 8
    (0xff, 0xa3, 0x00),  # 9
    (0xff, 0xec, 0x27),  # 10
    (0x00, 0xe4, 0x36),  # 11
    (0x29, 0xad, 0xff),  # 12
    (0x83, 0x76, 0x9c),  # 13
    (0xff, 0x77, 0xa8),  # 14
    (0xff, 0xcc, 0xaa),  # 15
]

# Alternate palette used by the PNG.
# Each entry maps directly to the corresponding PICO-8 index.
SOURCE_PALETTE = [
    (0x00, 0x00, 0x00),  # -> 0
    (0x22, 0x33, 0x55),  # -> 1
    (0x77, 0x22, 0x55),  # -> 2
    (0x66, 0x55, 0x55),  # -> 5
    (0xaa, 0x55, 0x33),  # -> 4
    (0xff, 0x00, 0x55),  # -> 8
    (0x00, 0xdd, 0x33),  # -> 11
    (0x00, 0x88, 0x55),  # -> 3
    (0xff, 0xaa, 0x00),  # -> 9
    (0xff, 0xee, 0x22),  # -> 10
    (0x88, 0x77, 0x99),  # -> 13
    (0xff, 0x77, 0xaa),  # -> 14
    (0x22, 0xaa, 0xff),  # -> 12
    (0xff, 0xcc, 0xaa),  # -> 15
    (0xbb, 0xbb, 0xcc),  # -> 6
    (0xff, 0xee, 0xee),  # -> 7
]

# Current source-palette index -> PICO-8 index.
SOURCE_TO_PICO8 = [
    0, 1, 2, 5, 4, 8, 11, 3,
    9, 10, 13, 14, 12, 15, 6, 7
]

source_index = {
    color: i for i, color in enumerate(SOURCE_PALETTE)
}

img = Image.open(INPUT).convert("RGB")

out = Image.new("P", img.size)
pixels = out.load()

for y in range(img.height):
    for x in range(img.width):
        rgb = img.getpixel((x, y))

        if rgb not in source_index:
            raise ValueError(
                f"Unexpected color {rgb} at ({x}, {y})"
            )

        src_index = source_index[rgb]
        pixels[x, y] = SOURCE_TO_PICO8[src_index]

# Install exact PICO-8 palette in indices 0-15.
palette = []
for r, g, b in PICO8:
    palette.extend((r, g, b))

# Fill remaining 240 palette entries.
palette.extend([0] * (256 * 3 - len(palette)))

out.putpalette(palette)
out.save(OUTPUT, format="BMP")

print(f"Converted {INPUT} -> {OUTPUT}")
print(f"Size: {img.width}x{img.height}")
print("Palette: PICO-8 indices 0-15")