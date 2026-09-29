
# This file contains utility functions for Engine's RHI
# Contents of this file are only meant to be used by the RHI

from ctypes import byref

from vulkan_py import (
    VkResult, VkImageViewCreateInfo, VkImageView, VkImageViewType, VkImageSubresourceRange, VkImageAspectFlagBits
)

def _check(result, op):
    if result != VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation {op} failed with error code: {result}")

def _create_image_view(device, image, _format, aspect_flag):

    view_info = VkImageViewCreateInfo(
        image = image,
        viewType = VkImageViewType.VK_IMAGE_VIEW_TYPE_2D,
        format = _format,
        subresourceRange = VkImageSubresourceRange(
            aspectMask = aspect_flag,
            baseMipLevel = 0,
            levelCount = 1,
            baseArrayLayer = 0,
            layerCount = 1
        )
    )

    view = VkImageView()
    _check(device._dispatch.vkCreateImageView(view_info, None, byref(view)), "vkCreateImageView")

    return view