"""Run with: python -B -m unittest discover -s tests -v."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from app.config import WorldConfig
from app.map import Grid
from app.persistence import load_world, save_world, _encode
from app.world import World
from app.save_img import save_map_image
from app.diagnostics import save_diagnostic_images
from app.simulation import renew_resources
from app.terminal import print_map


def small_world():
    return World(WorldConfig(width=12, height=10, seed=435635, river_threshold=0.5))


class EngineTests(unittest.TestCase):
    def test_reproducible_world_and_concrete_random_seed(self):
        first, second = small_world(), small_world()
        self.assertEqual(_encode(vars(first.terrain)), _encode(vars(second.terrain)))
        generated = World(WorldConfig(width=2, height=2))
        replay = World(generated.config)
        self.assertIsInstance(generated.config.seed, int)
        self.assertEqual(generated.terrain.elevation, replay.terrain.elevation)

    def test_drainage_has_no_cycles_and_conserves_runoff(self):
        for width, height in ((1, 1), (1, 5), (2, 4), (12, 10)):
            grid = Grid(width=width, height=height, seed=435635)
            for y in range(height):
                for x in range(width):
                    seen, point = set(), (x, y)
                    while point is not None:
                        self.assertNotIn(point, seen)
                        seen.add(point)
                        point = grid.flow_to[point[1]][point[0]]
            source = sum(grid.precipitation[y][x] * grid.config.runoff_fraction
                         for y in range(height) for x in range(width) if not grid.ocean[y][x])
            outlets = sum(grid.flow[y][x] for y in range(height) for x in range(width)
                          if grid.flow_to[y][x] is None)
            self.assertAlmostEqual(source, outlets)

    def test_foraging_consumption_and_spatial_index(self):
        world = small_world()
        grid = world.terrain
        grid.water = [[False] * grid.width for _ in range(grid.height)]
        grid.water[0][0] = True
        grid.resources = {(2, 0): {'food': 2}}
        entity = world.add_entity('Forager', (1, 0))
        entity.hunger, entity.thirst = 0.6, 0.8
        world.advance()
        self.assertEqual(entity.thirst, 0)
        world.advance()
        self.assertEqual(entity.location, (2, 0))
        self.assertEqual(grid.resources[(2, 0)]['food'], 1)
        self.assertLess(entity.hunger, 0.5)
        self.assertEqual(world.entities_at(2 + grid.width, 0), [entity])
        self.assertEqual(world.entities_at(1, 0), [])

    def test_movement_wraps_and_avoids_water(self):
        world = small_world()
        grid = world.terrain
        grid.water = [[False] * grid.width for _ in range(grid.height)]
        grid.resources = {(grid.width - 1, 0): {'food': 2}}
        entity = world.add_entity('Walker', (0, 0))
        entity.hunger = 0.6
        world.advance()
        self.assertEqual(entity.location, (grid.width - 1, 0))
        grid.water[0][0] = True
        with self.assertRaises(ValueError):
            world.add_entity('Swimmer', (0, 0))

    def test_renewal_limits_and_no_ore_regrowth(self):
        world = small_world()
        point = next((x, y) for y in range(world.terrain.height) for x in range(world.terrain.width)
                     if not world.terrain.water[y][x])
        world.resource_capacity = {point: {'food': 2, 'wood': 3, 'ore': 4}}
        world.terrain.resources = {point: {'food': 0, 'wood': 3, 'ore': 0}}
        for _ in range(4):
            renew_resources(world)
        self.assertEqual(world.terrain.resources[point], {'food': 2, 'wood': 3, 'ore': 0})
        world.terrain.water[point[1]][point[0]] = True
        world.terrain.resources[point]['food'] = 0
        renew_resources(world)
        self.assertEqual(world.terrain.resources[point]['food'], 0)

    def test_resources_use_current_forest_and_landform(self):
        grid = small_world().terrain
        grid.biomes = [['temperate_forest'] * grid.width for _ in range(grid.height)]
        grid.vegetation = [['tree'] * grid.width for _ in range(grid.height)]
        grid.generate_resources()
        self.assertTrue(any('food' in item for item in grid.resources.values()))
        self.assertTrue(all('wood' in item for item in grid.resources.values()))

    def test_erosion_budget_and_repeated_evolution(self):
        world = small_world()
        grid = world.terrain
        grid.initialize_geology()
        before = sum(map(sum, grid.elevation))
        budget = grid.erode_step(100)
        after = sum(map(sum, grid.elevation))
        self.assertAlmostEqual(budget['eroded'], budget['deposited'] + budget['exported'])
        self.assertAlmostEqual(before - after, budget['exported'])
        with self.assertRaises(RuntimeError):
            grid.erode_step()
        grid.refresh_environment()
        original = deepcopy(grid.elevation)
        world.evolve_terrain(100)
        world.evolve_terrain(100)
        self.assertEqual(grid.geological_years, 300)
        self.assertFalse(grid.terrain_dirty)
        self.assertNotEqual(original, grid.elevation)
        self.assertEqual(world.age, 0)

    def test_snapshot_resumes_exact_state(self):
        world = small_world()
        world.populate(4)
        world.advance(17)
        world.evolve_terrain(10)
        with tempfile.TemporaryDirectory() as directory:
            path = save_world(world, Path(directory) / 'world.json')
            restored = load_world(path)
            self.assertEqual(_encode(vars(world.terrain)), _encode(vars(restored.terrain)))
            world.advance(30)
            restored.advance(30)
            world.evolve_terrain(5)
            restored.evolve_terrain(5)
            self.assertEqual([asdict(e) for e in world.entities.values()],
                             [asdict(e) for e in restored.entities.values()])
            self.assertEqual(_encode(vars(world.terrain)), _encode(vars(restored.terrain)))
            self.assertEqual(world.terrain.rng.random(), restored.terrain.rng.random())
            self.assertEqual(restored.age, 47)

    def test_existing_snapshot_temporary_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'world.json'
            temporary = path.with_name('world.json.tmp')
            temporary.write_text('existing')
            with self.assertRaises(FileExistsError):
                save_world(small_world(), path)
            self.assertEqual(temporary.read_text(), 'existing')

    def test_renderers_do_not_mutate_world_and_png_is_valid(self):
        world = small_world()
        original = _encode(vars(world.terrain))
        with tempfile.TemporaryDirectory() as directory:
            paths = [save_map_image(world.terrain, layer=layer, output_dir=directory)
                     for layer in ('biomes', 'moisture')]
            paths += list(save_diagnostic_images(world.terrain, output_dir=directory).values())
            for path in paths:
                data = path.read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                offset, compressed = 8, b''
                while offset < len(data):
                    size = struct.unpack('!I', data[offset:offset+4])[0]
                    kind, body = data[offset+4:offset+8], data[offset+8:offset+8+size]
                    crc = struct.unpack('!I', data[offset+8+size:offset+12+size])[0]
                    self.assertEqual(crc, zlib.crc32(kind + body) & 0xffffffff)
                    if kind == b'IDAT':
                        compressed += body
                    offset += size + 12
                self.assertEqual(len(zlib.decompress(compressed)), (world.terrain.width * 4 * 3 + 1) * world.terrain.height * 4)
        with redirect_stdout(io.StringIO()):
            print_map(world.terrain)
            print_map(world.terrain, moisture=True)
        self.assertEqual(original, _encode(vars(world.terrain)))

    def test_imports_create_no_files_or_prompt(self):
        root = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PYTHONPATH=root)
            result = subprocess.run([sys.executable, '-B', '-c', 'import main; import app.world'],
                                    cwd=directory, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_configuration_rejects_invalid_values(self):
        for values in ({'width': 0}, {'height': True}, {'runoff_fraction': 2},
                       {'river_threshold': 0}, {'seed': 'bad'}, {'hunger_per_tick': float('nan')}):
            with self.assertRaises(ValueError):
                WorldConfig(**values)


if __name__ == '__main__':
    unittest.main()
