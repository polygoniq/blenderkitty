# copyright (c) 2018- polygoniq xyz s.r.o.
# A drawer full of cats?

import abc
import bpy
import dataclasses
import gpu
import gpu_extras
import mathutils
import os
import typing
import random

from . import preferences


MODULE_CLASSES: typing.List[typing.Any] = []

CAT_NAMES = [
    "Tom",
    "Garfield",
    "Felix",
    "Snowball I",
    "Snowball II",
    "Snowball III",
    "Snowball IV",
    "Luna",
    "Oliver",
    "Choco",
    "Bobor",
    "Chomik",
    "Maugli",
    "Newton",
    "Merlin",
    "Ash",
    "Simba",
    "Kimba",
    "Mittens",
    "Micka",
    "Woofer",
    "Sir Dr. Catchmice The Second, Junior",
    "Junior",
    "Purrfect",
    "Neferu",
    "Loafie",
    "Jesterka",
    "Lord Loaf",
    "Whiskers",
    "Minty",
    "Mr. Paddington",
]


def _tag_redraw_view_3d():
    context = bpy.context
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def _find_largest_view_3d_size(context: bpy.types.Context) -> typing.Tuple[int, int]:
    all_view_3d = [area for area in context.screen.areas if area.type == 'VIEW_3D']
    if len(all_view_3d) == 0:
        return 0, 0

    largest = all_view_3d[0]
    for view_3d in all_view_3d[1:]:
        if view_3d.width * view_3d.height > largest.width * largest.height:
            largest = view_3d

    return largest.width, largest.height


class PNGSequencePlayer:
    def __init__(
        self,
        folder: str,
        frame_duration: float = 0.1,
    ):
        self.folder = folder
        self.frame_duration = frame_duration
        self.textures = []
        # We expect the previews to be numbered and named 0-N.png
        self.current_index = 0
        self.total_frames = 0
        self.texture_width = 0
        self.texture_height = 0
        self._load_as_textures()

    def __del__(self):
        if bpy.app.timers.is_registered(self._tick):
            bpy.app.timers.unregister(self._tick)

    def start_play(self):
        if self.total_frames == 0:
            raise RuntimeError("No frames loaded, can't play!")

        bpy.app.timers.register(self._tick, persistent=True)

    def get_current_texture(self) -> typing.Optional[gpu.types.GPUTexture]:
        if self.current_index < len(self.textures):
            return self.textures[self.current_index]
        else:
            return None

    def _tick(self) -> float:
        self.current_index = (self.current_index + 1) % self.total_frames
        return self.frame_duration

    def _load_as_textures(self):
        frames = os.listdir(self.folder)
        self.total_frames = len(frames)
        for img_file in sorted(frames, key=lambda x: int(os.path.splitext(x)[0])):
            # Load image
            img = bpy.data.images.load(os.path.join(self.folder, img_file))
            # Create GPU texture
            self.textures.append(gpu.texture.from_image(img))
            # Remove image, so it won't show in the Image list in the UI
            bpy.data.images.remove(img)

        # We assume the same size for all textures
        self.texture_width = self.textures[0].width
        self.texture_height = self.textures[0].height


@dataclasses.dataclass
class TickContext:
    context: typing.Optional[bpy.types.Context] = None
    event: typing.Optional[bpy.types.Event] = None
    # Largest of the 3d viewports
    view_3d_size: mathutils.Vector = mathutils.Vector((0, 0))


GLOBAL_TICK_CONTEXT = TickContext()


class Cat:
    def __init__(
        self,
        anim_folder: str,
        sound_file: typing.Optional[str] = None,
        duration: float = 5.0,
        frame_duration: float = 0.1,
    ):
        self.player = PNGSequencePlayer(anim_folder, frame_duration)
        self.sound_file = sound_file
        self.duration = duration
        self.type = os.path.basename(anim_folder)
        self.name = CAT_NAMES[random.randint(0, len(CAT_NAMES) - 1)]
        self.position: mathutils.Vector = mathutils.Vector((0, 0))

    def play(self, context: bpy.types.Context):
        if self.player is None:
            raise RuntimeError("Cat has already played, it is tired!")

        self.player.start_play()

    def stop(self):
        if self.player is None:
            raise RuntimeError("Cat is already asleep!")

        del self.player

    @abc.abstractmethod
    def tick(self, delta: float) -> None:
        pass

    def _clamp_position(self) -> None:
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        w_max = size.x - self.player.texture_width
        h_max = size.y - self.player.texture_height
        self.position.x = max(0, min(self.position.x, w_max))
        self.position.y = max(0, min(self.position.y, h_max))


class HappyCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "happy"),
            sound_file=None,
            duration=random.randint(5, 10),
            frame_duration=0.08,
        )
        self.offset = mathutils.Vector((random.uniform(-20.0, 20.0), random.uniform(-20.0, 20.0)))

    def tick(self, delta: float) -> None:
        # This cat follows cursor
        event = GLOBAL_TICK_CONTEXT.event
        if event is None or event.type != 'MOUSEMOVE':
            return

        self.position = self.offset + mathutils.Vector(
            (
                event.mouse_x - self.player.texture_width / 2.0,
                event.mouse_y - self.player.texture_height / 2.0,
            )
        )

        self._clamp_position()


class SpinningCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "spinning"),
            sound_file=None,
            duration=random.uniform(10.0, 30.0),
            frame_duration=0.04,
        )
        # speed / tick_rate = pixels per second
        # tick_rate = 10 ticks per s
        self.speed = random.uniform(200.0, 500.0)

    def play(self, context: bpy.types.Context):
        super().play(context)
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        self.position = mathutils.Vector(
            (
                random.randint(0, int(size.x - self.player.texture_width)),
                random.randint(0, int(size.y - self.player.texture_height)),
            )
        )

        self.velocity = mathutils.Vector(
            (1 if random.random() > 0.5 else -1, 1 if random.random() > 0.5 else -1)
        )
        self._clamp_position()

    def tick(self, delta: float) -> None:
        context = GLOBAL_TICK_CONTEXT.context
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        if context is None:
            return

        self.position += self.velocity * self.speed * delta
        # Bounce of the wall, the wall is defined by (0, 0) and (context.area.width, context.area.height)
        if self.position.x < 0 or self.position.x > size.x - self.player.texture_width:
            self.velocity.x *= -1

        if self.position.y < 0 or self.position.y > size.y - self.player.texture_height:
            self.velocity.y *= -1

        self._clamp_position()


class DancingCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "dancing"),
            sound_file=None,
            duration=random.uniform(10.0, 30.0),
            frame_duration=1,
        )
        # speed / tick_rate = pixels per second
        # tick_rate = 10 ticks per s
        # half of DancingCats are static
        if random.random() > 0.5:
            self.speed = 0
        else:
            self.speed = random.uniform(200.0, 400.0)

    def play(self, context: bpy.types.Context):
        super().play(context)
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        self.position = mathutils.Vector(
            (random.randint(0, int(size.x - self.player.texture_width)), 0)
        )

        self.velocity = mathutils.Vector((1 if random.random() > 0.5 else -1, 0))
        self._clamp_position()

    def tick(self, delta: float) -> None:
        context = GLOBAL_TICK_CONTEXT.context
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        if context is None:
            return

        self.position += self.velocity * self.speed * delta
        if self.position.x < 0 or self.position.x > size.x - self.player.texture_width:
            self.velocity.x *= -1

        self._clamp_position()


class PopCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "popcat"),
            sound_file=None,
            duration=random.uniform(10.0, 30.0),
            frame_duration=5,
        )

    def play(self, context: bpy.types.Context):
        super().play(context)
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        self.position = mathutils.Vector(
            (random.randint(0, int(size.x - self.player.texture_width)), 0)
        )


class GooglyCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "googly"),
            sound_file=None,
            duration=random.uniform(5.0, 15.0),
            frame_duration=0.2,
        )

    def play(self, context: bpy.types.Context):
        super().play(context)
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        self.position = mathutils.Vector(
            (random.randint(0, int(size.x - self.player.texture_width)), -50)
        )


class HangingCat(Cat):
    def __init__(self):
        super().__init__(
            os.path.join(os.path.dirname(__file__), "cats_anim", "hanging"),
            sound_file=None,
            duration=random.uniform(5.0, 15.0),
            frame_duration=0.2,
        )

    def play(self, context: bpy.types.Context):
        super().play(context)
        size = GLOBAL_TICK_CONTEXT.view_3d_size
        self.position = mathutils.Vector(
            (
                random.randint(0, int(size.x - self.player.texture_width)),
                size.y - self.player.texture_height + random.randint(10, 40),
            )
        )


