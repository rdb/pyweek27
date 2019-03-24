from panda3d import core
import esper

from . import components
from . import processors
from .level import Level

import os


class World(esper.World):
    def __init__(self):
        super().__init__(self)

        self.root = core.NodePath("world")

        # Create camera entity
        camera = self.create_entity()
        self.add_component(camera, components.Camera(base.camera, fov=90, pos=(-1, -1, 10), look_at=(5, 5, 0)))

        self.load_level("test")
        self.level = None

        self.tiles = []

        self.add_processor(processors.Movement())

    def load_level(self, name):
        level_dir = os.path.join(os.path.dirname(__file__), '..', 'levels')
        level = Level()
        level.read(os.path.join(level_dir, name + '.lvl'))
        self.level = level

        for x, y, type in level.get_tiles():
            tile = self.create_entity()

            self.add_component(tile, components.Spatial("tile", parent=self.root, pos=(x, y)))
            self.add_component(tile, components.Model(type + ".egg", scale=(1, 1, 1)))
