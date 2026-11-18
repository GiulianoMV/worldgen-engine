"""Terrain hydrology system; operates on shared grid layers."""
import math
import heapq
from collections import deque


class Hydrology:
    def classify_ocean(self):
        """Convention: the largest connected submerged region is the ocean."""
        submerged = [[v <= self.sea_level for v in row] for row in self.elevation]
        visited = set()
        largest = []
        for y in range(self.height):
            for x in range(self.width):
                if not submerged[y][x] or (x, y) in visited:
                    continue
                region = []
                pending = deque([(x, y)])
                visited.add((x, y))
                while pending:
                    cx, cy = pending.popleft()
                    region.append((cx, cy))
                    for nx, ny in self._neighbors(cx, cy):
                        if submerged[ny][nx] and (nx, ny) not in visited:
                            visited.add((nx, ny))
                            pending.append((nx, ny))
                if len(region) > len(largest):
                    largest = region
        self.ocean = [[False] * self.width for _ in range(self.height)]
        for x, y in largest:
            self.ocean[y][x] = True
        self.water = submerged

    def _flow_neighbors(self, x, y):
        """Unique D8 neighbors with shortest cell-center distances, wrapping x."""
        neighbors = {}
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dx == 0 and dy == 0) or not 0 <= y + dy < self.height:
                    continue
                point = ((x + dx) % self.width, y + dy)
                if point == (x, y):
                    continue
                distance = math.hypot(dx, dy)
                neighbors[point] = min(neighbors.get(point, math.inf), distance)
        for (nx, ny), distance in neighbors.items():
            yield nx, ny, distance

    def calculate_drainage(self):
        """Fill depressions, then independently route D8 steepest descent.

        A distance-to-outlet gradient drains equal-height flats without relying
        on Priority-Flood predecessor order. Every receiver has a strictly
        lower (filled height, flat distance) key, so cycles are impossible.
        Actual elevation remains unchanged.
        """
        self.drainage_elevation = [row.copy() for row in self.elevation]
        visited = [[False] * self.width for _ in range(self.height)]
        pending = []
        roots = set()
        for y in range(self.height):
            for x in range(self.width):
                if self.ocean[y][x]:
                    level = max(self.sea_level, self.elevation[y][x])
                    self.drainage_elevation[y][x] = level
                    visited[y][x] = True
                    roots.add((x, y))
                    heapq.heappush(pending, (level, y, x))
        if not pending:
            level, y, x = min((self.elevation[y][x], y, x)
                             for y in range(self.height) for x in range(self.width))
            visited[y][x] = True
            roots.add((x, y))
            heapq.heappush(pending, (level, y, x))
        while pending:
            level, y, x = heapq.heappop(pending)
            for nx, ny, _ in self._flow_neighbors(x, y):
                if visited[ny][nx]:
                    continue
                visited[ny][nx] = True
                filled = max(self.elevation[ny][nx], level)
                self.drainage_elevation[ny][nx] = filled
                heapq.heappush(pending, (filled, ny, nx))

        # Dijkstra within each level surface: its outlets are roots or cells
        # adjacent to lower surfaces. Diagonal steps have length sqrt(2).
        flat_distance = [[math.inf] * self.width for _ in range(self.height)]
        pending = []
        for y in range(self.height):
            for x in range(self.width):
                level = self.drainage_elevation[y][x]
                if (x, y) in roots or any(self.drainage_elevation[ny][nx] < level
                                         for nx, ny, _ in self._flow_neighbors(x, y)):
                    flat_distance[y][x] = 0.0
                    heapq.heappush(pending, (0.0, y, x))
        while pending:
            distance, y, x = heapq.heappop(pending)
            if distance > flat_distance[y][x]:
                continue
            for nx, ny, step in self._flow_neighbors(x, y):
                if self.drainage_elevation[ny][nx] != self.drainage_elevation[y][x]:
                    continue
                candidate = distance + step
                if candidate < flat_distance[ny][nx]:
                    flat_distance[ny][nx] = candidate
                    heapq.heappush(pending, (candidate, ny, nx))

        self.flow_to = [[None] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in roots:
                    continue
                level = self.drainage_elevation[y][x]
                downhill, flat = [], []
                for nx, ny, step in self._flow_neighbors(x, y):
                    drop = level - self.drainage_elevation[ny][nx]
                    # Stable spatial tie-break only; never creates uphill flow.
                    tie = ((nx * 73856093) ^ (ny * 19349663)) & 0xffffffff
                    if drop > 0:
                        downhill.append((drop / step, tie, nx, ny))
                    elif drop == 0 and flat_distance[ny][nx] < flat_distance[y][x]:
                        gradient = (flat_distance[y][x] - flat_distance[ny][nx]) / step
                        original_drop = (self.elevation[y][x] - self.elevation[ny][nx]) / step
                        flat.append((gradient, original_drop, tie, nx, ny))
                candidates = downhill or flat
                if not candidates:
                    raise RuntimeError('Drainage cell has no path to its outlet.')
                *_, nx, ny = max(candidates)
                self.flow_to[y][x] = (nx, ny)
        self.drainage_order = sorted(
            ((x, y) for y in range(self.height) for x in range(self.width)),
            key=lambda point: (self.drainage_elevation[point[1]][point[0]],
                               flat_distance[point[1]][point[0]])
        )
        self.potential_lake_depth = [
            [0.0 if self.ocean[y][x] else max(
                0.0, self.drainage_elevation[y][x] - self.elevation[y][x])
             for x in range(self.width)] for y in range(self.height)]

    def calculate_flow(self, runoff_fraction=0.4):
            """Relative runoff, not physical discharge; ocean rain is excluded."""
            if not 0 <= runoff_fraction <= 1:
                raise ValueError("runoff_fraction must be between 0 and 1.")
            self.flow = [[0.0 if self.ocean[y][x] else
                          self.precipitation[y][x] * runoff_fraction
                          for x in range(self.width)] for y in range(self.height)]
            for x, y in reversed(self.drainage_order):
                target = self.flow_to[y][x]
                if target is not None:
                    nx, ny = target
                    self.flow[ny][nx] += self.flow[y][x]

    def generate_lakes_and_rivers(self, river_threshold=0.05, minimum_lake_flow=0.0):
        """Classify water from drainage, without carving or filling terrain.

        Fed depressions are assumed to fill to their spill level (MVP).
        Flow thresholds use the relative units of calculate_flow(). No water
        volume, evaporation balance, river width or depth is simulated here.
        """
        if not math.isfinite(river_threshold) or river_threshold <= 0:
            raise ValueError("river_threshold must be finite and positive.")
        if not math.isfinite(minimum_lake_flow) or minimum_lake_flow < 0:
            raise ValueError("minimum_lake_flow must be finite and nonnegative.")
        self.lake = [[False] * self.width for _ in range(self.height)]
        self.river = [[False] * self.width for _ in range(self.height)]
        self.lake_depth = [[0.0] * self.width for _ in range(self.height)]
        self.water_type = [[None] * self.width for _ in range(self.height)]
        self.water_surface = [[None] * self.width for _ in range(self.height)]
        epsilon = 1e-12
        visited = set()

        # Connected depressions with a common spill level form a lake basin.
        # Check supply over the entire basin so dry cells beside a fed cell
        # share the same horizontal water surface.
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in visited or self.ocean[y][x] or self.potential_lake_depth[y][x] <= epsilon:
                    continue
                level = self.drainage_elevation[y][x]
                basin = []
                pending = deque([(x, y)])
                visited.add((x, y))
                supplied = False
                while pending:
                    cx, cy = pending.popleft()
                    basin.append((cx, cy))
                    supplied = supplied or self.flow[cy][cx] > minimum_lake_flow
                    for nx, ny, _ in self._flow_neighbors(cx, cy):
                        if ((nx, ny) not in visited and not self.ocean[ny][nx]
                                and self.potential_lake_depth[ny][nx] > epsilon
                                and math.isclose(self.drainage_elevation[ny][nx], level,
                                                 rel_tol=0.0, abs_tol=epsilon)):
                            visited.add((nx, ny))
                            pending.append((nx, ny))
                if supplied:
                    for lx, ly in basin:
                        self.lake[ly][lx] = True
                        self.lake_depth[ly][lx] = self.potential_lake_depth[ly][lx]
                        self.water_surface[ly][lx] = level

        # Accumulated flow cannot decrease downstream in this runoff model.
        # A threshold therefore preserves connected channels through the
        # receiver tree, including lake outlets and the horizontal seam.
        for y in range(self.height):
            for x in range(self.width):
                if self.ocean[y][x]:
                    self.water_type[y][x] = 'ocean'
                    self.water_surface[y][x] = self.sea_level
                elif self.lake[y][x]:
                    self.water_type[y][x] = 'lake'
                elif self.flow[y][x] >= river_threshold:
                    self.river[y][x] = True
                    self.water_type[y][x] = 'river'

        # Rebuild, rather than mutate the former submerged mask: unfed
        # inland depressions are not automatically treated as permanent water.
        self.water = [[kind is not None for kind in row] for row in self.water_type]

    def calculate_distance_to_water(self):
        """Cardinal distance to water using a multi-source breadth-first search."""
        self.distance_to_water = [[math.inf] * self.width for _ in range(self.height)]
        pending = deque()
        for y in range(self.height):
            for x in range(self.width):
                if self.water[y][x]:
                    self.distance_to_water[y][x] = 0
                    pending.append((x, y))
        while pending:
            x, y = pending.popleft()
            for nx, ny in self._neighbors(x, y):
                if self.distance_to_water[ny][nx] == math.inf:
                    self.distance_to_water[ny][nx] = self.distance_to_water[y][x] + 1
                    pending.append((nx, ny))

