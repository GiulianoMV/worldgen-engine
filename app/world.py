"""World lifecycle and independent entity/geological clocks."""
from dataclasses import replace
from copy import deepcopy
import math
import secrets

from app.config import WorldConfig
from app.entity import Entity
from app.map import Grid
from app.simulation import advance_entities, renew_resources


class World:
    def __init__(self, config=None, name='World'):
        config = config or WorldConfig()
        self.config = replace(config, seed=secrets.randbits(32)) if config.seed is None else config
        self.terrain = Grid(name, config=self.config)
        self.entities = {}
        self.age = 0
        self.next_entity_id = 1
        self.resource_capacity = deepcopy(self.terrain.resources)
        self.rebuild_spatial_index()

    def rebuild_spatial_index(self):
        self.spatial_index = {}
        for entity in self.entities.values():
            self.spatial_index.setdefault(entity.location, set()).add(entity.id)

    def entities_at(self, x, y):
        return [self.entities[key] for key in sorted(self.spatial_index.get((x % self.terrain.width, y), ()))]

    def add_entity(self, name, location):
        x, y = location
        if not (0 <= x < self.terrain.width and 0 <= y < self.terrain.height):
            raise ValueError('Entity location is outside the world.')
        if self.terrain.water[y][x]:
            raise ValueError('Entities must start on land.')
        entity = Entity(self.next_entity_id, name, (x, y))
        self.next_entity_id += 1
        self.entities[entity.id] = entity
        self.rebuild_spatial_index()
        return entity

    def populate(self, count):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Population must be a nonnegative integer.')
        land = [(x, y) for y in range(self.terrain.height) for x in range(self.terrain.width)
                if not self.terrain.water[y][x]]
        if count and not land:
            raise ValueError('This world has no land for entities.')
        for _ in range(count):
            self.add_entity(f'Entity {self.next_entity_id}', self.terrain.rng.choice(land))

    def advance(self, ticks=1):
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 0:
            raise ValueError('ticks must be a nonnegative integer.')
        for _ in range(ticks):
            advance_entities(self)
            self.age += 1
            if self.age % self.config.resource_regrowth_ticks == 0:
                renew_resources(self)

    def evolve_terrain(self, years=1.0):
        if not math.isfinite(years) or years <= 0:
            raise ValueError('years must be finite and positive.')
        grid = self.terrain
        if not hasattr(grid, 'bedrock'):
            grid.initialize_geology(self.config.soil_depth, self.config.erodibility)
        for y in range(grid.height):
            for x in range(grid.width):
                uplift = grid.tectonics.uplift_rate[y][x] * years
                grid.bedrock[y][x] += uplift
                grid.elevation[y][x] += uplift
        grid.refresh_environment()
        budget = grid.erode_step(years, self.config.deposition_fraction)
        grid.refresh_environment()
        for point in list(grid.resources):
            x, y = point
            if grid.water[y][x]:
                del grid.resources[point]
        land = [(x, y) for y in range(grid.height) for x in range(grid.width) if not grid.water[y][x]]
        for entity in self.entities.values():
            x, y = entity.location
            if grid.water[y][x] and entity.alive:
                if land:
                    entity.location = min(land, key=lambda p: min(abs(p[0]-x), grid.width-abs(p[0]-x)) + abs(p[1]-y))
                else:
                    entity.health = 0.0
        self.rebuild_spatial_index()
        return budget
