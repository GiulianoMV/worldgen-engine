"""Cells, ticks and geological years are independent prototype units."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WorldConfig:
    width: int = 150
    height: int = 150
    seed: int | None = None
    sea_level: float = 0.35
    num_plates: int = 10
    runoff_fraction: float = 0.4
    river_threshold: float = 0.05
    rainfall_reference: float = 0.008
    mountain_amplitude: float = 0.5
    depression_amplitude: float = 0.15
    detail_amplitude: float = 0.1
    uplift_coefficient: float = 0.0001
    subsidence_coefficient: float = 0.0001
    soil_depth: float = 0.01
    erodibility: float = 0.0001
    deposition_fraction: float = 0.1
    hunger_per_tick: float = 0.04
    thirst_per_tick: float = 0.06
    resource_regrowth_ticks: int = 25

    def __post_init__(self):
        for key in ('width', 'height', 'num_plates', 'resource_regrowth_ticks'):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f'{key} must be a positive integer.')
        for key in ('sea_level', 'runoff_fraction', 'river_threshold', 'rainfall_reference',
                    'mountain_amplitude', 'depression_amplitude', 'detail_amplitude',
                    'uplift_coefficient', 'subsidence_coefficient', 'soil_depth',
                    'erodibility', 'deposition_fraction', 'hunger_per_tick', 'thirst_per_tick'):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{key} must be finite and nonnegative.')
        if self.runoff_fraction > 1 or self.deposition_fraction > 1 or self.river_threshold == 0 or self.rainfall_reference == 0:
            raise ValueError('Invalid hydrology parameters.')
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError('seed must be an integer or None.')
