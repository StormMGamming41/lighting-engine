
# This file contains utility functions for Engine's RHI
# Contents of this file are only meant to be used by the RHI

from vulkan_py import VkResult

def _check(result, op):
    if result != VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation {op} failed with error code: {result}")