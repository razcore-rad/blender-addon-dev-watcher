from . import utils
from .dependencies import ensure_dependencies


bl_info = {
    "name": "Addon Dev Watcher",
    "description": "Refreshes addons when detecting file changes",
    "author": "Răzvan C. Rădulescu (razcore-rad)",
    "version": (0, 2),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Tool",
    "warning": "",  # used for warning icon and text in addons panel
    "doc_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Development",
}

mods = []


def register():
    ensure_dependencies()
    from . import core

    mods.extend([core])
    utils.register(mods)


def unregister():
    utils.unregister(mods)
