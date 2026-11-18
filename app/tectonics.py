import math
import random



class Tectonics:
    """Fixed plates on a grid periodic in x, with conceptual velocities."""

    def __init__(self, width: int, height: int, num_plates: int = 10, seed: int = None, generate_fields=True):
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0
               for n in (width, height)):
            raise ValueError('Width and height must be positive integers.')
        if isinstance(num_plates, bool) or not isinstance(num_plates, int) or num_plates <= 0:
            raise ValueError('num_plates must be a positive integer.')
        if num_plates > width * height:
            raise ValueError('num_plates cannot exceed the number of cells.')

        self.width = width
        self.height = height
        self.num_plates = num_plates
        self.seed = seed
        self.rng = random.Random(seed)
        self.plates = []
        self.plate_id = [[0] * width for _ in range(height)]
        # Each sorted plate pair holds its individual contact segments.
        self.boundaries = {}

        # Trinity matrices
        self.base_elevation = [[0.0] * width for _ in range(height)]
        self.tectonic_relief = [[0.0] * width for _ in range(height)]
        self.uplift_rate = [[0.0] * width for _ in range(height)]

        self.generate_plates()
        self.assign_cells()
        self.classify_boundaries()
        if generate_fields:
            self.generate_fields()

    def generate_plates(self):
        """Create seeds and velocities; spacing constraints remain a future step."""
        self.plates = [
            {'id': i,
             'seed': (self.rng.random() * self.width, self.rng.random() * self.height),
             'velocity': (self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)),
             'base_height': self.rng.uniform(0.2, 0.6)}
            for i in range(self.num_plates)
        ]

    def _wrapped_dx(self, dx):
        """Shortest signed horizontal displacement (negative on half-period ties)."""
        return (dx + self.width / 2) % self.width - self.width / 2

    def assign_cells(self):
        """Rasterized periodic Voronoi, with deterministic ties by plate order."""
        for y in range(self.height):
            for x in range(self.width):
                self.plate_id[y][x] = min(
                    self.plates,
                    key=lambda p: self._wrapped_dx(p['seed'][0] - x) ** 2
                    + (p['seed'][1] - y) ** 2
                )['id']

    def classify_boundaries(self):
        """Record each raster face once and classify motion per segment.

        Normals point from the lower plate ID (A) to the higher ID (B),
        using the local periodic images of the Voronoi seeds. Positive
        normal_speed means separation; positive convergence means closing.
        Segment endpoints use cells centered on integer coordinates, and
        remain unwrapped locally at the horizontal seam.
        """
        plate_map = {p['id']: p for p in self.plates}
        self.boundaries = {}
        tolerance = 1e-9
        for y in range(self.height):
            for x in range(self.width):
                # Right and down enumerate faces once. With width=2, two
                # distinct cylindrical faces connect the same pair of cells.
                for dx, dy in ((1, 0), (0, 1)):
                    ux, ny = x + dx, y + dy
                    if ny >= self.height:
                        continue
                    nx = ux % self.width
                    current = self.plate_id[y][x]
                    neighbor = self.plate_id[ny][nx]
                    if current == neighbor:
                        continue
                    pair = tuple(sorted((current, neighbor)))
                    a, b = plate_map[pair[0]], plate_map[pair[1]]
                    current_seed = plate_map[current]['seed']
                    neighbor_seed = plate_map[neighbor]['seed']
                    # Pick each seed image near its owning cell in this
                    # local, unwrapped coordinate system.
                    cx = x + self._wrapped_dx(current_seed[0] - x)
                    bx = ux + self._wrapped_dx(neighbor_seed[0] - ux)
                    sx = bx - cx
                    sy = neighbor_seed[1] - current_seed[1]
                    orientation = 1 if current == pair[0] else -1
                    sx, sy = sx * orientation, sy * orientation
                    length = math.hypot(sx, sy)
                    if length <= tolerance:
                        normal = (dx * orientation, dy * orientation)
                    else:
                        normal = (sx / length, sy / length)
                    tangent = (-normal[1], normal[0])
                    relative = (b['velocity'][0] - a['velocity'][0],
                                b['velocity'][1] - a['velocity'][1])
                    normal_speed = sum(v * n for v, n in zip(relative, normal))
                    shear = sum(v * t for v, t in zip(relative, tangent))
                    if normal_speed < -tolerance:
                        kind = 'convergent'
                    elif normal_speed > tolerance:
                        kind = 'divergent'
                    elif abs(shear) > tolerance:
                        kind = 'transform'
                    else:
                        kind = 'stationary'
                    endpoints = (
                        ((x + 0.5, y - 0.5), (x + 0.5, y + 0.5)) if dx
                        else ((x - 0.5, y + 0.5), (x + 0.5, y + 0.5))
                    )
                    segment = {
                        'cells': ((x, y), (nx, ny)),
                        'endpoints': endpoints,
                        'wraps_x': bool(dx and ux == self.width),
                        'normal': normal,
                        'relative_velocity': relative,
                        'normal_speed': normal_speed,
                        'convergence': -normal_speed,
                        'shear': shear,
                        'type': kind,
                    }
                    boundary = self.boundaries.setdefault(pair, {'plates': pair, 'segments': []})
                    boundary['segments'].append(segment)

    def _empty_field(self):
        return [[0.0] * self.width for _ in range(self.height)]

    def _segment_distance_squared(self, x, y, segment):
        """Exact periodic distance to an axis-aligned raster boundary face.

        Taking the nearest image of its midpoint suffices for these short,
        axis-aligned segments. No duplicated wrapped samples are accumulated.
        """
        (ax, ay), (bx, by) = segment['endpoints']
        center_x, center_y = (ax + bx) / 2, (ay + by) / 2
        dx = max(0.0, abs(self._wrapped_dx(x - center_x)) - abs(bx - ax) / 2)
        dy = max(0.0, abs(y - center_y) - abs(by - ay) / 2)
        return dx * dx + dy * dy

    def generate_fields(self, influence_width=None, smoothing_length=None, mountain_amplitude=0.3, depression_amplitude=0.15, uplift_coefficient=0.0001, subsidence_coefficient=0.0001):
        """Rebuild deterministic fields from stored plate properties.

        Base uses continuous inverse-distance weights over all seeds. Segment
        interactions are blended by distance and length within each plate pair.
        Pair contributions fade with distance and are combined with a bounded,
        continuous weighted mean, rather than selecting a winning segment.
        Rates are provisional normalized-height units per simulation year.
        """
        if influence_width is None:
            influence_width = max(1.0, min(self.width, self.height) / 20)
        if smoothing_length is None:
            smoothing_length = max(1.0, min(self.width, self.height) / 20)
        for value in (influence_width, smoothing_length):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Field lengths must be finite and positive.')
        for value in (mountain_amplitude, depression_amplitude,
                      uplift_coefficient, subsidence_coefficient):
            if not math.isfinite(value) or value < 0:
                raise ValueError('Field amplitudes and rates must be finite and nonnegative.')
        self.base_elevation = self._empty_field()
        self.tectonic_relief = self._empty_field()
        self.uplift_rate = self._empty_field()
        smoothing_squared = smoothing_length ** 2
        gaussian_denominator = 2 * influence_width ** 2
        boundaries = []
        for boundary in self.boundaries.values():
            segments = []
            for segment in boundary['segments']:
                (ax, ay), (bx, by) = segment['endpoints']
                length = math.hypot(bx - ax, by - ay)
                if length > 0:
                    interaction = (0.0 if segment['type'] in ('transform', 'stationary')
                                   else segment['convergence'])
                    segments.append((segment, length, interaction))
            if segments:
                boundaries.append(segments)
        for y in range(self.height):
            for x in range(self.width):
                weighted_height = total_weight = 0.0
                for plate in self.plates:
                    px, py = plate['seed']
                    distance_squared = self._wrapped_dx(px - x) ** 2 + (py - y) ** 2
                    weight = 1.0 / (distance_squared + smoothing_squared)
                    weighted_height += plate['base_height'] * weight
                    total_weight += weight
                self.base_elevation[y][x] = weighted_height / total_weight
                weighted_interaction = boundary_weight = 0.0
                for segments in boundaries:
                    distances = [
                        (self._segment_distance_squared(x, y, segment), length, interaction)
                        for segment, length, interaction in segments
                    ]
                    nearest_distance = min(d for d, _, _ in distances)
                    attenuation = math.exp(-nearest_distance / gaussian_denominator)
                    if attenuation == 0.0:
                        continue
                    local_sum = local_weight = 0.0
                    for distance, length, interaction in distances:
                        # Subtracting the minimum avoids underflow in the
                        # normalized mean without changing relative weights.
                        weight = length * math.exp(
                            -(distance - nearest_distance) / gaussian_denominator)
                        local_sum += interaction * weight
                        local_weight += weight
                    weighted_interaction += (local_sum / local_weight) * attenuation
                    boundary_weight += attenuation
                # Sum weak distant influences, average overlapping strong ones.
                # The denominator is continuous and keeps amplitudes bounded.
                influence = weighted_interaction / max(1.0, boundary_weight)
                self.tectonic_relief[y][x] = influence * (
                    mountain_amplitude if influence >= 0 else depression_amplitude)
                self.uplift_rate[y][x] = influence * (
                    uplift_coefficient if influence >= 0 else subsidence_coefficient)

    def calculate_elevation(self):
        """Compose initial regional height and tectonic relief, without rescaling.

        This is initial terrain, not an increment to reapply during evolution.
        uplift_rate is the separate field reserved for subsequent time steps.
        """
        return [[self.base_elevation[y][x] + self.tectonic_relief[y][x]
                 for x in range(self.width)] for y in range(self.height)]
