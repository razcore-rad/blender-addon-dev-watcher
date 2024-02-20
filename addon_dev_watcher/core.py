import addon_utils
import logging
import bpy

from importlib import reload, import_module
from functools import partial
from queue import Queue
from pathlib import Path
from types import ModuleType
from typing import Iterator

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import Context, Operator, Panel, PropertyGroup, UIList, UILayout, Scene
from bpy.utils import register_class, unregister_class

from .paths import ADDON_PATH, BLACKLIST_DIR


MODULE_NAME = ADDON_PATH.name

addon_modules = []
watched_addon_modules = set([MODULE_NAME])
observers = {}
queue = Queue()


def get_addon_modules_sorted() -> list[dict]:
    return sorted(
        [
            {"module": mod, "info": addon_utils.module_bl_info(mod)}
            for mod in addon_utils.modules(refresh=False)
            if not mod.__file__.startswith(BLACKLIST_DIR)
        ],
        key=lambda d: d["info"]["name"].upper(),
    )


def get_addon_modules_by_name(name: str) -> Iterator[str]:
    return (d for d in addon_modules if d["module"].__name__ == name)


def execute_queue() -> None:
    while not queue.empty():
        function = queue.get()
        function()


def _reload(module, reload_all, reloaded):
    if isinstance(module, ModuleType):
        module_name = module.__name__
    elif isinstance(module, str):
        module_name, module = module, import_module(module)
    else:
        raise TypeError("'module' must be either a module or str; " f"got: {module.__class__.__name__}")

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        check = (
            # is it a module?
            isinstance(attr, ModuleType)
            # has it already been reloaded?
            and attr.__name__ not in reloaded
            # is it a proper submodule? (or just reload all)
            and (reload_all or attr.__name__.startswith(module_name))
        )
        if check:
            _reload(attr, reload_all, reloaded)
    reload(import_module(module_name))
    reloaded.add(module_name)


def reload_recursive(module, reload_external_modules=False):
    """
    Recursively reload a module (in order of dependence).

    Parameters
    ----------
    module : ModuleType or str
        The module to reload.

    reload_external_modules : bool, optional

        Whether to reload all referenced modules, including external ones which
        aren't submodules of ``module``.

    """
    module_name = module.__name__ if isinstance(module, ModuleType) else module
    bpy.ops.preferences.addon_disable(module=module_name)
    _reload(module, reload_external_modules, set())
    bpy.ops.preferences.addon_enable(module=module_name)


def reload_module(name) -> None:
    queue.put(partial(reload_recursive, name))
    bpy.app.timers.register(execute_queue)


def observe(module_name: str, module_file: str | Path) -> None:
    file = Path(module_file).resolve()
    is_single_file = file.name != "__init__.py"
    event_handler = PatternMatchingEventHandler(
        patterns=[file.name if is_single_file else "*.py"],
        ignore_directories=True,
        case_sensitive=True,
    )
    event_handler.on_modified = lambda event: reload_module(module_name)
    observer = Observer()
    observer.schedule(event_handler, file.parent, recursive=not is_single_file)
    observer.start()
    observers.update({module_name: observer})


class WatchAddonModuleItem(PropertyGroup):
    name: StringProperty()


class WATCH_UL_Addons(UIList):
    def __init__(self) -> None:
        super().__init__()
        self.use_filter_show = self.list_id != "watched"

    def draw_item(
        self,
        context: Context,
        layout: UILayout,
        data: Scene,
        item: str,
        icon: int,
        active_data: Scene,
        active_propname: int,
    ):
        for d in get_addon_modules_by_name(item.name):
            text = d["info"]["name"]
            if self.layout_type in {"DEFAULT", "COMPACT"}:
                layout.label(text=text, translate=False, icon_value=icon)
            elif self.layout_type == "GRID":
                layout.alignment = "CENTER"
                layout.label(text=text, icon_value=icon)
            break


