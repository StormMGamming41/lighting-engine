
import ctypes
from ctypes import byref, c_char_p, c_float, c_uint32, c_void_p, cast, pointer, POINTER
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


class Device:
    def __init__(self, instance, surface, require_anisotropy: bool = True):
        self.instance = instance
        self.surface = surface

        self.physical_device = None
        self.graphics_family = None
        self.present_family = None

        self.raw = None
        self.dispatch = None

        self.graphics_queue = None
        self.present_queue = None

        self._pick_physical_device()
        self._create_logical_device(require_anisotropy)

    def _find_queue_families(self, physical_device):
        count = c_uint32(0)
        self.instance.dispatch.vkGetPhysicalDeviceQueueFamilyProperties(
            physical_device, byref(count), None
        )
        families = (vk.VkQueueFamilyProperties * count.value)()
        self.instance.dispatch.vkGetPhysicalDeviceQueueFamilyProperties(
            physical_device, byref(count), families
        )

        graphics_family = present_family = None
        for i, fam in enumerate(families):
            if fam.queueFlags & vk.VkQueueFlagBits.VK_QUEUE_GRAPHICS_BIT:
                graphics_family = i

            supported = c_uint32(0)
            self.instance.dispatch.vkGetPhysicalDeviceSurfaceSupportKHR(
                physical_device, i, self.surface.raw, byref(supported)
            )
            if supported.value:
                present_family = i

            if graphics_family is not None and present_family is not None:
                break

        return graphics_family, present_family

    def _pick_physical_device(self):
        count = c_uint32(0)
        self.instance.dispatch.vkEnumeratePhysicalDevices(byref(count), None)
        if count.value < 1:
            raise RuntimeError("No Vulkan-compatible GPU found")

        candidates = (vk.VkPhysicalDevice * count.value)()
        self.instance.dispatch.vkEnumeratePhysicalDevices(byref(count), candidates)

        best = None
        for pd in candidates:
            gfx, present = self._find_queue_families(pd)
            if gfx is None or present is None:
                continue

            props = vk.VkPhysicalDeviceProperties()
            self.instance.dispatch.vkGetPhysicalDeviceProperties(pd, byref(props))
            score = 2 if props.deviceType == vk.VkPhysicalDeviceType.VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU else 1

            if best is None or score > best[0]:
                best = (score, pd, gfx, present)

        if best is None:
            raise RuntimeError("No GPU with both graphics and present support found")

        _, pd, gfx, present = best
        self.physical_device = pd
        self.graphics_family = gfx
        self.present_family = present

    def _create_logical_device(self, require_anisotropy: bool):
        unique_families = {self.graphics_family, self.present_family}
        priority = c_float(1.0)

        queue_infos = [
            vk.VkDeviceQueueCreateInfo(
                queueFamilyIndex=fam, queueCount=1, pQueuePriorities=pointer(priority)
            )
            for fam in unique_families
        ]
        queue_infos_arr = (vk.VkDeviceQueueCreateInfo * len(queue_infos))(*queue_infos)

        exts = [b"VK_KHR_swapchain"]
        ext_arr = (c_char_p * len(exts))(*exts)

        features = vk.VkPhysicalDeviceFeatures(
            samplerAnisotropy=vk.VK_TRUE if require_anisotropy else vk.VK_FALSE
        )

        vk13_features = vk.VkPhysicalDeviceVulkan13Features(
            dynamicRendering=1,
            synchronization2=1,
        )

        create_info = vk.VkDeviceCreateInfo(
            pNext=cast(pointer(vk13_features), c_void_p),
            queueCreateInfoCount=len(queue_infos),
            pQueueCreateInfos=cast(queue_infos_arr, POINTER(vk.VkDeviceQueueCreateInfo)),
            enabledExtensionCount=len(exts),
            ppEnabledExtensionNames=cast(ext_arr, POINTER(c_char_p)),
            pEnabledFeatures=pointer(features),
        )

        raw = vk.VkDevice()
        _check(
            self.instance.dispatch.vkCreateDevice(self.physical_device, create_info, None, raw),
            "vkCreateDevice",
        )

        self.raw = raw
        self.dispatch = vk.Device(raw)

        graphics_queue = vk.VkQueue()
        self.dispatch.vkGetDeviceQueue(self.graphics_family, 0, byref(graphics_queue))
        self.graphics_queue = graphics_queue

        present_queue = vk.VkQueue()
        self.dispatch.vkGetDeviceQueue(self.present_family, 0, byref(present_queue))
        self.present_queue = present_queue

    def wait_idle(self):
        self.dispatch.vkDeviceWaitIdle()

    def destroy(self):
        if self.dispatch is not None:
            self.dispatch.vkDestroyDevice(None)
            self.raw = None
            self.dispatch = None