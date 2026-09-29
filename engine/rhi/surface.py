
# This is file is for handling the window surfaces

# My binding impotrs
from vulkan_py import (
    VkSurfaceKHR
)

class RHISurface:

    def __init__(self, handle, instance):

        self._handle = handle
        self.instance = instance

    def destroy(self):

        if self._handle:
            self.instance._dispatch.vkDestroySurfaceKHR(self._handle, None)
            print("Surface destroyed")