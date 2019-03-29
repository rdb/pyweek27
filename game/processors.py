from direct.showbase.DirectObject import DirectObject
from direct.interval.IntervalGlobal import LerpFunctionInterval, Func, Sequence, Parallel, Wait
from panda3d import core
import esper
import math

from .level import TileType
from . import components


MOUSE_SENSITIVITY = 0.3


class PlayerControl(esper.Processor, DirectObject):
    def __init__(self, player, camera):
        self.player = player
        self.camera = camera

        self.accept('arrow_up', self.move_up)
        self.accept('arrow_down', self.move_down)
        self.accept('arrow_left', self.move_left)
        self.accept('arrow_right', self.move_right)
        self.accept('mouse1', self.start_drag)
        self.accept('mouse1-up', self.stop_drag)
        self.accept('r', self.reload)

        self.locked = True
        self.moving = False
        self.winning_move = False
        self.dragging_pos = None
        self.restore_interval = None
        self.cracked_tile = None
        self.button_tile = None
        self.reload = False

    def lock(self):
        # Locks the controls
        self.locked = True
        if self.dragging_pos:
            self.stop_drag()

    def unlock(self):
        self.locked = False
        assert self.world.level

    def reload(self):
        if self.locked:
            return

        self.reload = True

    def start_drag(self):
        if self.restore_interval:
            self.restore_interval.pause()
            self.restore_interval = None

        ptr = base.win.get_pointer(0)
        if ptr.in_window:
            self.dragging_pos = ptr.x, ptr.y

    def stop_drag(self):
        if self.dragging_pos:
            self.dragging_pos = None

            spatial = self.world.component_for_entity(self.camera, components.Spatial)
            self.restore_interval = spatial.path.hprInterval(0.3, spatial.default_hpr, blendType='easeOut')
            self.restore_interval.start()

    def move_up(self):
        if self.locked:
            return
        die = self.world.component_for_entity(self.player, components.Die)
        die.move_up()

    def move_down(self):
        if self.locked:
            return
        die = self.world.component_for_entity(self.player, components.Die)
        die.move_down()

    def move_left(self):
        if self.locked:
            return
        die = self.world.component_for_entity(self.player, components.Die)
        die.move_left()

    def move_right(self):
        if self.locked:
            return
        die = self.world.component_for_entity(self.player, components.Die)
        die.move_right()

    def start_move(self, dir):
        die = self.world.component_for_entity(self.player, components.Die)
        spatial = self.world.component_for_entity(self.player, components.Spatial)

        orig_pos = spatial.path.get_pos()
        orig_quat = spatial.path.get_quat()
        target_pos = spatial.path.get_pos()
        target_quat = spatial.path.get_quat()
        next_number = None
        vector = core.Vec2(0, 0)
        if dir == 'N':
            vector.y += 1
            target_quat *= core.LRotation((1, 0, 0), -90)
            next_number = die.die.north_number
        elif dir == 'E':
            vector.x += 1
            target_quat *= core.LRotation((0, 1, 0), 90)
            next_number = die.die.east_number
        elif dir == 'S':
            vector.y -= 1
            target_quat *= core.LRotation((1, 0, 0), 90)
            next_number = die.die.south_number
        elif dir == 'W':
            vector.x -= 1
            target_quat *= core.LRotation((0, 1, 0), -90)
            next_number = die.die.west_number

        z_scale = math.sqrt(0.5) - 0.5

        target_pos.xy += vector
        x, y = int(target_pos[0]), int(target_pos[1])
        type = self.world.level.get_tile(x, y)
        if not type.is_passable(next_number, self.world.toggle_state) and not base.mouseWatcherNode.is_button_down('pause'):
            self.moving = True
            Sequence(
                Parallel(
                    spatial.path.posInterval(0.05, orig_pos * 0.9 + target_pos * 0.1, blendType='easeInOut'),
                    LerpFunctionInterval(lambda x: spatial.path.set_z(math.sin(x) * z_scale), 0.05, toData=math.pi * 0.1, blendType='easeInOut'),
                    spatial.path.quatInterval(0.05, orig_quat * 0.9 + target_quat * 0.1, blendType='easeInOut'),
                ),
                Parallel(
                    spatial.path.posInterval(0.05, orig_pos, blendType='easeIn'),
                    LerpFunctionInterval(lambda x: spatial.path.set_z(math.sin(x) * z_scale), 0.05, fromData=math.pi * 0.1, toData=0, blendType='easeIn'),
                    spatial.path.quatInterval(0.05, orig_quat, blendType='easeIn'),
                ),
                Func(self.stop_move)).start()
            return False

        # Build up the animation; the parallel gets prepended to the sequence
        parallel = [
            spatial.path.posInterval(0.25, target_pos),
            LerpFunctionInterval(lambda x: spatial.path.set_z(math.sin(x) * z_scale), 0.25, toData=math.pi),
            spatial.path.quatInterval(0.25, target_quat),
        ]
        sequence = []

        while type == TileType.ice:
            target_pos.xy += vector
            x, y = int(target_pos[0]), int(target_pos[1])
            type = self.world.level.get_tile(x, y)

            if type == TileType.ice:
                sequence.append(spatial.path.posInterval(0.25, target_pos))
            else:
                sequence.append(spatial.path.posInterval(0.5, target_pos, blendType='easeOut'))

        if type == TileType.teleporter:
            # Find other teleporter.
            others = set(self.world.teleporters)
            others.discard(tuple(target_pos.xy))
            if others:
                target_pos.xy = others.pop()
                sequence.append(spatial.path.posInterval(0.0, target_pos))

        if self.button_tile:
            # Make the button raised again
            button_path = self.world.component_for_entity(self.button_tile, components.Spatial).path
            button_pos = core.LPoint3(button_path.get_pos())
            button_pos.z = 0.07
            parallel.append(button_path.posInterval(0.25, button_pos))

        if self.cracked_tile:
            # Break away the cracked tile
            self.world.add_component(self.cracked_tile, components.Falling(drag=5.0))
            self.cracked_tile = None

        if type == TileType.exit:
            self.winning_move = True
            self.lock()

        if type == TileType.cracked:
            self.cracked_tile = self.world.tiles[(x, y)]
            self.world.level.remove_tile(x, y)
            del self.world.tiles[(x, y)]

        if type == TileType.button:
            button_tile = self.world.tiles[(x, y)]
            button_path = self.world.component_for_entity(button_tile, components.Spatial).path
            button_pos = core.LPoint3(button_path.get_pos())
            button_pos.z = 0.0
            parallel.append(button_path.posInterval(0.25, button_pos))
            parallel.append(Sequence(Wait(0.1), Func(self.world.toggle_button)))
            self.button_tile = button_tile

        if dir == 'N':
            die.die.rotate_north()
        elif dir == 'E':
            die.die.rotate_east()
        elif dir == 'S':
            die.die.rotate_south()
        elif dir == 'W':
            die.die.rotate_west()

        self.moving = True

        sequence.insert(0, Parallel(*parallel))

        sequence.append(Func(self.stop_move))
        Sequence(*sequence).start()

        return True

    def stop_move(self):
        if self.winning_move:
            self.lock()
            self.world.win_level()
            self.winning_move = False

        self.moving = False

    def process(self, dt):
        if self.locked or self.moving:
            return

        die = self.world.component_for_entity(self.player, components.Die)
        spatial = self.world.component_for_entity(self.player, components.Spatial)

        if self.reload:
            self.reload = False
            die.moves.clear()
            self.world.reload_level()
            return

        if self.dragging_pos:
            ptr = base.win.get_pointer(0)
            if ptr.in_window:
                x = (self.dragging_pos[0] - ptr.x) * MOUSE_SENSITIVITY
                y = (self.dragging_pos[1] - ptr.y) * MOUSE_SENSITIVITY
                spatial = self.world.component_for_entity(self.camera, components.Spatial)
                spatial.path.set_hpr(spatial.default_hpr[0] + x, max(min(spatial.default_hpr[1] + y, 0), -90), 0)

        if die.moves:
            if not self.start_move(die.moves.pop(0)):
                die.moves.clear()


class Gravity(esper.Processor):
    def __init__(self, acceleration=1.0):
        self.acceleration = 1.0

    def process(self, dt):
        removed = []

        for ent, (spatial, fall) in self.world.get_components(components.Spatial, components.Falling):
            fall.velocity += self.acceleration * dt * fall.drag

            spatial.path.set_z(spatial.path.get_z() - fall.velocity * dt)

            spatial.path.set_p(spatial.path.get_p() + dt)

            if spatial.path.get_z() < -35:
                removed.append(ent)

        for ent in removed:
            self.world.delete_entity(ent)