class DrawerFullOfCats:
    def __init__(self, tick_rate: float = 1.0 / 30.0):
        self.available_cats = [HappyCat, SpinningCat, DancingCat, PopCat, GooglyCat, HangingCat]
        self.cats = []
        self.tick_rate = tick_rate
        bpy.app.timers.register(self.tick, persistent=True, first_interval=0.0)

    def open(self, context: bpy.types.Context) -> Cat:
        cat = self.available_cats[random.randint(0, len(self.available_cats) - 1)]()
        cat.play(context)
        self.cats.append(cat)
        bpy.app.timers.register(
            lambda: self.close(cat), persistent=True, first_interval=cat.duration
        )
        return cat

    def close(self, cat: Cat):
        cat.stop()
        self.cats.remove(cat)

    def draw(self):
        blend: str = gpu.state.blend_get()
        gpu.state.blend_set('ALPHA')

        for cat in self.cats:
            texture = cat.player.get_current_texture()
            gpu_extras.presets.draw_texture_2d(texture, cat.position, texture.width, texture.height)

        gpu.state.blend_set(blend)

        # Force redraw of 3D viewport (has to be out of loop)
        bpy.app.timers.register(_tag_redraw_view_3d, persistent=True, first_interval=0.0)

    def tick(self):
        for cat in self.cats:
            cat.tick(self.tick_rate)

        return self.tick_rate


CAT_DRAWER = DrawerFullOfCats()
_DRAW_HANDLER = None


class UpdateGlobalTickContext(bpy.types.Operator):
    bl_idname = "blenderkitty.update_global_tick_context"
    bl_label = "Update Global Tick Context"
    bl_description = "Update Global Tick Context"

    def execute(self, context: bpy.types.Context):
        return {'FINISHED'}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        GLOBAL_TICK_CONTEXT.context = context
        GLOBAL_TICK_CONTEXT.event = event
        GLOBAL_TICK_CONTEXT.view_3d_size = mathutils.Vector(_find_largest_view_3d_size(context))
        return {'PASS_THROUGH'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


MODULE_CLASSES.append(UpdateGlobalTickContext)


class OpenCatDrawer(bpy.types.Operator):
    bl_idname = "blenderkitty.open_drawer"
    bl_label = "Open Drawer"
    bl_description = "Pull one of the cats out of the drawer"
    bl_options = {'REGISTER'}

    # The index is used for the operator being at multiple places and having separate states
    index: bpy.props.IntProperty()

    # Default state is "o" - button of the drawer :)
    index_state_map: typing.Dict[int, str] = {}

    @classmethod
    def get_state(cls, index: int) -> str:
        return cls.index_state_map.get(index, "o")

    @classmethod
    def open(cls, context: bpy.types.Context, index: int):
        cat = CAT_DRAWER.open(context)
        cls.index_state_map[index] = f"Got: {cat.type.capitalize()} {cat.name}!"
        bpy.app.timers.register(lambda: cls.finish(index), first_interval=3.0)

    @classmethod
    def finish(cls, index: int):
        cls.index_state_map[index] = "o"

    @classmethod
    def add_dot(cls, index: int):
        assert index in cls.index_state_map
        cls.index_state_map[index] += "."

    def execute(self, context: bpy.types.Context):
        OpenCatDrawer.index_state_map[self.index] = "Opening"
        opening_time = random.uniform(3.0, 5.0)

        prefs = preferences.get_preferences(context)
        prefs.play_sound(os.path.join(prefs.sounds_path, "drawer.ogg"), stop_after=opening_time)

        bpy.app.timers.register(
            lambda: OpenCatDrawer.open(context, self.index), first_interval=opening_time
        )
        bpy.app.timers.register(
            lambda: OpenCatDrawer.add_dot(self.index), first_interval=opening_time * 0.2
        )
        bpy.app.timers.register(
            lambda: OpenCatDrawer.add_dot(self.index), first_interval=opening_time * 0.4
        )
        bpy.app.timers.register(
            lambda: OpenCatDrawer.add_dot(self.index), first_interval=opening_time * 0.8
        )
        return {'FINISHED'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        state = OpenCatDrawer.index_state_map.get(self.index, "o")
        if state != "o":
            return {'CANCELLED'}

        return self.execute(context)


MODULE_CLASSES.append(OpenCatDrawer)


def register():
    def _start_gathering_events():
        bpy.ops.blenderkitty.update_global_tick_context('INVOKE_DEFAULT')
        return None

    for cls in MODULE_CLASSES:
        bpy.utils.register_class(cls)

    global _DRAW_HANDLER
    _DRAW_HANDLER = bpy.types.SpaceView3D.draw_handler_add(
        CAT_DRAWER.draw, (), 'WINDOW', 'POST_PIXEL'
    )

    # Start the update_global_tick_context, right after registering blenderkitty
    bpy.app.timers.register(_start_gathering_events, first_interval=0.5, persistent=True)


def unregister():
    for cls in reversed(MODULE_CLASSES):
        bpy.utils.unregister_class(cls)

    global _DRAW_HANDLER
    if _DRAW_HANDLER is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_DRAW_HANDLER, 'WINDOW')
        _DRAW_HANDLER = None
