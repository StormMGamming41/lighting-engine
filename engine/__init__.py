
# Hightest level class engine that communicates with the application code
# - Any engine specific stuff and vulkan stuff can reach reach here at max
# - These objects will not be exposed to the application code

from .platform.window import *
from .rhi.instance import RHIInstance
from .rhi.surface import RHISurface
from .rhi.debug_messenger import DebugMessenger
from .rhi.device import RHIDevice

class Engine:

    version: str = "0.0.1"

    def __init__(self, title: str, size: tuple[int, int], version: str = "1.0.0", resizable: bool = True, debug: bool = False):

        self.window = Window(title, size, resizable)
        self.title = title
        self.debug = debug
        self.app_version = version

        self.inst_exts = self.window.get_rquired_extensions()
        if debug: self.inst_exts.append("VK_EXT_debug_utils")
        self.instance = RHIInstance(self, self.inst_exts, ["VK_LAYER_KHRONOS_validation"] if debug else [])
        self.surface = RHISurface(self.window.get_surface(self.instance._handle), self.instance)

        if debug: self.debugger = DebugMessenger(self.instance)

        self.device = RHIDevice(self.instance, self.surface)
    
    def update(self):

        self.window.update()

    def cleanup(self):

        self.device.destroy()

        if self.debug: self.debugger.destroy()

        self.surface.destroy()
        self.instance.destroy()

        self.window.close()
    
    def close(self):

        self.cleanup()