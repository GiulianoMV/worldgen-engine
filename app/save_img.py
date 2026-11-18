"""Export grid layers as RGB PNGs using only the Python standard library."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.png import write_png
from app.palette import PALETTE


IMAGE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'img'
LOCAL_TIMEZONE = timezone(timedelta(hours=-3))  # America/Sao_Paulo


def save_map_image(grid, cell_size=4, layer='biomes', output_dir=None):
    """Save the current map without regenerating it; return the absolute path.

    Biomes use the RGB palette with centered vegetation markers.
    Moisture ranges from dry brown to wet green; water stays blue.
    """
    if isinstance(cell_size, bool) or not isinstance(cell_size, int) or cell_size <= 0:
        raise ValueError('cell_size must be a positive integer.')
    if layer not in ('biomes', 'moisture'):
        raise ValueError('layer must be biomes or moisture.')

    palette = PALETTE
    pixels = bytearray()
    for y in range(grid.height):
        rows = [bytearray() for _ in range(cell_size)]
        for x in range(grid.width):
            if layer == 'moisture':
                moisture = max(0.0, min(1.0, grid.moisture[y][x]))
                color = palette['water'] if grid.water[y][x] else (
                    round(180 - 150 * moisture), round(110 + 90 * moisture),
                    round(50 + 30 * moisture),
                )
            else:
                color = palette[grid.biomes[y][x]]
            vegetation = grid.vegetation[y][x] if layer == 'biomes' else None
            for py in range(cell_size):
                for px in range(cell_size):
                    marker = (vegetation is not None and (
                        cell_size < 3 or
                        cell_size // 3 <= px < cell_size - cell_size // 3
                        and cell_size // 3 <= py < cell_size - cell_size // 3
                    ))
                    rows[py].extend(palette[vegetation] if marker else color)
        for row in rows:
            pixels.extend(row)

    width, height = grid.width * cell_size, grid.height * cell_size
    metadata = f'{grid.name} | seed={grid.seed} | layer={layer}'
    directory = Path(output_dir).resolve() if output_dir is not None else IMAGE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(LOCAL_TIMEZONE).strftime('%Y%m%d_%H%M%S_%f')
    path = directory / f'{timestamp}_{grid.width}x{grid.height}_seed{grid.seed}_{layer}.png'
    write_png(path, pixels, width, height, metadata)
    return path
