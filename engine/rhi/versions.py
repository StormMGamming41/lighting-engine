
# This file handles the following stuff (currently follow major.minor.patch convention)
# - Abstract version creation for vulkan compatibility
# - Providing predefines vulkan api versions

def make_version(major, minor, patch):
    return ((major & 0x7f) << 22) | ((minor & 0x3ff) << 12) | (patch & 0xfff)

def make_version_from_str(version: str):

    ver = []
    parts = version.split(".")
    for part in parts:
        ver.append(int(part))
    return make_version(ver[0], ver[1], ver[2])

VK_API_VERSION_1_0 = make_version(1, 0, 0)
VK_API_VERSION_1_1 = make_version(1, 1, 0)
VK_API_VERSION_1_2 = make_version(1, 2, 0)
VK_API_VERSION_1_3 = make_version(1, 3, 0)
VK_API_VERSION_1_4 = make_version(1, 4, 0)