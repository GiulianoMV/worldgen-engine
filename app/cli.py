"""Interactive and scripted interfaces to the same world lifecycle."""
import argparse
import math
from pathlib import Path

from app.config import WorldConfig
from app.world import World
from app.persistence import load_world, save_world
from app.save_img import save_map_image
from app.diagnostics import save_diagnostic_images
from app.terminal import print_map
from app.logger import configure_logging

DATA = Path(__file__).resolve().parents[1] / 'data'


def summary(world):
    living = sum(entity.alive for entity in world.entities.values())
    print(f'{world.terrain.name}: {world.terrain.width}x{world.terrain.height}, seed={world.config.seed}')
    print(f'Ticks: {world.age} | Entidades vivas: {living}/{len(world.entities)} | '
          f'Anos geologicos: {getattr(world.terrain, "geological_years", 0):g}')


def export(world, output_dir=None):
    grid = world.terrain
    paths = {layer: save_map_image(grid, layer=layer, output_dir=output_dir)
             for layer in ('biomes', 'moisture')}
    paths.update(save_diagnostic_images(grid, output_dir=output_dir))
    for layer, path in paths.items():
        print(f'{layer}: {path}')


def interactive():
    world = None
    while True:
        print('\n1 Gerar mundo | 2 Resumo | 3 Mapa | 4 Umidade | 5 Exportar imagens')
        print('6 Adicionar entidades | 7 Simular ticks | 8 Evoluir terreno | 9 Salvar | 10 Carregar | 0 Sair')
        try:
            choice = input('Acao: ').strip()
            if choice == '0':
                return
            if choice == '1':
                width = int(input('Largura [150]: ') or 150)
                height = int(input('Altura [150]: ') or 150)
                seed = input('Seed [aleatoria]: ').strip()
                world = World(WorldConfig(width=width, height=height, seed=int(seed) if seed else None))
                summary(world)
            elif choice == '10':
                world = load_world(input('Arquivo JSON: '))
                summary(world)
            elif world is None:
                print('Gere ou carregue um mundo primeiro.')
            elif choice == '2':
                summary(world)
            elif choice in ('3', '4'):
                print_map(world.terrain, moisture=choice == '4')
            elif choice == '5':
                export(world)
            elif choice == '6':
                world.populate(int(input('Quantidade: ')))
                summary(world)
            elif choice == '7':
                world.advance(int(input('Ticks [1]: ') or 1))
                summary(world)
            elif choice == '8':
                print(world.evolve_terrain(float(input('Anos geologicos [1]: ') or 1)))
            elif choice == '9':
                path = input('Arquivo JSON [data/worlds/world.json]: ') or str(DATA / 'worlds' / 'world.json')
                print(save_world(world, path))
            else:
                print('Opcao invalida.')
        except (ValueError, OSError, KeyError, TypeError) as error:
            print(f'Nao foi possivel concluir: {error}')
        except EOFError:
            return


def main(argv=None):
    parser = argparse.ArgumentParser(description='Gerador de mundos e simulador de entidades/terreno.')
    parser.add_argument('--generate', action='store_true', help='Gerar sem menu interativo')
    parser.add_argument('--width', type=int, default=150)
    parser.add_argument('--height', type=int, default=150)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--entities', type=int, default=0)
    parser.add_argument('--ticks', type=int, default=0)
    parser.add_argument('--years', type=float, default=0, help='Anos geologicos, independentes dos ticks')
    parser.add_argument('--load', type=Path)
    parser.add_argument('--save', type=Path)
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    if not math.isfinite(args.years) or args.years < 0:
        parser.error('Anos geologicos devem ser finitos e nao negativos.')
    if args.entities < 0 or args.ticks < 0:
        parser.error('Entidades e ticks devem ser nao negativos.')
    if args.generate and args.load:
        parser.error('Escolha gerar ou carregar um mundo.')
    if not args.generate and args.load is None and any((args.save, args.export, args.entities, args.ticks, args.years, args.seed is not None, args.width != 150, args.height != 150, args.output_dir)):
        parser.error('Use --generate ou --load para executar sem menu.')
    log = configure_logging()
    if not args.generate and args.load is None:
        interactive()
        return 0
    try:
        if args.years < 0:
            raise ValueError('Anos geologicos devem ser positivos ou zero.')
        world = load_world(args.load) if args.load else World(WorldConfig(width=args.width, height=args.height, seed=args.seed))
        world.populate(args.entities)
        if args.years:
            world.evolve_terrain(args.years)
        world.advance(args.ticks)
        if args.save:
            print(save_world(world, args.save))
        if args.export:
            export(world, args.output_dir)
        summary(world)
        log.info('World processed: seed=%s ticks=%s', world.config.seed, world.age)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
