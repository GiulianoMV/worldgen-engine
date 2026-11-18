"""Optional terminal renderer, separate from terrain state."""


class TerminalRenderer:
    BIOME_STYLES = {
        'water': ('W', '38;5;33'),
        'beach': ('S', '38;5;229'),
        'mountain': ('M', '38;5;245'),
        'alpine': ('A', '38;5;255'),
        'cliff': ('R', '38;5;240'),
        'polar_desert': ('P', '38;5;159'),
        'tundra': ('U', '38;5;151'),
        'cold_steppe': ('E', '38;5;180'),
        'taiga': ('I', '38;5;22'),
        'boreal_forest': ('B', '38;5;65'),
        'desert': ('D', '38;5;178'),
        'grassland': ('G', '38;5;114'),
        'temperate_forest': ('F', '38;5;28'),
        'temperate_rainforest': ('H', '38;5;37'),
        'hot_desert': ('X', '38;5;208'),
        'savanna': ('V', '38;5;142'),
        'tropical_seasonal_forest': ('J', '38;5;70'),
        'tropical_rainforest': ('Q', '38;5;46'),
    }
    SYMBOLS = {biome: style[0] for biome, style in BIOME_STYLES.items()}
    COLORS = {symbol: color for symbol, color in BIOME_STYLES.values()}
    COLORS.update({'T': '38;5;34', 'C': '38;5;40'})
    def build_visual_grid(self):
        self.grid = [[{'tree': 'T', 'cactus': 'C'}.get(self.vegetation[y][x]) or self.SYMBOLS[self.biomes[y][x]]
                      for x in range(self.width)] for y in range(self.height)]

    def print_grid(self):
        self.build_visual_grid()
        cell_width = max(1, len(str(self.width - 1)))
        row_width = max(1, len(str(self.height - 1)))
        print('Coordinates (x, y): x increases right; y increases down; origin (0, 0).')
        print(f'World wraps horizontally: x={self.width - 1} connects to x=0; north/south do not wrap.')
        print(f'{"y/x":>{row_width + 2}} ' + ' '.join(
            f'{x:>{cell_width}}' for x in range(self.width)))
        for y, row in enumerate(self.grid):
            cells = ' '.join(
                f'\033[{self.COLORS[cell]}m{cell:>{cell_width}}\033[0m'
                for cell in row)
            print(f'{y:>{row_width + 2}} {cells}')
        print('Biome legend (T: Tree and C: Cactus overlay the biome symbol):')
        entries = [
            f'\033[{color}m{symbol}\033[0m: {biome.replace("_", " ")}'
            for biome, (symbol, color) in self.BIOME_STYLES.items()
        ]
        for start in range(0, len(entries), 4):
            print(' | '.join(entries[start:start + 4]))
        print(f'\033[{self.COLORS["T"]}mT\033[0m: Tree | '
              f'\033[{self.COLORS["C"]}mC\033[0m: Cactus')
        print(f"Map Name: {self.name} | Width: {self.width} | Height: {self.height} | Seed: {self.seed}")
        print(f"Sea Level: {self.sea_level} | Resource-bearing cells: {len(self.resources)}")
        return self.grid, self.seed

    def print_moisture_map(self):
        """Prints a simplified ASCII map of humidity to the terminal."""
        print(f"\n--- Humity map: {self.name} ---")
        # Characteristics ranging from the driest (desert) to the wettest (forest/water)
        shades = " .:-=+*#%@"
        
        for y, row in enumerate(self.moisture):
            line = ""
            for x, val in enumerate(row):
                if self.water[y][x]:
                    line += "\033[34mW\033[0m" # Blue for water
                else:
                    # Maps the value [0.0, 1.0] to the index of the characters
                    idx = int(val * (len(shades) - 1))
                    line += shades[idx]
            print(line)
        print("Legend: ' ' (very dry) and '@' (very wet) | 'W' Water")



def print_map(grid, moisture=False):
    view = TerminalRenderer()
    view.__dict__.update(grid.__dict__)
    if moisture:
        view.print_moisture_map()
    else:
        view.print_grid()
