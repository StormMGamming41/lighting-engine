
from ctypes import byref
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


class CommandPool:
    def __init__(self, device):
        self.device = device
        self.raw = None
        self._create()

    def _create(self):
        pool_info = vk.VkCommandPoolCreateInfo(
            flags=vk.VkCommandPoolCreateFlagBits.VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
            queueFamilyIndex=self.device.graphics_family,
        )
        raw = vk.VkCommandPool()
        _check(
            self.device.dispatch.vkCreateCommandPool(pool_info, None, byref(raw)),
            "vkCreateCommandPool",
        )
        self.raw = raw

    def allocate_buffers(self, count: int):
        alloc_info = vk.VkCommandBufferAllocateInfo(
            commandPool=self.raw,
            level=vk.VkCommandBufferLevel.VK_COMMAND_BUFFER_LEVEL_PRIMARY,
            commandBufferCount=count,
        )
        buffers = (vk.VkCommandBuffer * count)()
        _check(
            self.device.dispatch.vkAllocateCommandBuffers(alloc_info, buffers),
            "vkAllocateCommandBuffers",
        )
        return list(buffers)

    def destroy(self):
        if self.raw is not None:
            self.device.dispatch.vkDestroyCommandPool(self.raw, None)
            self.raw = None