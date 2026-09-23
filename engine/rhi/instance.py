
import ctypes
from ctypes import byref, c_char_p, cast, POINTER
import glfw
import vulkan_py as vk

from engine.rhi.constants import VK_MAKE_VERSION


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


class Instance:
    def __init__(self, app_name: str = "App", enable_validation: bool = True):
        self.app_name = app_name
        self.enable_validation = enable_validation

        self.raw = None        # raw VkInstance handle
        self.dispatch = None   # vulkan_py.Instance(raw) - instance-level call surface

        self._create()

    def _create(self):
        app_info = vk.VkApplicationInfo(
            pApplicationName=self.app_name.encode(),
            applicationVersion=VK_MAKE_VERSION(1, 0, 0),
            pEngineName=b"MyEngine",
            engineVersion=VK_MAKE_VERSION(1, 0, 0),
            apiVersion=VK_MAKE_VERSION(1, 3, 0),
        )

        exts = glfw.get_required_instance_extensions() or []
        ext_bytes = [e.encode("utf-8") for e in exts]
        if self.enable_validation:
            ext_bytes.append(b"VK_EXT_debug_utils")
        ext_arr = (c_char_p * len(ext_bytes))(*ext_bytes)

        layers = [b"VK_LAYER_KHRONOS_validation"] if self.enable_validation else []
        layer_arr = (c_char_p * len(layers))(*layers)

        create_info = vk.VkInstanceCreateInfo(
            pApplicationInfo=ctypes.pointer(app_info),
            enabledExtensionCount=len(ext_bytes),
            ppEnabledExtensionNames=cast(ext_arr, POINTER(c_char_p)),
            enabledLayerCount=len(layers),
            ppEnabledLayerNames=cast(layer_arr, POINTER(c_char_p)),
        )

        raw = vk.VkInstance()
        _check(vk.vkCreateInstance(byref(create_info), None, byref(raw)), "vkCreateInstance")

        self.raw = raw
        self.dispatch = vk.Instance(raw)

    def destroy(self):
        if self.dispatch is not None:
            self.dispatch.vkDestroyInstance(None)
            self.raw = None
            self.dispatch = None