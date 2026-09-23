
def VK_MAKE_VERSION(major: int, minor: int, patch: int) -> int:
    return ((major & 0x7F) << 22) | ((minor & 0x3FF) << 12) | (patch & 0xFFF)


VK_API_VERSION_1_0 = VK_MAKE_VERSION(1, 0, 0)
VK_API_VERSION_1_1 = VK_MAKE_VERSION(1, 1, 0)
VK_API_VERSION_1_2 = VK_MAKE_VERSION(1, 2, 0)
VK_API_VERSION_1_3 = VK_MAKE_VERSION(1, 3, 0)
VK_API_VERSION_1_4 = VK_MAKE_VERSION(1, 4, 0)