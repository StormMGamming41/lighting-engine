
import ctypes
from ctypes import byref, c_void_p, cast, pointer, POINTER
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


def _find_memory_type(device, type_filter: int, properties):
    mem_props = vk.VkPhysicalDeviceMemoryProperties()
    device.instance.dispatch.vkGetPhysicalDeviceMemoryProperties(
        device.physical_device, byref(mem_props)
    )
    for i in range(mem_props.memoryTypeCount):
        if (type_filter & (1 << i)) and (mem_props.memoryTypes[i].propertyFlags & properties) == properties:
            return i
    raise RuntimeError("No compatible memory type found")


def create_buffer(device, size: int, usage, properties):
    buffer_info = vk.VkBufferCreateInfo(
        size=size, usage=usage, sharingMode=vk.VkSharingMode.VK_SHARING_MODE_EXCLUSIVE
    )
    buf = vk.VkBuffer()
    _check(device.dispatch.vkCreateBuffer(pointer(buffer_info), None, byref(buf)), "vkCreateBuffer")

    mem_req = vk.VkMemoryRequirements()
    device.dispatch.vkGetBufferMemoryRequirements(buf, byref(mem_req))

    alloc_info = vk.VkMemoryAllocateInfo(
        allocationSize=mem_req.size,
        memoryTypeIndex=_find_memory_type(device, mem_req.memoryTypeBits, properties),
    )
    mem = vk.VkDeviceMemory()
    _check(device.dispatch.vkAllocateMemory(pointer(alloc_info), None, byref(mem)), "vkAllocateMemory")

    _check(device.dispatch.vkBindBufferMemory(buf, mem, 0), "vkBindBufferMemory")
    return buf, mem


def destroy_buffer(device, buf, mem):
    if buf is not None:
        device.dispatch.vkDestroyBuffer(buf, None)
    if mem is not None:
        device.dispatch.vkFreeMemory(mem, None)


def begin_single_time_commands(device, command_pool):
    buffers = command_pool.allocate_buffers(1)
    cmd = buffers[0]
    begin_info = vk.VkCommandBufferBeginInfo(
        flags=vk.VkCommandBufferUsageFlagBits.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT
    )
    _check(device.dispatch.vkBeginCommandBuffer(cmd, begin_info), "vkBeginCommandBuffer")
    return cmd


def end_single_time_commands(device, command_pool, cmd):
    device.dispatch.vkEndCommandBuffer(cmd)

    cmd_arr = (vk.VkCommandBuffer * 1)(cmd)
    submit_info = vk.VkSubmitInfo(commandBufferCount=1, pCommandBuffers=cmd_arr)
    device.dispatch.vkQueueSubmit(device.graphics_queue, 1, byref(submit_info), vk.VkFence(0))
    device.dispatch.vkQueueWaitIdle(device.graphics_queue)
    cmd_free_arr = (vk.VkCommandBuffer * 1)(cmd)
    device.dispatch.vkFreeCommandBuffers(command_pool.raw, 1, cmd_free_arr)


def copy_buffer(device, command_pool, src, dst, size):
    cmd = begin_single_time_commands(device, command_pool)
    region = (vk.VkBufferCopy * 1)(vk.VkBufferCopy(0, 0, size))
    device.dispatch.vkCmdCopyBuffer(cmd, src, dst, 1, region)
    end_single_time_commands(device, command_pool, cmd)


def _upload_via_staging(device, command_pool, data_ptr, size, usage):
    staging_buf, staging_mem = create_buffer(
        device, size,
        vk.VkBufferUsageFlagBits.VK_BUFFER_USAGE_TRANSFER_SRC_BIT,
        vk.VkMemoryPropertyFlagBits.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT
        | vk.VkMemoryPropertyFlagBits.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
    )

    mapped = c_void_p()
    _check(device.dispatch.vkMapMemory(staging_mem, 0, size, 0, byref(mapped)), "vkMapMemory")
    ctypes.memmove(mapped.value, data_ptr, size)
    device.dispatch.vkUnmapMemory(staging_mem)

    final_buf, final_mem = create_buffer(
        device, size,
        usage | vk.VkBufferUsageFlagBits.VK_BUFFER_USAGE_TRANSFER_DST_BIT,
        vk.VkMemoryPropertyFlagBits.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
    )

    copy_buffer(device, command_pool, staging_buf, final_buf, size)
    destroy_buffer(device, staging_buf, staging_mem)

    return final_buf, final_mem


class VertexBuffer:
    def __init__(self, device, command_pool, data):
        self.device = device
        self.count = len(data)
        size = ctypes.sizeof(data)
        self.raw, self.memory = _upload_via_staging(
            device, command_pool, ctypes.addressof(data), size,
            vk.VkBufferUsageFlagBits.VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
        )

    def destroy(self):
        destroy_buffer(self.device, self.raw, self.memory)
        self.raw, self.memory = None, None


class IndexBuffer:
    def __init__(self, device, command_pool, data, index_type=None):
        self.device = device
        self.count = len(data)
        self.index_type = index_type if index_type is not None else vk.VkIndexType.VK_INDEX_TYPE_UINT32
        size = ctypes.sizeof(data)
        self.raw, self.memory = _upload_via_staging(
            device, command_pool, ctypes.addressof(data), size,
            vk.VkBufferUsageFlagBits.VK_BUFFER_USAGE_INDEX_BUFFER_BIT,
        )

    def destroy(self):
        destroy_buffer(self.device, self.raw, self.memory)
        self.raw, self.memory = None, None


class UniformBuffer:
    def __init__(self, device, size: int):
        self.device = device
        self.size = size
        self.raw, self.memory = create_buffer(
            device, size,
            vk.VkBufferUsageFlagBits.VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
            vk.VkMemoryPropertyFlagBits.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT
            | vk.VkMemoryPropertyFlagBits.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
        )
        mapped = c_void_p()
        _check(device.dispatch.vkMapMemory(self.memory, 0, size, 0, byref(mapped)), "vkMapMemory")
        self.mapped_ptr = mapped.value

    def update(self, data_ptr, size=None):
        ctypes.memmove(self.mapped_ptr, data_ptr, size if size is not None else self.size)

    def destroy(self):
        self.device.dispatch.vkUnmapMemory(self.memory)
        destroy_buffer(self.device, self.raw, self.memory)
        self.raw, self.memory, self.mapped_ptr = None, None, None