#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from . import addon_updater_ops
import bpy
import sys
import os
import random
import typing
import tempfile
import logging
import logging.handlers
import importlib

root_logger = logging.getLogger("polygoniq")
logger = logging.getLogger(f"polygoniq.{__name__}")
if not getattr(root_logger, "polygoniq_initialized", False):
    root_logger_formatter = logging.Formatter(
        "P%(process)d:%(asctime)s:%(name)s:%(levelname)s: [%(filename)s:%(lineno)d] %(message)s",
        "%H:%M:%S",
    )
    try:
        root_logger.setLevel(int(os.environ.get("POLYGONIQ_LOG_LEVEL", "20")))
    except (ValueError, TypeError):
        root_logger.setLevel(20)
    root_logger.propagate = False
    root_logger_stream_handler = logging.StreamHandler()
    root_logger_stream_handler.setFormatter(root_logger_formatter)
    root_logger.addHandler(root_logger_stream_handler)
    try:
        log_path = os.path.join(tempfile.gettempdir(), "polygoniq_logs")
        os.makedirs(log_path, exist_ok=True)
        root_logger_handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(log_path, f"blender_addons.txt"),
            when="h",
            interval=1,
            backupCount=2,
            utc=True,
        )
        root_logger_handler.setFormatter(root_logger_formatter)
        root_logger.addHandler(root_logger_handler)
    except:
        logger.exception(
            f"Can't create rotating log handler for polygoniq root logger "
            f"in module \"{__name__}\", file \"{__file__}\""
        )
    setattr(root_logger, "polygoniq_initialized", True)
    logger.info(
        f"polygoniq root logger initialized in module \"{__name__}\", file \"{__file__}\" -----"
    )


# To comply with extension encapsulation, after the addon initialization:
# - sys.path needs to stay the same as before the initialization
# - global namespace can not contain any additional modules outside of __package__

# Dependencies for all 'production' addons are shipped in folder `./python_deps`
# So we do the following:
# - Add `./python_deps` to sys.path
# - Import all dependencies to global namespace
# - Manually remap the dependencies from global namespace in sys.modules to a subpackage of __package__
# - Clear global namespace of remapped dependencies
# - Remove `./python_deps` from sys.path
# - For developer experience, import "real" dependencies again, only if TYPE_CHECKING is True

# See https://docs.blender.org/manual/en/4.2/extensions/addons.html#extensions-and-namespace
# for more details
ADDITIONAL_DEPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "python_deps"))
try:
    if os.path.isdir(ADDITIONAL_DEPS_DIR) and ADDITIONAL_DEPS_DIR not in sys.path:
        sys.path.insert(0, ADDITIONAL_DEPS_DIR)

    dependencies = {
        "polib",
        "hatchery",  # hatchery is a transitive dependency from polib, but we still need to move it
    }
    for dependency in dependencies:
        logger.debug(f"Importing additional dependency {dependency}")
        dependency_module = importlib.import_module(dependency)
        local_module_name = f"{__package__}.{dependency}"
        sys.modules[local_module_name] = dependency_module
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(tuple(dependencies)):
            del sys.modules[module_name]

    from . import polib
    from . import hatchery

    from . import preferences
    from . import cat_drawer

    if typing.TYPE_CHECKING:
        import polib
        import hatchery

finally:
    if ADDITIONAL_DEPS_DIR in sys.path:
        sys.path.remove(ADDITIONAL_DEPS_DIR)


bl_info = {
    "name": "blenderkitty",
    "author": "polygoniq xyz s.r.o.",
    "version": (2, 0, 1),
    "blender": (3, 3, 0),
    "location": "View3D > Sidebar > Item Tab",
    "description": "Cheers you up!",
    "category": "System",
}
telemetry = polib.get_telemetry("blenderkitty")
telemetry.report_addon(bl_info, __file__)


ADDON_CLASSES: typing.List[typing.Type] = []