class WATCH_OT_AddWatch(Operator):
    bl_idname = "watch.add"
    bl_label = "Add Watch"

    def execute(self, context: Context) -> None:
        scene = context.scene
        addon_module = scene.watch_addon_modules[scene.watch_addon_module_index]
        watched_addon_modules.add(addon_module.name)
        scene.watch_addon_module_index -= 1
        for d in get_addon_modules_by_name(addon_module.name):
            observe(d["module"].__name__, d["module"].__file__)
        return {"FINISHED"}


class WATCH_OT_RemoveWatch(Operator):
    bl_idname = "watch.remove"
    bl_label = "Remove Watch"

    @classmethod
    def poll(cls, context: Context) -> bool:
        scene = context.scene
        result = scene.watch_watched_addon_module_index <= len(scene.watch_watched_addon_modules)
        if result and scene.watch_watched_addon_modules:
            name = scene.watch_watched_addon_modules[scene.watch_watched_addon_module_index].name
            result = name != MODULE_NAME
        return result

    def execute(self, context: Context) -> None:
        scene = context.scene
        watched_addon_module = scene.watch_watched_addon_modules[scene.watch_watched_addon_module_index]
        watched_addon_modules.discard(watched_addon_module.name)
        scene.watch_watched_addon_module_index -= 1
        if watched_addon_module.name in observers:
            observers[watched_addon_module.name].stop()
            observers[watched_addon_module.name].join()
            del observers[watched_addon_module.name]
        return {"FINISHED"}


class WATCH_PT_PanelBase(Panel):
    """Creates a Panel in the Object properties window"""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"
    bl_label = "Addon Dev Watcher"

    def __init__(self):
        try:
            super().__init__()
            self.layout.use_property_decorate = False
            global addon_modules
            addon_modules = get_addon_modules_sorted()

            bpy.context.scene.watch_addon_modules.clear()
            for addon_module in addon_modules:
                if addon_module["module"].__name__ in watched_addon_modules:
                    continue
                item = bpy.context.scene.watch_addon_modules.add()
                item.name = addon_module["module"].__name__

            bpy.context.scene.watch_watched_addon_modules.clear()
            for watch_addon_module in sorted(watched_addon_modules):
                item = bpy.context.scene.watch_watched_addon_modules.add()
                item.name = watch_addon_module
        except AttributeError:
            pass

    def draw(self, context: Context):
        self.layout.label(text="Addons:")
        self.layout.template_list(
            "WATCH_UL_Addons",
            "",
            context.scene,
            "watch_addon_modules",
            context.scene,
            "watch_addon_module_index",
        )
        self.layout.operator("watch.add")
        self.layout.label(text="Watching:")
        for watched_addon_module in context.scene.watch_watched_addon_modules:
            for d in get_addon_modules_by_name(watched_addon_module):
                self.layout.label(text=d["info"]["name"])

        self.layout.template_list(
            "WATCH_UL_Addons",
            "watched",
            context.scene,
            "watch_watched_addon_modules",
            context.scene,
            "watch_watched_addon_module_index",
        )
        self.layout.operator("watch.remove")


CLASSES = [
    WatchAddonModuleItem,
    WATCH_OT_AddWatch,
    WATCH_OT_RemoveWatch,
    WATCH_UL_Addons,
    WATCH_PT_PanelBase,
]


def register():
    logging.getLogger("watchdog").setLevel(logging.INFO)
    for cls in CLASSES:
        register_class(cls)
    Scene.watch_addon_modules = CollectionProperty(type=WatchAddonModuleItem)
    Scene.watch_addon_module_index = IntProperty()
    Scene.watch_watched_addon_modules = CollectionProperty(type=WatchAddonModuleItem)
    Scene.watch_watched_addon_module_index = IntProperty()
    observe(ADDON_PATH.name, ADDON_PATH / "__init__.py")


def unregister():
    for cls in CLASSES:
        unregister_class(cls)
    del Scene.watch_addon_modules
    del Scene.watch_addon_module_index
    del Scene.watch_watched_addon_modules
    del Scene.watch_watched_addon_module_index
    for observer in observers.values():
        observer.stop()
