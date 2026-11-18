"""Terrain climate system; operates on shared grid layers."""
import math


class Climate:
    def generate_precipitation(self, max_iterations=None, tolerance=1e-6):
        """Steady relative rainfall from conservative 2D moisture transport.

        Ocean evaporation supplies moisture; baseline/convection rain also
        falls on flat or descending land. Iteration is bounded, not a weather
        simulation. Initial inland depressions do not act as ocean sources.
        """
        if max_iterations is None:
            max_iterations = max(512, min(4096, 4 * (self.width + self.height)))
        if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError('max_iterations must be a positive integer.')
        if not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError('tolerance must be finite and positive.')
        self.precipitation = [[0.0] * self.width for _ in range(self.height)]
        air = [[0.0] * self.width for _ in range(self.height)]
        evaporation = [[0.0] * self.width for _ in range(self.height)]
        fractions = [[0.0] * self.width for _ in range(self.height)]
        directions = []
        for y in range(self.height):
            latitude = 0.0 if self.height == 1 else 90 - 180 * y / (self.height - 1)
            latitude = abs(latitude)
            direction = 1 if 30 <= latitude < 60 else -1
            directions.append(direction)
            # Small per-cell losses let moist air cross continental interiors.
            convection = 0.02 * math.exp(-(latitude / 20) ** 2)
            frontal = 0.012 * math.exp(-((latitude - 50) / 15) ** 2)
            for x in range(self.width):
                temperature = self.get_temperature_index(x, y)
                if self.ocean[y][x]:
                    evaporation[y][x] = 0.25 * (0.25 + 0.75 * temperature)
                previous_x = (x - direction) % self.width
                uphill = max(0.0, self.elevation[y][x] - self.elevation[y][previous_x])
                fractions[y][x] = min(0.85, 0.008 + convection + frontal + uphill * 1.5)
        self.climate_converged = False
        for iteration in range(max_iterations):
            next_air = [[0.0] * self.width for _ in range(self.height)]
            largest_change = 0.0
            for y in range(self.height):
                north, south = max(0, y - 1), min(self.height - 1, y + 1)
                direction = directions[y]
                for x in range(self.width):
                    # Reflect at north/south; horizontal transport wraps.
                    available = (0.90 * air[y][(x - direction) % self.width]
                                 + 0.05 * air[north][x] + 0.05 * air[south][x])
                    available += evaporation[y][x] * (1 - available)
                    rainfall = available * fractions[y][x]
                    next_air[y][x] = available - rainfall
                    self.precipitation[y][x] = rainfall
                    largest_change = max(largest_change, abs(next_air[y][x] - air[y][x]))
            air = next_air
            if largest_change <= tolerance:
                self.climate_converged = True
                break
        self.climate_iterations = iteration + 1
        self.climate_residual = largest_change

    def generate_moisture(self, rainfall_reference=0.008):
        """Soil-moisture index from rain, regional variation and nearby water.

        A fixed rainfall reference calibrates relative precipitation without
        forcing every planet to contain a maximally wet or dry cell.
        """
        if not math.isfinite(rainfall_reference) or rainfall_reference <= 0:
            raise ValueError('rainfall_reference must be finite and positive.')
        noise = self._noise(max(2, min(self.width, self.height) / 3))
        self.moisture = [[0.0] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                rain = -math.expm1(-self.precipitation[y][x] / rainfall_reference)
                proximity = max(0.0, 1 - self.distance_to_water[y][x] / 5)
                combined = 0.70 * rain + 0.10 * noise[y][x] + 0.20 * proximity
                self.moisture[y][x] = min(1.0, max(0.0, combined))

    def get_temperature_index(self, x, y):
        if self.height <= 1:
            latitude_factor = 1.0
        else:
            lat = 90 - 180 * y / (self.height - 1)
            latitude_factor = max(0.1, 1.0 - (abs(lat) / 90.0))

        elevation = self.elevation[y][x]
        elevation_penalty = elevation * 0.5

        temperature = max(0.0, min(1.0, latitude_factor - elevation_penalty))
        return temperature

