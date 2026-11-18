"""Versioned JSON snapshots, including RNG and derived layers; no pickle."""
from dataclasses import asdict
import json
import math
from pathlib import Path
import random

from app.config import WorldConfig
from app.entity import Entity
from app.map import Grid
from app.tectonics import Tectonics
from app.world import World


def _encode(value):
    if isinstance(value, WorldConfig):
        return {'$config': asdict(value)}
    if isinstance(value, random.Random):
        return {'$rng': _encode(value.getstate())}
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            raise ValueError('Cannot save NaN.')
        return {'$infinity': 1 if value > 0 else -1}
    if isinstance(value, tuple):
        return {'$tuple': [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {'$dict': [[_encode(key), _encode(item)] for key, item in value.items()]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, (Grid, Tectonics, Entity)):
        return {'$object': type(value).__name__, 'state': _encode(vars(value))}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'Unsupported snapshot value: {type(value).__name__}')


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if '$config' in value:
        return WorldConfig(**value['$config'])
    if '$rng' in value:
        rng = random.Random()
        rng.setstate(_decode(value['$rng']))
        return rng
    if '$infinity' in value:
        return math.inf * value['$infinity']
    if '$tuple' in value:
        return tuple(_decode(item) for item in value['$tuple'])
    if '$dict' in value:
        return {_decode(key): _decode(item) for key, item in value['$dict']}
    if '$object' in value:
        cls = {'Grid': Grid, 'Tectonics': Tectonics, 'Entity': Entity}[value['$object']]
        instance = cls.__new__(cls)
        instance.__dict__.update(_decode(value['state']))
        return instance
    raise ValueError('Unknown snapshot structure.')


def save_world(world, path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {key: value for key, value in vars(world).items() if key != 'spatial_index'}
    payload = {'version': 1, 'state': _encode(state)}
    temporary = path.with_name(path.name + '.tmp')
    output = temporary.open('x', encoding='utf-8')
    try:
        with output:
            json.dump(payload, output, allow_nan=False, separators=(',', ':'))
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def load_world(path):
    with Path(path).open(encoding='utf-8') as source:
        payload = json.load(source)
    if payload.get('version') != 1:
        raise ValueError('Unsupported world snapshot version.')
    state = _decode(payload['state'])
    world = World.__new__(World)
    world.__dict__.update(state)
    if not isinstance(world.config, WorldConfig) or not isinstance(world.terrain, Grid):
        raise ValueError('Invalid world snapshot.')
    world.rebuild_spatial_index()
    return world
