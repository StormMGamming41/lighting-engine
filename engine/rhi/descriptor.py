
from ctypes import byref, cast, pointer, POINTER
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


class DescriptorSets:
    """Owns a descriptor pool and one descriptor set per frame-in-flight, each
    pointing at that frame's own UniformBuffer. Rebuilding a set every frame
    isn't necessary - each frame gets a fixed set once, and you just update
    the underlying UniformBuffer's contents (via UniformBuffer.update()) each
    frame instead of touching the descriptor set itself.
    """

    def __init__(self, device, descriptor_set_layout, uniform_buffers, ubo_size: int):
        """uniform_buffers: list of UniformBuffer, one per frame-in-flight.
        One descriptor set gets allocated and bound to each."""
        self.device = device
        self.descriptor_set_layout = descriptor_set_layout
        self.count = len(uniform_buffers)

        self.pool = None
        self.sets = []

        self._create_pool()
        self._allocate_and_write(uniform_buffers, ubo_size)

    def _create_pool(self):
        pool_size = (vk.VkDescriptorPoolSize * 1)(
            vk.VkDescriptorPoolSize(
                type=vk.VkDescriptorType.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                descriptorCount=self.count,
            )
        )
        pool_info = vk.VkDescriptorPoolCreateInfo(
            flags=vk.VkDescriptorPoolCreateFlagBits.VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT,
            maxSets=self.count,
            poolSizeCount=1,
            pPoolSizes=cast(pool_size, POINTER(vk.VkDescriptorPoolSize)),
        )
        pool = vk.VkDescriptorPool()
        _check(
            self.device.dispatch.vkCreateDescriptorPool(pointer(pool_info), None, byref(pool)),
            "vkCreateDescriptorPool",
        )
        self.pool = pool

    def _allocate_and_write(self, uniform_buffers, ubo_size: int):
        layouts = (vk.VkDescriptorSetLayout * self.count)(*([self.descriptor_set_layout] * self.count))
        alloc_info = vk.VkDescriptorSetAllocateInfo(
            descriptorPool=self.pool,
            descriptorSetCount=self.count,
            pSetLayouts=cast(layouts, POINTER(vk.VkDescriptorSetLayout)),
        )
        sets = (vk.VkDescriptorSet * self.count)()
        _check(self.device.dispatch.vkAllocateDescriptorSets(byref(alloc_info), sets), "vkAllocateDescriptorSets")
        self.sets = list(sets)

        for i, ubo in enumerate(uniform_buffers):
            buffer_info = (vk.VkDescriptorBufferInfo * 1)(
                vk.VkDescriptorBufferInfo(buffer=ubo.raw, offset=0, range=ubo_size)
            )
            write = vk.VkWriteDescriptorSet(
                dstSet=self.sets[i],
                dstBinding=0,
                dstArrayElement=0,
                descriptorCount=1,
                descriptorType=vk.VkDescriptorType.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                pBufferInfo=cast(buffer_info, POINTER(vk.VkDescriptorBufferInfo)),
            )
            write_arr = (vk.VkWriteDescriptorSet * 1)(write)
            self.device.dispatch.vkUpdateDescriptorSets(1, write_arr, 0, None)

    def bind(self, cmd, pipeline_layout, frame_index: int):
        sets_arr = (vk.VkDescriptorSet * 1)(self.sets[frame_index])
        self.device.dispatch.vkCmdBindDescriptorSets(
            cmd, vk.VkPipelineBindPoint.VK_PIPELINE_BIND_POINT_GRAPHICS,
            pipeline_layout, 0, 1, sets_arr, 0, None,
        )

    def destroy(self):
        if self.pool is not None:
            self.device.dispatch.vkDestroyDescriptorPool(self.pool, None)
            self.pool = None
            self.sets = []