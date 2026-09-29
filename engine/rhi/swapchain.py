
# This file handles creation and handling of swapchain of the engine

# Standard imports
import ctypes
from ctypes import byref, POINTER, cast, c_uint32
import glfw

# Engine specific imports
from .utils import _check, _create_image_view

# My binding imports
from vulkan_py import (
    VkSurfaceCapabilitiesKHR, VkSurfaceFormatKHR, VkFormat, VkColorSpaceKHR, VkPresentModeKHR, VkExtent2D, VkSharingMode,
    VkImageUsageFlagBits, VkCompositeAlphaFlagBitsKHR, VkSwapchainCreateInfoKHR, VkSwapchainKHR, VkImage, VkImageAspectFlagBits
)

class RHISwapchain:

    def __init__(self, instance, device, surface):

        self._handle = None
        self._format = None
        self.extent = None
        self.device = device
        self.instance = instance
        self.surface = surface

        self._create()

    def _create(self):
    
        caps = VkSurfaceCapabilitiesKHR()
        self.instance._dispatch.vkGetPhysicalDeviceSurfaceCapabilitiesKHR(self.device.physical_device, self.surface._handle, byref(caps))
    
        fmt_count = c_uint32(0)
        self.instance._dispatch.vkGetPhysicalDeviceSurfaceFormatsKHR(self.device.physical_device, self.surface._handle, byref(fmt_count), None)
        formats = (VkSurfaceFormatKHR * fmt_count.value)()
        self.instance._dispatch.vkGetPhysicalDeviceSurfaceFormatsKHR(self.device.physical_device, self.surface._handle, byref(fmt_count), formats)
        chosen_format = formats[0]
        for f in formats:
            if (f.format == VkFormat.VK_FORMAT_B8G8R8A8_UNORM
                    and f.colorSpace == VkColorSpaceKHR.VK_COLOR_SPACE_SRGB_NONLINEAR_KHR):
                chosen_format = f
                break
    
        mode_count = c_uint32(0)
        self.instance._dispatch.vkGetPhysicalDeviceSurfacePresentModesKHR(self.device.physical_device, self.surface._handle, byref(mode_count), None)
        modes = (ctypes.c_int32 * mode_count.value)()
        self.instance._dispatch.vkGetPhysicalDeviceSurfacePresentModesKHR(self.device.physical_device, self.surface._handle, byref(mode_count), modes)
        if VkPresentModeKHR.VK_PRESENT_MODE_IMMEDIATE_KHR in list(modes):
            present_mode = VkPresentModeKHR.VK_PRESENT_MODE_IMMEDIATE_KHR
        elif VkPresentModeKHR.VK_PRESENT_MODE_MAILBOX_KHR in list(modes):
            present_mode = VkPresentModeKHR.VK_PRESENT_MODE_MAILBOX_KHR
        else:
            present_mode = VkPresentModeKHR.VK_PRESENT_MODE_FIFO_KHR
    
        if caps.currentExtent.width != 0xFFFFFFFF:
            extent = caps.currentExtent
        else:
            fb_w, fb_h = glfw.get_framebuffer_size(self.window)
            extent = VkExtent2D(width=fb_w, height=fb_h)
    
        image_count = caps.minImageCount + 1
        if caps.maxImageCount != 0 and image_count > caps.maxImageCount:
            image_count = caps.maxImageCount
    
        if self.device.graphics_family != self.device.present_family:
            indices = (c_uint32 * 2)(self.graphics_family, self.present_family)
            sharing_mode, index_count, indices_ptr = VkSharingMode.VK_SHARING_MODE_CONCURRENT, 2, cast(indices, POINTER(c_uint32))
        else:
            sharing_mode, index_count, indices_ptr = VkSharingMode.VK_SHARING_MODE_EXCLUSIVE, 0, None
    
        create_info = VkSwapchainCreateInfoKHR(
            surface=self.surface._handle,
            minImageCount=image_count,
            imageFormat=chosen_format.format,
            imageColorSpace=chosen_format.colorSpace,
            imageExtent=extent,
            imageArrayLayers=1,
            imageUsage=VkImageUsageFlagBits.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
            imageSharingMode=sharing_mode,
            queueFamilyIndexCount=index_count,
            pQueueFamilyIndices=indices_ptr,
            preTransform=caps.currentTransform,
            compositeAlpha=VkCompositeAlphaFlagBitsKHR.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
            presentMode=present_mode,
            clipped=1,
            oldSwapchain=VkSwapchainKHR(0),
        )
    
        swapchain = VkSwapchainKHR()
        _check(self.device._dispatch.vkCreateSwapchainKHR(create_info, None, byref(swapchain)),"vkCreateSwapchainKHR")
        self._handle, self._format, self.extent = swapchain, chosen_format.format, extent
    
        img_count = c_uint32(0)
        self.device._dispatch.vkGetSwapchainImagesKHR(self._handle, byref(img_count), None)
        images = (VkImage * img_count.value)()
        self.device._dispatch.vkGetSwapchainImagesKHR(self._handle, byref(img_count), images)
        self.images = list(images)

        self._create_image_views()

        print("Swapchain creation successful")

    def _create_image_views(self):

        self.image_views = []
        for img in self.images:
            view = _create_image_view(self.device, img, self._format, VkImageAspectFlagBits.VK_IMAGE_ASPECT_COLOR_BIT)
            self.image_views.append(view)

    def destroy(self):

        for view in self.image_views: self.device._dispatch.vkDestroyImageView(view, None)
        self.device._dispatch.vkDestroySwapchainKHR(self._handle, None)