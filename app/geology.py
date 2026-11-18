"""Terrain geology system; operates on shared grid layers."""
import math


class Geology:
    def initialize_geology(self, soil_depth=0.01, erodibility=0.0001):
        """Normalized prototype units; does not assign real geological rates."""
        if not all(math.isfinite(v) and v >= 0 for v in (soil_depth, erodibility)):
            raise ValueError("Geological parameters must be finite and nonnegative.")
        self.soil_depth = [[soil_depth] * self.width for _ in range(self.height)]
        self.bedrock = [[v - soil_depth for v in row] for row in self.elevation]
        self.erodibility = [[erodibility] * self.width for _ in range(self.height)]
        self.geological_years = 0.0
        self.exported_sediment = 0.0
        self.terrain_dirty = False

    def erode_step(self, years=1.0, deposition_fraction=0.1):
        """Experimental normalized sediment budget, with equal-area cells.

        One bounded step, not a calibrated geological simulation. Lake interiors
        store sediment rather than being carved using artificial fill slopes.
        Derived terrain layers must be refreshed before another step.
        """
        if not math.isfinite(years) or years <= 0:
            raise ValueError("years must be finite and positive.")
        if not math.isfinite(deposition_fraction) or not 0 <= deposition_fraction <= 1:
            raise ValueError("deposition_fraction must be between 0 and 1.")
        if not hasattr(self, 'bedrock'):
            raise RuntimeError("Call initialize_geology() first.")
        if self.terrain_dirty:
            raise RuntimeError("Refresh hydrology and dependent layers before another step.")
        incoming = [[0.0] * self.width for _ in range(self.height)]
        delta = [[0.0] * self.width for _ in range(self.height)]
        exported = eroded = deposited = 0.0
        for x, y in reversed(self.drainage_order):
            load = incoming[y][x]
            target = self.flow_to[y][x]
            if self.ocean[y][x]:
                exported += load
                continue
            if target is None or self.potential_lake_depth[y][x] > 1e-12:
                amount = load
            else:
                amount = load * deposition_fraction
            delta[y][x] += amount
            deposited += amount
            load -= amount
            if target is not None and self.potential_lake_depth[y][x] <= 1e-12:
                nx, ny = target
                drop = max(0.0, self.elevation[y][x] - self.elevation[ny][nx])
                # Limit incision to avoid crossing the receiver in a large step.
                dx = min(abs(nx - x), self.width - abs(nx - x))
                step = math.hypot(dx, ny - y)
                removal = min(self.erodibility[y][x] * self.flow[y][x] ** 0.5
                              * (drop / step) * years, drop * 0.25)
                delta[y][x] -= removal
                eroded += removal
                load += removal
            if target is not None:
                nx, ny = target
                incoming[ny][nx] += load
        for y in range(self.height):
            for x in range(self.width):
                change = delta[y][x]
                if change < 0:
                    removed_soil = min(self.soil_depth[y][x], -change)
                    self.soil_depth[y][x] -= removed_soil
                    self.bedrock[y][x] -= -change - removed_soil
                else:
                    self.soil_depth[y][x] += change
                self.elevation[y][x] = self.bedrock[y][x] + self.soil_depth[y][x]
        self.geological_years += years
        self.exported_sediment += exported
        self.terrain_dirty = True
        return dict(eroded=eroded, deposited=deposited, exported=exported)