@polib.log_helpers_bpy.logged_panel
class BlenderKittyPanel(bpy.types.Panel):
    bl_idname = "VIEW_3D_PT_blenderkitty"
    bl_label = "blenderkitty"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = "objectmode"
    bl_category = "Item"
    bl_order = 100

    def draw_header(self, context: bpy.types.Context):
        self.layout.template_icon(
            icon_value=preferences.icon_manager.get_polygoniq_addon_icon_id("blenderkitty"),
            scale=1.0,
        )

    @staticmethod
    def toggle_button(layout: bpy.types.UILayout, data, attribute: str, text: str = ""):
        layout.prop(
            data,
            attribute,
            text=text,
            icon='TRIA_DOWN' if getattr(data, attribute) else 'TRIA_RIGHT',
            icon_only=True,
            expand=True,
        )

    def draw(self, context: bpy.types.Context):
        prefs = preferences.get_preferences(context)
        prefs.ensure_valid_enum_items(context)

        # Draw the "cat drawer"
        box = self.layout.box()
        col = box.column()
        row = col.row().box()
        row.alignment = 'CENTER'
        row.label(text="THE CAT Drawer", icon='OUTLINER_COLLECTION')
        col = col.box().column(align=True)
        col.scale_y = 2.0
        col.operator(
            cat_drawer.OpenCatDrawer.bl_idname, text=cat_drawer.OpenCatDrawer.get_state(0)
        ).index = 0
        col.operator(
            cat_drawer.OpenCatDrawer.bl_idname, text=cat_drawer.OpenCatDrawer.get_state(1)
        ).index = 1
        col.operator(
            cat_drawer.OpenCatDrawer.bl_idname, text=cat_drawer.OpenCatDrawer.get_state(2)
        ).index = 2

        row = self.layout.row()
        row.template_icon_view(prefs, "cat", scale=8.0, scale_popup=6.0)
        number, _ = os.path.splitext(os.path.basename(prefs.cat))
        cat_text = preferences.CAT_TEXTS.get(int(number), "")
        col = self.layout.column(align=True)
        for line in cat_text.split("\n"):
            col.label(text=line)

        row = self.layout.row()
        BlenderKittyPanel.toggle_button(row, prefs, "settings_expanded")
        row.label(text="Cattings")
        if prefs.settings_expanded:
            row = self.layout.row()
            box = row.box()
            box.prop(prefs, "sounds_enabled")
            box.prop(prefs, "sound_volume")
            box.prop(prefs, "min_refresh_interval")
            box.prop(prefs, "max_refresh_interval")


ADDON_CLASSES.append(BlenderKittyPanel)


def blenderkitty_tick() -> None:
    prefs = preferences.get_preferences(bpy.context)
    prefs.randomize_cat(bpy.context)
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'UI':
                    region.tag_redraw()


def blenderkitty_tick_wrapper() -> float:
    blenderkitty_tick()

    prefs = preferences.get_preferences(bpy.context)
    if prefs is None:  # blenderkitty unregistered?
        return 0.0

    min_refresh_interval = abs(prefs.min_refresh_interval)
    max_refresh_interval = abs(prefs.max_refresh_interval)
    if min_refresh_interval > max_refresh_interval:
        min_refresh_interval, max_refresh_interval = max_refresh_interval, min_refresh_interval

    new_interval = random.uniform(min_refresh_interval, max_refresh_interval)
    return new_interval


def register():
    # We pass mock "bl_info" to the updater, since Blender 4.2.0 the "bl_info" is no longer
    # available in this scope.
    addon_updater_ops.register({"version": (2, 0, 1)})

    preferences.register()
    cat_drawer.register()

    for cls in ADDON_CLASSES:
        bpy.utils.register_class(cls)

    bpy.app.timers.register(blenderkitty_tick_wrapper, first_interval=10.0, persistent=True)


def unregister():
    for cls in reversed(ADDON_CLASSES):
        bpy.utils.unregister_class(cls)

    cat_drawer.unregister()
    preferences.unregister()

    # Remove all nested modules from module cache, more reliable than importlib.reload(..)
    # Idea by BD3D / Jacques Lucke
    for module_name in list(sys.modules.keys()):
        if module_name.startswith(__package__):
            del sys.modules[module_name]

    if bpy.app.timers.is_registered(blenderkitty_tick_wrapper):
        bpy.app.timers.unregister(blenderkitty_tick_wrapper)

    addon_updater_ops.unregister()
