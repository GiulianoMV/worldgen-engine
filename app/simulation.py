"""Deterministic foraging: one cardinal movement per tick, land only."""
from collections import deque


def next_step(grid, start, goal):
    pending, previous = deque([start]), {start: None}
    while pending:
        point = pending.popleft()
        if goal(*point):
            while previous[point] is not None and previous[point] != start:
                point = previous[point]
            return point
        for neighbor in grid._neighbors(*point):
            x, y = neighbor
            if neighbor not in previous and not grid.water[y][x]:
                previous[neighbor] = point
                pending.append(neighbor)
    return start


def advance_entities(world):
    grid, config = world.terrain, world.config

    def water_near(x, y):
        return grid.water[y][x] or any(grid.water[ny][nx] for nx, ny in grid._neighbors(x, y))

    def food_at(x, y):
        return grid.resources.get((x, y), {}).get('food', 0) > 0

    for entity in sorted(world.entities.values(), key=lambda item: item.id):
        if not entity.alive:
            continue
        entity.hunger = min(1.0, entity.hunger + config.hunger_per_tick)
        entity.thirst = min(1.0, entity.thirst + config.thirst_per_tick)
        if entity.thirst >= 0.5:
            entity.location = next_step(grid, entity.location, water_near)
        elif entity.hunger >= 0.5:
            entity.location = next_step(grid, entity.location, food_at)
        x, y = entity.location
        if water_near(x, y):
            entity.thirst = 0.0
        if entity.hunger >= 0.5 and food_at(x, y):
            grid.resources[(x, y)]['food'] -= 1
            entity.hunger = max(0.0, entity.hunger - 0.6)
        entity.health = max(0.0, entity.health - (2 if entity.hunger >= 1 else 0)
                            - (4 if entity.thirst >= 1 else 0))
    world.rebuild_spatial_index()


def renew_resources(world):
    """Refill renewable initial deposits gradually, excluding submerged cells."""
    for point, capacity in world.resource_capacity.items():
        x, y = point
        if world.terrain.water[y][x]:
            continue
        deposits = world.terrain.resources.setdefault(point, {})
        for kind in ('food', 'wood'):
            if kind in capacity:
                deposits[kind] = min(capacity[kind], deposits.get(kind, 0) + 1)
