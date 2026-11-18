"""Read-only temperature, elevation and tectonic PNG diagnostics."""

from datetime import datetime
from pathlib import Path

from app.save_img import IMAGE_DIR, LOCAL_TIMEZONE
from app.png import write_png


def _temperature_color(value):
    value = max(0.0, min(1.0, value))
    cold, neutral, hot = (30, 80, 210), (235, 240, 245), (225, 40, 20)
    start, end = (cold, neutral) if value <= 0.5 else (neutral, hot)
    factor = value * 2 if value <= 0.5 else (value - 0.5) * 2
    return tuple(round(a + (b - a) * factor) for a, b in zip(start, end))


def _render(grid, cell_size, color_at):
    pixels = bytearray()
    for y in range(grid.height):
        row = b''.join(bytes(color_at(x, y)) * cell_size for x in range(grid.width))
        pixels.extend(row * cell_size)
    return pixels


def _draw_convergence(grid, pixels, cell_size):
    width, height = grid.width * cell_size, grid.height * cell_size
    for boundary in grid.tectonics.boundaries.values():
        for segment in boundary['segments']:
            if segment['type'] != 'convergent':
                continue
            (ax, ay), (bx, by) = segment['endpoints']
            # Cells are centered on integer world coordinates. Shift half a
            # cell to match image pixels; faces at the seam wrap to column 0.
            x0, y0 = round((ax + 0.5) * cell_size), round((ay + 0.5) * cell_size)
            x1, y1 = round((bx + 0.5) * cell_size), round((by + 0.5) * cell_size)
            steps = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(steps + 1):
                x = round(x0 + (x1 - x0) * i / steps) % width
                y = round(y0 + (y1 - y0) * i / steps)
                if 0 <= y < height:
                    offset = (y * width + x) * 3
                    pixels[offset:offset + 3] = b'\xff\x40\x40'


def save_diagnostic_images(grid, cell_size=4, output_dir=None):
    """Export three views of the same world, without changing its state.

    Temperature uses the current 0..1 index, not degrees Celsius. Grayscale
    elevation has a fixed 0..1 display range; only display colors are clipped.
    """
    if isinstance(cell_size, bool) or not isinstance(cell_size, int) or cell_size <= 0:
        raise ValueError('cell_size must be a positive integer.')
    directory = Path(output_dir).resolve() if output_dir is not None else IMAGE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(LOCAL_TIMEZONE).strftime('%Y%m%d_%H%M%S_%f')
    prefix = f'{timestamp}_{grid.width}x{grid.height}_seed{grid.seed}'
    paths = {layer: directory / f'{prefix}_{layer}.png'
             for layer in ('temperature', 'elevation', 'convergence')}
    width, height = grid.width * cell_size, grid.height * cell_size
    metadata = f'{grid.name} | seed={grid.seed} | sea_level={grid.sea_level}'

    temperature = _render(grid, cell_size, lambda x, y:
                          _temperature_color(grid.get_temperature_index(x, y)))
    write_png(paths['temperature'], temperature, width, height,
               f'{metadata} | temperature index: blue=0 white=0.5 red=1')

    elevation = _render(grid, cell_size, lambda x, y:
                        (round(max(0.0, min(1.0, grid.elevation[y][x])) * 255),) * 3)
    write_png(paths['elevation'], elevation, width, height,
               f'{metadata} | elevation: black=0 white=1; display clipped, not rescaled')
    _draw_convergence(grid, elevation, cell_size)
    write_png(paths['convergence'], elevation, width, height,
               f'{metadata} | grayscale elevation; red=convergent plate boundary')
    return paths
