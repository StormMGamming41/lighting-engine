from ctypes import byref, c_uint32, c_uint64, pointer
import vulkan_py as vk

UINT64_MAX = 0xFFFFFFFFFFFFFFFF


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


def _transition_image(device, cmd, image, old_layout, new_layout,
                       src_access, dst_access, src_stage, dst_stage, aspect):
    """Dynamic-rendering-style layout transition using synchronization2 (VkImageMemoryBarrier2)."""
    barrier = vk.VkImageMemoryBarrier2(
        srcStageMask=src_stage,
        srcAccessMask=src_access,
        dstStageMask=dst_stage,
        dstAccessMask=dst_access,
        oldLayout=old_layout,
        newLayout=new_layout,
        srcQueueFamilyIndex=vk.VK_QUEUE_FAMILY_IGNORED,
        dstQueueFamilyIndex=vk.VK_QUEUE_FAMILY_IGNORED,
        image=image,
        subresourceRange=vk.VkImageSubresourceRange(
            aspectMask=aspect, baseMipLevel=0, levelCount=1, baseArrayLayer=0, layerCount=1
        ),
    )
    dep_info = vk.VkDependencyInfo(imageMemoryBarrierCount=1, pImageMemoryBarriers=vk.pointer(barrier))
    device.dispatch.vkCmdPipelineBarrier2(cmd, byref(dep_info))


