
# This file handles the crucial part of creation and management of the Vulkan's VkDevice object
# Currently only supports working with a single device

# Standard imports
from ctypes import byref, POINTER, pointer, cast, c_void_p, c_uint32, c_float, c_char_p

#Engine specific imports
from .utils import _check

# My binding import
from vulkan_py import (
    VkPhysicalDevice, VkPhysicalDeviceProperties, VkPhysicalDeviceType, VkQueueFamilyProperties, VkQueueFlagBits, VkDeviceQueueCreateInfo,
    VkPhysicalDeviceFeatures, VkPhysicalDeviceVulkan13Features, VkDeviceCreateInfo, VkDevice, VkResult, VkQueue, Device, VK_TRUE
)

class RHIDevice:

    def __init__(self, instance, surface):

        self._handle = None
        self._dispatch = None
        self.instance = instance
        self.surface = surface
        self.physical_device = None
        self.physical_devices = None
        self.graphics_family = None
        self.present_family = None

        self.pick_physical_device()
        self._create()

    def pick_physical_device(self):

        count = c_uint32(0)
        self.instance._dispatch.vkEnumeratePhysicalDevices(byref(count), None)
        if count.value < 1:
            raise RuntimeError("Failed to find a Vulkan compatible GPU")
        self.physical_devices = (VkPhysicalDevice * count.value)()
        self.instance._dispatch.vkEnumeratePhysicalDevices(byref(count), self.physical_devices)

        best = None
        for pd in self.physical_devices:
            gfx, present = self._find_queue_families(pd)
            if gfx is None or present is None:
                continue
            props = VkPhysicalDeviceProperties()
            self.instance._dispatch.vkGetPhysicalDeviceProperties(pd, props)
            score = 2 if props.deviceType == VkPhysicalDeviceType.VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU else 1
            if best is None or score > best[0]:
                best = (score, pd, gfx, present, props.deviceName.decode(errors="ignore"))
        
        if best is None:
            raise RuntimeError("No GPU with both graphics and present support found")

        _, pd, gfx, present, name = best
        self.physical_device, self.graphics_family, self.present_family = pd, gfx, present

    def _find_queue_families(self, physical_device):
        count = c_uint32(0)
        self.instance._dispatch.vkGetPhysicalDeviceQueueFamilyProperties(physical_device, byref(count), None)
        families = (VkQueueFamilyProperties * count.value)()
        self.instance._dispatch.vkGetPhysicalDeviceQueueFamilyProperties(physical_device, byref(count), families)

        graphics_family = present_family = None
        for i, fam in enumerate(families):
            if fam.queueFlags & VkQueueFlagBits.VK_QUEUE_GRAPHICS_BIT:
                graphics_family = i
            supported = c_uint32(0)
            self.instance._dispatch.vkGetPhysicalDeviceSurfaceSupportKHR(physical_device, i, self.surface._handle, byref(supported))
            if supported.value:
                present_family = i
            if graphics_family is not None and present_family is not None:
                break
        return graphics_family, present_family

    def _create(self):

        unique_families = {self.graphics_family, self.present_family}
        priority = c_float(1.0)
        queue_infos = [
            VkDeviceQueueCreateInfo(queueFamilyIndex=fam, queueCount=1, pQueuePriorities=pointer(priority))
            for fam in unique_families
        ]
        queue_infos_arr = (VkDeviceQueueCreateInfo * len(queue_infos))(*queue_infos)

        exts = [b"VK_KHR_swapchain"]
        ext_arr = (c_char_p * len(exts))(*exts)

        features = VkPhysicalDeviceFeatures(
            samplerAnisotropy = VK_TRUE
        )

        vk13_features = VkPhysicalDeviceVulkan13Features(
            dynamicRendering=1,
            synchronization2=1
        )
        create_info = VkDeviceCreateInfo(
            pNext=cast(pointer(vk13_features), c_void_p),
            queueCreateInfoCount=len(queue_infos),
            pQueueCreateInfos=cast(queue_infos_arr, POINTER(VkDeviceQueueCreateInfo)),
            enabledExtensionCount=len(exts),
            ppEnabledExtensionNames=cast(ext_arr, POINTER(c_char_p)),
            pEnabledFeatures=pointer(features)
        )

        raw_device = VkDevice()
        _check(self.instance._dispatch.vkCreateDevice(self.physical_device, create_info, None, raw_device), "vkCreateDevice")
        self._handle = raw_device
        self._dispatch = Device(raw_device)

        graphics_queue = VkQueue()
        self._dispatch.vkGetDeviceQueue(self.graphics_family, 0, byref(graphics_queue))
        self.graphics_queue = graphics_queue

        present_queue = VkQueue()
        self._dispatch.vkGetDeviceQueue(self.present_family, 0, byref(present_queue))
        self.present_queue = present_queue

        print("Device creation successful")
    
    def destroy(self):

        if self._handle and self._dispatch:
            self._dispatch.vkDestroyDevice(None)
            print("Device destroyed")

