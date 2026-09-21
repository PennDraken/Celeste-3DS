#!/usr/bin/env python3

from PIL import Image
import sys

PICO8_PALETTE = [
    (0x00, 0x00, 0x00),  # 0 black
    (0x1d, 0x2b, 0x53),  # 1 dark-blue
    (0x7e, 0x25, 0x53),  # 2 dark-purple
    (0x00, 0x87, 0x51),  # 3 dark-green
    (0xab, 0x52, 0x36),  # 4 brown
    (0x5f, 0x57, 0x4f),  # 5 dark-gray
    (0xc2, 0xc3, 0xc7),  # 6 light-gray
    (0xff, 0xf1, 0xe8),  # 7 white
    (0xff, 0x00, 0x4d),  # 8 red
    (0xff, 0xa3, 0x00),  # 9 orange
    (0xff, 0xec, 0x27),  # 10 yellow
    (0x00, 0xe4, 0x36),  # 11 green
    (0x29, 0xad, 0xff),  # 12 blue
    (0x83, 0x76, 0x9c),  # 13 lavender
    (0xff, 0x77, 0xa8),  # 14 pink
    (0xff, 0xcc, 0xaa),  # 15 peach
]


def nearest_color(rgb):
    """Return the nearest PICO-8 palette index."""
    r, g, b = rgb

    best_index = 0
    best_distance = float("inf")

    for i, (pr, pg, pb) in enumerate(PICO8_PALETTE):
        distance = (
            (r - pr) ** 2 +
            (g - pg) ** 2 +
            (b - pb) ** 2
        )

        if distance < best_distance:
            best_distance = distance
            best_index = i

    return best_index


def main():
    filename = "data/map.bmp"

    if len(sys.argv) > 1:
        filename = sys.argv[1]

    print(f"Converting {filename} to PICO-8 palette...")

    image = Image.open(filename).convert("RGB")

    if image.size != (320, 240):
        print(f"Warning: image is {image.width}x{image.height}, expected 320x240")

    # Create an indexed image using palette indices 0-15.
    indexed = Image.new("P", image.size)

    # Build a 256-entry BMP palette. The first 16 entries are PICO-8.
    palette = []

    for color in PICO8_PALETTE:
        palette.extend(color)

    # Fill the remaining 240 entries.
    palette.extend([0, 0, 0] * (256 - 16))

    indexed.putpalette(palette)

    # Convert every pixel to the nearest PICO-8 color.
    src = image.load()
    dst = indexed.load()

    for y in range(image.height):
        for x in range(image.width):
            dst[x, y] = nearest_color(src[x, y])

    # Save back to map.bmp.
    indexed.save(filename, format="BMP")

    print(f"Written {filename}")
    print(f"Size: {image.width}x{image.height}")
    print("Palette: PICO-8 16 colors")


if __name__ == "__main__":
    main()