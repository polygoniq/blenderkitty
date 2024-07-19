# copyright (c) 2018- polygoniq xyz s.r.o.

from . import addon_updater
from . import addon_updater_ops
import bpy
import bpy.utils.previews
import aud
import mathutils
import os
import random
import functools
import typing
import logging
from . import polib

logger = logging.getLogger(f"polygoniq.{__name__}")

telemetry = polib.get_telemetry("blenderkitty")
icon_manager = polib.preview_manager_bpy.PreviewManager()
icon_manager.add_preview_path(os.path.join(os.path.dirname(__file__), "icons"))


MODULE_CLASSES: typing.List[typing.Type] = []


CAT_TEXTS: typing.Mapping[int, str] = {
    1: "Just increase the\nlight intensity a bit!",
    2: "Scale Z 2 Enter",
    3: "Imma just take\na little nap...",
    4: "They see me rollin',\nthey hatin'",
    5: "I can only show you\nthe Documentation.\nYou're the one that\nhas to walk through it.",
    6: "Cycles X render\nkernels be like:",
    7: "There Is A Great\nDisturbance\nIn The Force.",
    8: "It's getting cold,\nplease start\nrendering already.",
    9: "Maybe I should\nbuy a boat.",
    10: "I didn't delete\nyour changes,\nI promise!",
    11: "I am not a cat judge\nand I'm prepared to\ngo forward with it.",
    12: "Is this a webcam?",
    13: "What seems to be\nthe officer, problem?",
    14: "Working on the\nproject for 10h be like:",
    15: "Just scale the parent,\nI swear it works!",
    16: "Extrude along normal.",
}


def is_blenderkitty_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    if not os.path.isdir(os.path.join(path, "cats")):
        return False

    return True


def autodetect_install_path() -> str:
    return polib.utils_bpy.autodetect_install_path("blenderkitty", __file__, is_blenderkitty_dir)


@functools.lru_cache(maxsize=32)
def get_cat_enum_items(image_path):
    if getattr(get_cat_enum_items, "pcoll", None) is None:
        get_cat_enum_items.pcoll = bpy.utils.previews.new()

    ret = {"enum_items": [], "pcoll": get_cat_enum_items.pcoll}
    for i, filename in enumerate(sorted(os.listdir(image_path))):
        if not filename.endswith(".png"):
            continue

        full_path = os.path.join(image_path, filename)
        if not os.path.exists(full_path):
            logger.warning(f"{full_path} not found! Skipping this cat image!")
            continue

        image_name = filename

        if image_name in ret["pcoll"]:
            image = ret["pcoll"][image_name]
        else:
            image = ret["pcoll"].load(image_name, full_path, 'IMAGE')

        ret["enum_items"].append((image_name, f"{i}", image_name, image.icon_id, i))

    return ret


def get_cat_enum_items_context(context):
    prefs = get_preferences(context)
    return get_cat_enum_items(prefs.cats_path)


class ShowReleaseNotes(bpy.types.Operator):
    bl_idname = "blenderkitty.show_release_notes"
    bl_label = "Show Release Notes"
    bl_description = "Show the release notes for the latest version of blenderkitty"
    bl_options = {'REGISTER'}

    release_tag: bpy.props.StringProperty(
        name="Release Tag",
        default="",
    )

    def execute(self, context: bpy.types.Context):
        polib.ui_bpy.show_release_notes_popup(context, __package__, self.release_tag)
        return {'FINISHED'}


MODULE_CLASSES.append(ShowReleaseNotes)