class FrameLoop:
    """Owns per-frame sync objects and the acquire/submit/present sequence.

    Usage per frame:
        result = frame_loop.begin_frame()
        if result is None:
            continue  # swapchain was out of date and got recreated; skip this frame
        cmd, image_index = result
        # ... record draw commands into cmd, using frame_loop.begin_rendering(cmd, image_index)
        #     and device.dispatch.vkCmd*() calls directly ...
        frame_loop.end_frame(cmd, image_index)
    """

    def __init__(self, device, swapchain, command_pool, max_frames_in_flight: int = 2):
        self.device = device
        self.swapchain = swapchain
        self.max_frames_in_flight = max_frames_in_flight

        self.command_buffers = command_pool.allocate_buffers(max_frames_in_flight)

        # one render-finished semaphore per swapchain image (signaled at submit, waited on at present)
        self.render_finished_semaphores = [self._create_semaphore() for _ in swapchain.images]

        # one image-available semaphore + in-flight fence per frame-in-flight slot
        self.image_available_semaphores = [self._create_semaphore() for _ in range(max_frames_in_flight)]
        self.in_flight_fences = [self._create_fence(signaled=True) for _ in range(max_frames_in_flight)]

        self.frame_index = 0

    def _create_semaphore(self):
        sem = vk.VkSemaphore()
        _check(
            self.device.dispatch.vkCreateSemaphore(vk.VkSemaphoreCreateInfo(), None, byref(sem)),
            "vkCreateSemaphore",
        )
        return sem

    def _create_fence(self, signaled: bool):
        flags = vk.VkFenceCreateFlagBits.VK_FENCE_CREATE_SIGNALED_BIT if signaled else 0
        fence = vk.VkFence()
        _check(
            self.device.dispatch.vkCreateFence(vk.VkFenceCreateInfo(flags=flags), None, byref(fence)),
            "vkCreateFence",
        )
        return fence

    # -- per-frame sequence -------------------------------------------------

    def begin_frame(self):
        """Waits for this frame slot to be free, acquires a swapchain image, and
        returns (command_buffer, image_index) ready to record into - or None if
        the swapchain needed recreating (caller should just skip this frame)."""
        fence = self.in_flight_fences[self.frame_index]
        self.device.dispatch.vkWaitForFences(1, byref(fence), vk.VK_TRUE, UINT64_MAX)

        image_index = c_uint32(0)
        result = self.device.dispatch.vkAcquireNextImageKHR(
            self.swapchain.raw, UINT64_MAX,
            self.image_available_semaphores[self.frame_index],
            vk.VkFence(0), byref(image_index),
        )
        if result == vk.VkResult.VK_ERROR_OUT_OF_DATE_KHR:
            self.swapchain.recreate()
            return None
        if result not in (vk.VkResult.VK_SUCCESS, vk.VkResult.VK_SUBOPTIMAL_KHR):
            raise RuntimeError(f"Failed to acquire swapchain image: {result}")

        self.device.dispatch.vkResetFences(1, byref(fence))

        cmd = self.command_buffers[self.frame_index]
        self.device.dispatch.vkResetCommandBuffer(cmd, 0)
        _check(self.device.dispatch.vkBeginCommandBuffer(cmd, vk.VkCommandBufferBeginInfo()), "vkBeginCommandBuffer")

        image = self.swapchain.images[image_index.value]
        _transition_image(
            self.device, cmd, image,
            vk.VkImageLayout.VK_IMAGE_LAYOUT_UNDEFINED,
            vk.VkImageLayout.VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL,
            0, vk.VkAccessFlagBits2.VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
            vk.VkPipelineStageFlagBits2.VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            vk.VkPipelineStageFlagBits2.VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            vk.VkImageAspectFlagBits.VK_IMAGE_ASPECT_COLOR_BIT,
        )

        return cmd, image_index.value

    def begin_rendering(self, cmd, image_index, clear_color=(0.1, 0.1, 0.1, 1.0)):
        """Starts dynamic rendering targeting the swapchain image, and sets the
        dynamic viewport/scissor to match the current swapchain extent."""
        attachment_info = vk.VkRenderingAttachmentInfo(
            imageView=self.swapchain.image_views[image_index],
            imageLayout=vk.VkImageLayout.VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL,
            loadOp=vk.VkAttachmentLoadOp.VK_ATTACHMENT_LOAD_OP_CLEAR,
            storeOp=vk.VkAttachmentStoreOp.VK_ATTACHMENT_STORE_OP_STORE,
            clearValue=vk.VkClearValue(color=vk.VkClearColorValue(float32=clear_color)),
        )
        render_info = vk.VkRenderingInfo(
            renderArea=vk.VkRect2D(vk.VkOffset2D(x=0, y=0), self.swapchain.extent),
            layerCount=1,
            colorAttachmentCount=1,
            pColorAttachments=vk.pointer(attachment_info),
        )
        self.device.dispatch.vkCmdBeginRendering(cmd, render_info)

        viewport = vk.VkViewport(
            x=0.0, y=0.0,
            width=float(self.swapchain.extent.width), height=float(self.swapchain.extent.height),
            minDepth=0.0, maxDepth=1.0,
        )
        scissor = vk.VkRect2D(vk.VkOffset2D(x=0, y=0), self.swapchain.extent)
        self.device.dispatch.vkCmdSetViewport(cmd, 0, 1, viewport)
        self.device.dispatch.vkCmdSetScissor(cmd, 0, 1, scissor)

    def end_frame(self, cmd, image_index):
        """Ends dynamic rendering, transitions for present, submits, and presents."""
        self.device.dispatch.vkCmdEndRendering(cmd)

        image = self.swapchain.images[image_index]
        _transition_image(
            self.device, cmd, image,
            vk.VkImageLayout.VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL,
            vk.VkImageLayout.VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
            vk.VkAccessFlagBits2.VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT, vk.VkAccessFlagBits2.VK_ACCESS_2_NONE,
            vk.VkPipelineStageFlagBits2.VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
            vk.VkPipelineStageFlagBits2.VK_PIPELINE_STAGE_2_NONE,
            vk.VkImageAspectFlagBits.VK_IMAGE_ASPECT_COLOR_BIT,
        )

        self.device.dispatch.vkEndCommandBuffer(cmd)

        wait_sem = (vk.VkSemaphore * 1)(self.image_available_semaphores[self.frame_index])
        signal_sem = (vk.VkSemaphore * 1)(self.render_finished_semaphores[image_index])
        wait_stage = (c_uint32 * 1)(vk.VkPipelineStageFlagBits.VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT)
        cmd_arr = (vk.VkCommandBuffer * 1)(cmd)

        submit_info = vk.VkSubmitInfo(
            waitSemaphoreCount=1, pWaitSemaphores=wait_sem, pWaitDstStageMask=wait_stage,
            commandBufferCount=1, pCommandBuffers=cmd_arr,
            signalSemaphoreCount=1, pSignalSemaphores=signal_sem,
        )
        _check(
            self.device.dispatch.vkQueueSubmit(self.device.graphics_queue, 1, byref(submit_info),
                                                self.in_flight_fences[self.frame_index]),
            "vkQueueSubmit",
        )

        swapchains = (vk.VkSwapchainKHR * 1)(self.swapchain.raw)
        image_index_c = c_uint32(image_index)
        present_info = vk.VkPresentInfoKHR(
            waitSemaphoreCount=1, pWaitSemaphores=signal_sem,
            swapchainCount=1, pSwapchains=swapchains,
            pImageIndices=pointer(image_index_c),
        )
        result = self.device.dispatch.vkQueuePresentKHR(self.device.present_queue, byref(present_info))
        if result in (vk.VkResult.VK_ERROR_OUT_OF_DATE_KHR, vk.VkResult.VK_SUBOPTIMAL_KHR):
            self.swapchain.recreate()
        elif result != vk.VkResult.VK_SUCCESS:
            raise RuntimeError(f"Failed to present: {result}")

        self.frame_index = (self.frame_index + 1) % self.max_frames_in_flight

    def destroy(self):
        for sem in self.render_finished_semaphores:
            self.device.dispatch.vkDestroySemaphore(sem, None)
        for sem in self.image_available_semaphores:
            self.device.dispatch.vkDestroySemaphore(sem, None)
        for fence in self.in_flight_fences:
            self.device.dispatch.vkDestroyFence(fence, None)
        self.render_finished_semaphores = []
        self.image_available_semaphores = []
        self.in_flight_fences = []