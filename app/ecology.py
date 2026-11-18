"""Terrain ecology system; operates on shared grid layers."""


class Ecology:
    FOREST_BIOMES = frozenset(("taiga", "boreal_forest", "temperate_forest", "temperate_rainforest", "tropical_seasonal_forest", "tropical_rainforest"))
    def calculate_slopes(self):
        self.slope = [
            [max((abs(self.elevation[y][x] - self.elevation[ny][nx])
                  for nx, ny in self._neighbors(x, y)), default=0.0)
             for x in range(self.width)] for y in range(self.height)]

    def get_landform(self, x, y):
        if self.water[y][x]:
            return "submerged"

        elevation = self.elevation[y][x]
        slope = self.slope[y][x]

        if elevation >= 0.8:
            return "mountain"
        elif elevation >= 0.6 and slope < 0.1:
            return "plateau"
        elif slope >= 0.2:
            return "cliff"
        elif slope >= 0.1:
            return "slope"
        
        return "plain"

    def get_shore_type(self, x, y):
        if self.water[y][x]:
            return None

        if self.distance_to_water[y][x] <= 2:
            slope = self.slope[y][x]
            elevation = self.elevation[y][x]

            if slope >= 0.2:
                return "rocky_cliff"
            elif elevation <= self.sea_level + 0.05:
                return "beach"
            else:
                return "wetland"

        return "inland"

    def classify_biomes(self):
        self.biomes = [[None] * self.width for _ in range(self.height)]

        for y in range(self.height):
            for x in range(self.width):
                if self.water[y][x]:
                    biome = 'water'
                else:
                    landform = self.get_landform(x, y)
                    temp = self.get_temperature_index(x, y)     # 0.0 (cold/polar) to 1.0 (hot/tropical)
                    moisture = self.moisture[y][x]              # 0.0 (dry) to 1.0 (wet)
                    shore = self.get_shore_type(x, y)

                    # 1. Rules concerning extreme terrain and coastal areas take precedence
                    if landform == 'mountain':
                        biome = 'alpine' if temp < 0.3 else 'mountain'
                    elif shore == 'beach':
                        biome = 'beach'
                    elif shore == 'rocky_cliff':
                        biome = 'cliff'

                    # 2. Temperature-based rules (Extreme Cold / Polar and Alpine)
                    elif temp < 0.2:
                        biome = 'polar_desert' if moisture < 0.3 else 'tundra'

                    # 3. Rules based on Cold/Moderate Climate (Taiga / Boreal)
                    elif temp < 0.4:
                        if moisture < 0.3:
                            biome = 'cold_steppe'
                        elif moisture > 0.6:
                            biome = 'taiga'
                        else:
                            biome = 'boreal_forest'

                    # 4. Rules based on a Temperate Climate
                    elif temp < 0.7:
                        if moisture < 0.25:
                            biome = 'desert'
                        elif moisture < 0.45:
                            biome = 'grassland'
                        elif moisture < 0.75:
                            biome = 'temperate_forest'
                        else:
                            biome = 'temperate_rainforest'
                            
                    # 5. Rules based on Hot / Tropical Climates
                    else:
                        if moisture < 0.25:
                            biome = 'hot_desert'
                        elif moisture < 0.50:
                            biome = 'savanna'
                        elif moisture < 0.80:
                            biome = 'tropical_seasonal_forest'
                        else:
                            biome = 'tropical_rainforest'

                self.biomes[y][x] = biome

    def place_vegetation(self):
        """Place trees/cacti using biome, regional density, temperature and slope.

        Bare, polar and alpine biomes have no supported vegetation symbol.
        Grass/shrub ground cover remains represented by the biome itself.
        These probabilities are initial gameplay parameters, not ecological rates.
        """
        density = self._noise(max(2, min(self.width, self.height) / 8))
        self.vegetation = [[None] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                biome, chance = self.biomes[y][x], self.rng.random()
                if self.water[y][x] or self.slope[y][x] >= 0.2:
                    continue
                temperature = self.get_temperature_index(x, y)
                slope_factor = max(0.0, 1.0 - self.slope[y][x] / 0.2)
                tree_chance = self.TREE_DENSITIES.get(biome, 0.0) * density[y][x] * slope_factor
                if temperature >= 0.2 and chance < tree_chance:
                    self.vegetation[y][x] = 'tree'
                elif biome in ('desert', 'hot_desert') and temperature >= 0.4:
                    cactus_chance = 0.08 * (0.5 + 0.5 * density[y][x]) * slope_factor
                    if chance < cactus_chance:
                        self.vegetation[y][x] = 'cactus'

    def generate_resources(self):
        self.resources = {}

        # Generate abundance for each resource type based on biome and noise
        abundance = self._noise(max(2, min(self.width, self.height) / 6))

        for y in range(self.height):
            for x in range(self.width):
                biome = self.biomes[y][x]
                vegetation = self.vegetation[y][x]
                richness = abundance[y][x]
                deposits = {}

                # Food: more abundant in forests with trees
                if biome in self.FOREST_BIOMES:
                    chance = 0.3 if vegetation == "tree" else 0.1
                    if self.rng.random() < chance * richness:
                        deposits["food"] = self.rng.randint(2, 8)

                elif biome == "grassland":
                    if self.rng.random() < 0.08 * richness:
                        deposits["food"] = self.rng.randint(1, 3)

                # Wood: more abundant in forests with trees
                if vegetation == "tree":
                    if biome in self.FOREST_BIOMES:
                        deposits["wood"] = self.rng.randint(5, 10)
                    elif biome == "grassland":
                        if self.rng.random() < 0.05 * richness:
                            deposits["wood"] = self.rng.randint(1, 3)

                # Ore: more abundant in mountains and slopes
                if self.get_landform(x, y) in ("mountain", "slope", "cliff"):
                    chance = 0.45 if self.get_landform(x, y) == "mountain" else 0.2

                    if richness > 0.55 and self.rng.random() < chance:
                        deposits["ore"] = int(5 + richness * 20)

                if deposits:
                    self.resources[(x, y)] = deposits

