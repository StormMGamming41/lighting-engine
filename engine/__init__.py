
# Hightest level class engine that communicates with the application code
# - Any engine specific stuff and vulkan stuff can reach reach here at max
# - These objects will not be exposed to the application code

from .platform.window import *

class Engine:

    version = "0.0.1"

    def __init__(self, title: str, size: tuple[int, int], version:str = "1.0.0", resizable: bool = True):

        self.window = Window(title, size, resizable)
        self.app_version = version
    
    def update(self):

        self.window.update()

    def cleanup(self):

        del self.window