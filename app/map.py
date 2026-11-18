"""Terrain state and procedural generation orchestration."""
import math
import random
import secrets
from dataclasses import replace
from app.config import WorldConfig
from app.tectonics import Tectonics
from app.hydrology import Hydrology
from app.climate import Climate
from app.ecology import Ecology
from app.geology import Geology


class Grid(Hydrology, Climate, Ecology, Geology):
    """Periodic longitude, bounded latitude; values use prototype units."""
    TREE_DENSITIES = {
        'taiga': 0.65,
        'boreal_forest': 0.75,
        'temperate_forest': 0.80,
        'temperate_rainforest': 0.95,
        'tropical_seasonal_forest': 0.65,
        'tropical_rainforest': 0.95,
        'savanna': 0.12,
        'grassland': 0.08,
    }

    def __init__(self, name='World', width=150, height=150, seed=None, config=None):
        self.config = config or WorldConfig(width=width, height=height, seed=seed)
        self.name = name
        self.width, self.height = self.config.width, self.config.height
        self.seed = self.config.seed if self.config.seed is not None else secrets.randbits(32)
        self.config = replace(self.config, seed=self.seed)
        self.sea_level = self.config.sea_level
        self.generate_grid()

    def _noise(self, scale):
        """Smooth noise periodic in x at every octave, normalized to [0, 1]."""
        field = [[0.0] * self.width for _ in range(self.height)]
        for octave, weight in enumerate((1.0, 0.5, 0.25)):
            spacing = max(1.0, scale / 2 ** octave)
            columns = max(1, math.ceil(self.width / spacing))
            rows = math.ceil((self.height - 1) / spacing) + 2
            anchors = [[self.rng.random() for _ in range(columns)] for _ in range(rows)]
            for y in range(self.height):
                iy = int(y / spacing)
                fy = y / spacing - iy
                sy = fy * fy * (3 - 2 * fy)
                for x in range(self.width):
                    # One full period covers the width; the final interval
                    # interpolates back to the first anchor, without duplicating
                    # the first column at the end of the map.
                    gx = x * columns / self.width
                    ix = int(gx)
                    fx = gx - ix
                    next_ix = (ix + 1) % columns
                    sx = fx * fx * (3 - 2 * fx)
                    top = anchors[iy][ix] * (1 - sx) + anchors[iy][next_ix] * sx
                    bottom = anchors[iy + 1][ix] * (1 - sx) + anchors[iy + 1][next_ix] * sx
                    field[y][x] += (top * (1 - sy) + bottom * sy) * weight
        low, high = min(map(min, field)), max(map(max, field))
        if high == low:
            return [[0.5] * self.width for _ in range(self.height)]
        return [[(v - low) / (high - low) for v in row] for row in field]

    def _neighbors(self, x, y):
        """Unique cardinal neighbors, wrapping longitude but never latitude."""
        visited = {(x, y)}
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            nx %= self.width
            if 0 <= ny < self.height and (nx, ny) not in visited:
                visited.add((nx, ny))
                yield nx, ny

    def generate_grid(self):
        """Generate initial layers; never use this to refresh evolved terrain."""
        for name in ('bedrock', 'soil_depth', 'erodibility', 'geological_years', 'exported_sediment'):
            self.__dict__.pop(name, None)
        self.rng = random.Random(self.seed)
        self.generate_elevation()
        self.refresh_environment()
        self.generate_resources()

    def refresh_environment(self):
        """Recompute derived layers without resetting elevation or deposits."""
        self.classify_ocean()
        self.generate_precipitation()
        self.calculate_drainage()
        self.calculate_flow(self.config.runoff_fraction)
        self.generate_lakes_and_rivers(self.config.river_threshold)
        self.calculate_distance_to_water()
        state = self.rng.getstate()
        self.rng.seed(f'{self.seed}:environment')
        self.generate_moisture(self.config.rainfall_reference)
        self.calculate_slopes()
        self.classify_biomes()
        self.place_vegetation()
        self.rng.setstate(state)
        self.terrain_dirty = False

    def generate_elevation(self):
        self.tectonics = Tectonics(
            width=self.width,
            height=self.height,
            num_plates=min(self.config.num_plates, self.width * self.height),
            seed=self.seed,
            generate_fields=False,
        )

        scale = min(self.width, self.height)

        self.tectonics.generate_fields(
            influence_width=max(3.0, scale / 13),
            smoothing_length=max(3.0, scale / 10),
            mountain_amplitude=self.config.mountain_amplitude,
            depression_amplitude=self.config.depression_amplitude,
            uplift_coefficient=self.config.uplift_coefficient,
            subsidence_coefficient=self.config.subsidence_coefficient,
        )
        # Fixed vertical scale: tectonics provides structure, noise adds detail.
        # Do not normalize against each world's extrema after composition.
        initial = self.tectonics.calculate_elevation()
        detail = self._noise(max(2, min(self.width, self.height) / 8))
        detail_amplitude = self.config.detail_amplitude
        self.elevation = [
            [initial[y][x] + detail_amplitude * (detail[y][x] - 0.5)
             for x in range(self.width)] for y in range(self.height)
        ]

