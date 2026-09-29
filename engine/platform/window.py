
# Part of the engine that handles windowing stuff
# - Currently there is only GLFW support
# - More platform support will added in the future

# Standard imports
from ctypes import byref, c_void_p
import glfw

# Engine specific imports
from ..rhi.utils import _check

# My binding imports
from vulkan_py import (
    VkSurfaceKHR
)

class Window:

    def __init__(self, title: str, size: tuple[int, int], resizable: bool = True):

        self.title = title
        self.size = size
        self.resizable = glfw.TRUE if resizable else glfw.FALSE
        self._handle = None

        self._create()
    
    def should_close(self) -> bool:
        return glfw.window_should_close(self._handle)

    def get_rquired_extensions(self):
        return glfw.get_required_instance_extensions()

    def get_surface(self, inst_handle):
        surface_handle = c_void_p(0)
        _check(glfw.create_window_surface(inst_handle.value, self._handle, None, byref(surface_handle)),"glfw.create_window_surface")
        return VkSurfaceKHR(surface_handle.value)

    def update(self):
        glfw.poll_events()

    def _create(self):

        if not glfw.init():
            raise RuntimeError("GLFW failed initialize")
        
        glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
        glfw.window_hint(glfw.RESIZABLE, self.resizable)

        self._handle = glfw.create_window(self.size[0], self.size[1], self.title, None, None)

        if not self._handle:
            raise RuntimeError("Window creation failed")
    
    def close(self):
        if self._handle:
            glfw.destroy_window(self._handle)
        glfw.terminate()

        print("Window closed")
