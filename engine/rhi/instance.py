
# Handles the vulkan instance creation for the engine

# Standart lib imports
# import ctypes
from ctypes import byref, cast, pointer, POINTER, c_uint32, c_char_p

# Engine specific imports
from .versions import make_version_from_str, VK_API_VERSION_1_3
from .utils import _check

# vulkan binding import
from vulkan_py import (
    VkApplicationInfo, vkEnumerateInstanceExtensionProperties, VkExtensionProperties, vkEnumerateInstanceLayerProperties, VkLayerProperties,
    VkInstanceCreateInfo, VkInstance, vkCreateInstance, Instance
)

class RHIInstance:

    def __init__(self, engine, extensions: list[str] = [], layers: list[str] = []):

        self._handle = None
        self._dispatch = None
        self.engine = engine
        self.app_name = engine.title
        self.ext_list = [ext.encode("utf-8") for ext in extensions]
        self.lyr_list = [lyr.encode("utf-8") for lyr in layers]

        self._create()

    def _check_support(self):

        ext_count = c_uint32(0)
        _check(vkEnumerateInstanceExtensionProperties(None, byref(ext_count), None), "vkEnumerateInstanceExtensionProperties")
        available_exts = (VkExtensionProperties * ext_count.value)()
        vkEnumerateInstanceExtensionProperties(None, byref(ext_count), available_exts)
        ext_names = [e.extensionName for e in available_exts]
        for ext in self.ext_list:
            if ext not in ext_names:
                raise RuntimeError(f"Extension {ext} is not supported")

        lyr_count = c_uint32(0)
        _check(vkEnumerateInstanceLayerProperties(byref(lyr_count), None), "vkEnumerateInstanceExtensionProperties")
        available_lyrs = (VkLayerProperties * ext_count.value)()
        vkEnumerateInstanceLayerProperties(byref(lyr_count), available_lyrs)
        lyr_names = [l.layerName for l in available_lyrs]
        for lyr in self.lyr_list:
                    if lyr not in lyr_names:
                        raise RuntimeError(f"Extension {lyr} is not supported")

    def _create(self):

        app_info = VkApplicationInfo(
            pApplicationName=self.engine.title.encode("utf-8"),
            applicationVersion=make_version_from_str(self.engine.app_version),
            pEngineName=b"Lighting Engine",
            engineVersion=make_version_from_str(self.engine.version),
            apiVersion=VK_API_VERSION_1_3
        )

        self._check_support()
        ext_arr = (c_char_p * len(self.ext_list))(*self.ext_list)
        lyr_arr = (c_char_p * len(self.lyr_list))(*self.lyr_list)

        create_info = VkInstanceCreateInfo(
            pApplicationInfo=pointer(app_info),
            enabledExtensionCount=len(self.ext_list),
            ppEnabledExtensionNames=cast(ext_arr, POINTER(c_char_p)),
            enabledLayerCount=len(self.lyr_list),
            ppEnabledLayerNames=cast(lyr_arr, POINTER(c_char_p)),
        )

        raw_inst = VkInstance()
        _check(vkCreateInstance(byref(create_info), None, byref(raw_inst)), "vkCreateInstance")
        self._handle = raw_inst
        self._dispatch = Instance(raw_inst)

        print("Instance creation : success")

    def __del__(self):

        if self._handle and self._dispatch:
            self._dispatch.vkDestroyInstance(None)
            print("Instance destroyed")
