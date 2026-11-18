"""Entity state; behavior belongs to simulation systems."""
from dataclasses import dataclass, field


@dataclass
class Entity:
    id: int
    name: str
    location: tuple[int, int]
    health: float = 100.0
    hunger: float = 0.0
    thirst: float = 0.0
    inventory: dict[str, int] = field(default_factory=dict)

    @property
    def alive(self):
        return self.health > 0
