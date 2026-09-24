
import ctypes
from ctypes import byref, c_uint32, cast, POINTER
import glfw
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


class Swapchain:
    """RHI wrapper around swapchain creation + its image views.

    Needs Instance (for surface capability/format queries), Surface, Device,
    and the platform Window (for framebuffer size fallback + recreation).
    """

    # fallback chain for each preferred mode - tried in order until one is supported
    _PRESENT_MODE_FALLBACKS = {
        "immediate": [
            vk.VkPresentModeKHR.VK_PRESENT_MODE_IMMEDIATE_KHR,
            vk.VkPresentModeKHR.VK_PRESENT_MODE_MAILBOX_KHR,
            vk.VkPresentModeKHR.VK_PRESENT_MODE_FIFO_KHR,
        ],
        "mailbox": [
            vk.VkPresentModeKHR.VK_PRESENT_MODE_MAILBOX_KHR,
            vk.VkPresentModeKHR.VK_PRESENT_MODE_FIFO_KHR,
        ],
    }

    def __init__(self, instance, surface, device, window, preferred_present_mode: str = "mailbox"):
        self.instance = instance
        self.surface = surface
        self.device = device
        self.window = window
        self.preferred_present_mode = preferred_present_mode

        self.raw = None
        self.images = []
        self.image_views = []
        self.format = None
        self.extent = None

        self._create()

    # -- creation ---------------------------------------------------------

    def _choose_surface_format(self, formats):
        for f in formats:
            if (f.format == vk.VkFormat.VK_FORMAT_B8G8R8A8_UNORM
                    and f.colorSpace == vk.VkColorSpaceKHR.VK_COLOR_SPACE_SRGB_NONLINEAR_KHR):
                return f
        return formats[0]

    def _choose_present_mode(self, modes):
        modes = list(modes)
        fallback_chain = self._PRESENT_MODE_FALLBACKS.get(
            self.preferred_present_mode, self._PRESENT_MODE_FALLBACKS["mailbox"]
        )
        for mode in fallback_chain:
            if mode in modes:
                return mode
        return vk.VkPresentModeKHR.VK_PRESENT_MODE_FIFO_KHR  # always guaranteed available

    def _choose_extent(self, caps):
        if caps.currentExtent.width != 0xFFFFFFFF:
            return caps.currentExtent
        fb_w, fb_h = glfw.get_framebuffer_size(self.window.handle)
        return vk.VkExtent2D(width=fb_w, height=fb_h)

    def _create(self):
        caps = vk.VkSurfaceCapabilitiesKHR()
        self.instance.dispatch.vkGetPhysicalDeviceSurfaceCapabilitiesKHR(
            self.device.physical_device, self.surface.raw, byref(caps)
        )

        fmt_count = c_uint32(0)
        self.instance.dispatch.vkGetPhysicalDeviceSurfaceFormatsKHR(
            self.device.physical_device, self.surface.raw, byref(fmt_count), None
        )
        formats = (vk.VkSurfaceFormatKHR * fmt_count.value)()
        self.instance.dispatch.vkGetPhysicalDeviceSurfaceFormatsKHR(
            self.device.physical_device, self.surface.raw, byref(fmt_count), formats
        )
        chosen_format = self._choose_surface_format(formats)

        mode_count = c_uint32(0)
        self.instance.dispatch.vkGetPhysicalDeviceSurfacePresentModesKHR(
            self.device.physical_device, self.surface.raw, byref(mode_count), None
        )
        modes = (ctypes.c_int32 * mode_count.value)()
        self.instance.dispatch.vkGetPhysicalDeviceSurfacePresentModesKHR(
            self.device.physical_device, self.surface.raw, byref(mode_count), modes
        )
        present_mode = self._choose_present_mode(modes)

        extent = self._choose_extent(caps)

        image_count = caps.minImageCount + 1
        if caps.maxImageCount != 0 and image_count > caps.maxImageCount:
            image_count = caps.maxImageCount

        if self.device.graphics_family != self.device.present_family:
            indices = (c_uint32 * 2)(self.device.graphics_family, self.device.present_family)
            sharing_mode = vk.VkSharingMode.VK_SHARING_MODE_CONCURRENT
            index_count, indices_ptr = 2, cast(indices, POINTER(c_uint32))
        else:
            sharing_mode = vk.VkSharingMode.VK_SHARING_MODE_EXCLUSIVE
            index_count, indices_ptr = 0, None

        create_info = vk.VkSwapchainCreateInfoKHR(
            surface=self.surface.raw,
            minImageCount=image_count,
            imageFormat=chosen_format.format,
            imageColorSpace=chosen_format.colorSpace,
            imageExtent=extent,
            imageArrayLayers=1,
            imageUsage=vk.VkImageUsageFlagBits.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
            imageSharingMode=sharing_mode,
            queueFamilyIndexCount=index_count,
            pQueueFamilyIndices=indices_ptr,
            preTransform=caps.currentTransform,
            compositeAlpha=vk.VkCompositeAlphaFlagBitsKHR.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
            presentMode=present_mode,
            clipped=1,
            oldSwapchain=vk.VkSwapchainKHR(0),
        )

        raw = vk.VkSwapchainKHR()
        _check(
            self.device.dispatch.vkCreateSwapchainKHR(create_info, None, byref(raw)),
            "vkCreateSwapchainKHR",
        )

        self.raw = raw
        self.format = chosen_format.format
        self.extent = extent

        img_count = c_uint32(0)
        self.device.dispatch.vkGetSwapchainImagesKHR(self.raw, byref(img_count), None)
        images = (vk.VkImage * img_count.value)()
        self.device.dispatch.vkGetSwapchainImagesKHR(self.raw, byref(img_count), images)
        self.images = list(images)

        self._create_image_views()

    def _create_image_views(self):
        self.image_views = []
        for image in self.images:
            view_info = vk.VkImageViewCreateInfo(
                image=image,
                viewType=vk.VkImageViewType.VK_IMAGE_VIEW_TYPE_2D,
                format=self.format,
                subresourceRange=vk.VkImageSubresourceRange(
                    aspectMask=vk.VkImageAspectFlagBits.VK_IMAGE_ASPECT_COLOR_BIT,
                    baseMipLevel=0,
                    levelCount=1,
                    baseArrayLayer=0,
                    layerCount=1,
                ),
            )
            view = vk.VkImageView()
            _check(
                self.device.dispatch.vkCreateImageView(view_info, None, byref(view)),
                "vkCreateImageView",
            )
            self.image_views.append(view)

    # -- lifecycle ----------------------------------------------------------

    def recreate(self):
        """Call after a resize or VK_ERROR_OUT_OF_DATE_KHR/SUBOPTIMAL_KHR."""
        width, height = glfw.get_framebuffer_size(self.window.handle)
        while width == 0 or height == 0:
            width, height = glfw.get_framebuffer_size(self.window.handle)
            glfw.wait_events()

        self.device.wait_idle()
        self._cleanup()
        self._create()

    def _cleanup(self):
        for view in self.image_views:
            self.device.dispatch.vkDestroyImageView(view, None)
        self.image_views = []

        if self.raw is not None:
            self.device.dispatch.vkDestroySwapchainKHR(self.raw, None)
            self.raw = None

    def destroy(self):
        self._cleanup()