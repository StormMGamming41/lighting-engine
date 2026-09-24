
from ctypes import byref, c_void_p
import glfw
import vulkan_py as vk


class Surface:
    def __init__(self, instance, window):
        self.instance = instance
        self.raw = None
        self._create(window)

    def _create(self, window):
        surface_handle = c_void_p(0)
        result = glfw.create_window_surface(
            self.instance.raw.value, window.handle, None, byref(surface_handle)
        )
        if result != vk.VkResult.VK_SUCCESS:
            raise RuntimeError(f"Surface creation failed: VkResult {result}")

        self.raw = vk.VkSurfaceKHR(surface_handle.value) # type: ignore

    def destroy(self):
        if self.raw is not None:
            self.instance.dispatch.vkDestroySurfaceKHR(self.raw, None)
            self.raw = None