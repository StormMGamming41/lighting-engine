
# This file handles with creation and handling of the Vulkan debug messenger

# Standard Imports
from ctypes import byref

# Engine specific imports
from .utils import _check

# My binding import
from vulkan_py import (
    PFN_vkDebugUtilsMessengerCallbackEXT, VkDebugUtilsMessageSeverityFlagBitsEXT, VK_FALSE, VkDebugUtilsMessageTypeFlagsEXT,
    VkDebugUtilsMessageTypeFlagBitsEXT, VkDebugUtilsMessengerCreateInfoEXT, VkDebugUtilsMessengerEXT
)

class DebugMessenger:

    def __init__(self, instance):

        self._handle = None
        self.instance = instance

        self._create()

    def _create(self):

        self.callback_fn = PFN_vkDebugUtilsMessengerCallbackEXT(self.debug_callback)
        
        create_info = VkDebugUtilsMessengerCreateInfoEXT(
            messageSeverity=(
                VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_VERBOSE_BIT_EXT
                | VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
                | VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT
                | VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT
            ),
            messageType=(
                VkDebugUtilsMessageTypeFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT
                | VkDebugUtilsMessageTypeFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT
                | VkDebugUtilsMessageTypeFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT
            ),
            pfnUserCallback=self.callback_fn
        )
        
        messenger = VkDebugUtilsMessengerEXT()
        _check(self.instance._dispatch.vkCreateDebugUtilsMessengerEXT(create_info, None, byref(messenger)), "vkCreateDebugUtilsMessengerEXT")
        self._handle = messenger

    def debug_callback(self, severity, msg_type, callback_data_ptr, user_data):

        data = callback_data_ptr.contents
        message = data.pMessage.decode(errors="ignore") if data.pMessage else "<no message>"
        col = "\033[34m"
        
        if severity >= VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT:
            tag = "ERROR"
            col = "\033[31m"
        elif severity >= VkDebugUtilsMessageSeverityFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT:
            tag = "WARN"
            col = "\033[38;5;208m"
        else:
            tag = "INFO"
        
        if msg_type >= VkDebugUtilsMessageTypeFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT:
            t_tag = "PERF"
        elif msg_type >= VkDebugUtilsMessageTypeFlagBitsEXT.VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT:
            t_tag = "VALD"
        else:
            t_tag = "GENR"
        
        print(f"{col}[{tag}:{t_tag}] {message}"+"\033[0m")
        return VK_FALSE

    def destroy(self):

        if self._handle:
            self.instance._dispatch.vkDestroyDebugUtilsMessengerEXT(self._handle, None)
            print("Messenger cleaned up")
