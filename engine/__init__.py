
# Hightest level class engine that communicates with the application code
# - Any engine specific stuff and vulkan stuff can reach reach here at max
# - These objects will not be exposed to the application code

from .platform.window import *
from .rhi.instance import RHIInstance

class Engine:

    version: str = "0.0.1"

    def __init__(self, title: str, size: tuple[int, int], version: str = "1.0.0", resizable: bool = True, debug: bool = False):

        self.window = Window(title, size, resizable)
        self.title = title
        self.app_version = version
        self.instance = RHIInstance(self, self.window.get_rquired_extensions(), ["VK_LAYER_KHRONOS_validation"] if debug else [])
    
    def update(self):

        self.window.update()

    def cleanup(self):

        del self.window
        del self.instance