@polib.log_helpers_bpy.logged_preferences
@addon_updater_ops.make_annotations
class Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    # Addon updater preferences.
    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=True,
    )

    updater_interval_months: bpy.props.IntProperty(
        name='Months', description="Number of months between checking for updates", default=0, min=0
    )

    updater_interval_days: bpy.props.IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31,
    )

    updater_interval_hours: bpy.props.IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )

    updater_interval_minutes: bpy.props.IntProperty(
        name='Minutes',
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )

    blenderkitty_path: bpy.props.StringProperty(
        name="blenderkitty_path",
        subtype="DIR_PATH",
        default=autodetect_install_path(),
        update=lambda self, context: polib.utils_bpy.absolutize_preferences_path(
            self, context, "blenderkitty_path"
        ),
    )

    cat: bpy.props.EnumProperty(
        name="Cat", items=lambda self, context: get_cat_enum_items_context(context)["enum_items"]
    )

    settings_expanded: bpy.props.BoolProperty(
        name="Settings Expanded",
        default=False,
        description="Whether settings are expanded in the main panel",
    )

    sounds_enabled: bpy.props.BoolProperty(
        name="Sounds Enabled",
        default=True,
        description="Play a random cute cat sound every time the cat image changes",
    )

    sound_volume: bpy.props.FloatProperty(
        name="Sound Volume [0.0-1.0]",
        default=0.3,
        min=0.0,
        max=1.0,
        description="How loud the cat sounds should be if enabled",
    )

    min_refresh_interval: bpy.props.FloatProperty(
        name="Min interval for refresh [s]",
        default=10.0,
        min=0.0,
        description="Minimal interval in seconds between cat image changes",
    )

    max_refresh_interval: bpy.props.FloatProperty(
        name="Max interval for refresh [s]",
        default=30.0,
        min=0.0,
        description="Maximal interval in seconds between cat image changes",
    )

    sound_device: typing.Optional[aud.Device] = None

    def play_sound(
        self,
        sound_path: str,
        distance: float = 20.0,
        vec: typing.Tuple[float, float, float] = (1.0, 0.0, 0.0),
        stop_after: typing.Optional[float] = None,
    ) -> None:
        if not self.sounds_enabled:
            logger.debug("Sounds are disabled, but requested to play sound!")
            return

        # We store all these variables as class variables to avoid their reference
        # count dropping to zero before we are finished playing the sound.
        if Preferences.sound_device is None:
            Preferences.sound_device = aud.Device()
        try:
            Preferences.sound = aud.Sound(sound_path)
            Preferences.sound_cache = aud.Sound.cache(Preferences.sound)
            Preferences.sound_handle = Preferences.sound_device.play(Preferences.sound_cache)
            # this is the number of loops remaining, since we are already playing the sound
            # the number of loops remaining must be 0 to avoid looping at all
            Preferences.sound_handle.loop_count = 0
            Preferences.sound_handle.volume = self.sound_volume
            mag = sum(x**2 for x in vec) ** 0.5
            direction = [x / mag for x in vec]
            Preferences.sound_handle.location = mathutils.Vector(
                (direction[0] * distance, direction[1] * distance, direction[2] * distance)
            )

            if stop_after is not None:
                bpy.app.timers.register(
                    Preferences.sound_handle.stop, first_interval=stop_after, persistent=False
                )

        except aud.error:
            # this could fail if no sound device is available
            pass

    def play_random_sound(self, context: bpy.types.Context):
        if not os.path.isdir(self.random_sounds_path):
            logger.error(
                f"Sound directory {self.random_sounds_path} was not found or is not a directory!"
            )
            return

        sounds = [x for x in os.listdir(self.random_sounds_path) if x.endswith(".ogg")]
        sound_path: str = os.path.join(self.random_sounds_path, random.choice(sounds))
        if not os.path.isfile(sound_path):
            logger.error(f"Wanted to play sound {sound_path} but the file was not found!")
            return

        self.play_sound(
            sound_path,
            random.uniform(30.0, 100.0),
            (random.gauss(0.0, 1.0), random.gauss(0.0, 1.0), random.gauss(0.0, 1.0)),
        )

    def ensure_valid_enum_items(self, context):
        cat_enum_items = get_cat_enum_items_context(context)["enum_items"]
        if self.cat is None:
            try:
                self.cat = cat_enum_items[0][0]
            except:
                pass

        else:
            if self.cat not in [x[0] for x in cat_enum_items]:
                self.cat = cat_enum_items["enum_items"][0][0]

    def randomize_cat(self, context: bpy.types.Context):
        cats_enum_items = get_cat_enum_items_context(context)["enum_items"]
        choice = random.choice(cats_enum_items)[0]
        self.cat = choice
        self.play_random_sound(context)
        self.ensure_valid_enum_items(context)

    def draw(self, context):
        self.layout.prop(self, "sounds_enabled")
        self.layout.prop(self, "sound_volume")
        self.layout.prop(self, "min_refresh_interval")
        self.layout.prop(self, "max_refresh_interval")

        row = self.layout.row()
        row.operator(PackLogs.bl_idname, icon='EXPERIMENTAL')

        self.layout.separator()
        row = self.layout.row()
        col = row.column()

        if bpy.app.version < (4, 2, 0) or (bpy.app.version >= (4, 2, 0) and bpy.app.online_access):
            self.draw_update_settings(context, col)

        polib.ui_bpy.draw_settings_footer(self.layout)

    def draw_update_settings(self, context: bpy.types.Context, layout: bpy.types.UILayout) -> None:
        col = layout.column()
        addon_updater_ops.update_settings_ui(self, context, col)
        split = col.split(factor=0.5)
        left_row = split.row()
        left_row.enabled = bool(addon_updater.Updater.update_ready)
        left_row.operator(
            ShowReleaseNotes.bl_idname, text="Latest Release Notes", icon='PRESET_NEW'
        ).release_tag = ""
        right_row = split.row()
        current_release_tag = polib.utils_bpy.get_release_tag_from_version(
            addon_updater.Updater.current_version
        )
        right_row.operator(
            ShowReleaseNotes.bl_idname, text="Current Release Notes", icon='PRESET'
        ).release_tag = current_release_tag

    @property
    def install_path(self) -> str:
        return os.path.abspath(bpy.path.abspath(self.blenderkitty_path))

    @property
    def cats_path(self):
        return os.path.join(self.install_path, "cats")

    @property
    def sounds_path(self):
        return os.path.join(self.install_path, "sounds")

    @property
    def random_sounds_path(self):
        return os.path.join(self.sounds_path, "random")


MODULE_CLASSES.append(Preferences)


@polib.log_helpers_bpy.logged_operator
class PackLogs(bpy.types.Operator):
    bl_idname = "blenderkitty.pack_logs"
    bl_label = "Pack Logs"
    bl_description = "Archives polygoniq logs as zip file and opens its location"
    bl_options = {'REGISTER'}

    def execute(self, context):
        packed_logs_directory_path = polib.log_helpers_bpy.pack_logs(telemetry)
        polib.utils_bpy.xdg_open_file(packed_logs_directory_path)
        return {'FINISHED'}


MODULE_CLASSES.append(PackLogs)


def get_preferences(context: bpy.types.Context) -> Preferences:
    return context.preferences.addons[__package__].preferences


def register():
    for cls in MODULE_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(MODULE_CLASSES):
        bpy.utils.unregister_class(cls)

    pcoll = getattr(get_cat_enum_items, "pcoll", None)
    if pcoll is not None:
        bpy.utils.previews.remove(pcoll)
        setattr(get_cat_enum_items, "pcoll", None)

    # Delete the icon_manager to close the preview collection and allow previews to free
    global icon_manager
    del icon_manager
