from engine.platform.window import Window
from engine.rhi.instance import Instance
from engine.rhi.surface import Surface
from engine.rhi.device import Device
from engine.rhi.swapchain import Swapchain
from engine.rhi.commands import CommandPool
from engine.rhi.pipeline import GraphicsPipeline
from engine.rhi.frame import FrameLoop
from engine.rhi.buffer import VertexBuffer, IndexBuffer, UniformBuffer
from engine.rhi.descriptor import DescriptorSets
import ctypes
import time
import numpy as np
import pyrr
import vulkan_py as vk


# Minimal vertex format for this test - pos (vec2) + color (vec3).
# This will move to core/ once the engine has a proper mesh type.
class Vertex(ctypes.Structure):
    _fields_ = [
        ("pos", ctypes.c_float * 2),
        ("color", ctypes.c_float * 3),
    ]

    @staticmethod
    def binding_description():
        return vk.VkVertexInputBindingDescription(
            binding=0,
            stride=ctypes.sizeof(Vertex),
            inputRate=vk.VkVertexInputRate.VK_VERTEX_INPUT_RATE_VERTEX,
        )

    @staticmethod
    def attribute_descriptions():
        return [
            vk.VkVertexInputAttributeDescription(
                binding=0, location=0,
                format=vk.VkFormat.VK_FORMAT_R32G32_SFLOAT,
                offset=Vertex.pos.offset,
            ),
            vk.VkVertexInputAttributeDescription(
                binding=0, location=1,
                format=vk.VkFormat.VK_FORMAT_R32G32B32_SFLOAT,
                offset=Vertex.color.offset,
            ),
        ]


TRIANGLE_VERTICES = [
    Vertex(pos=(0.0, -0.5), color=(1.0, 0.0, 0.0)),
    Vertex(pos=(0.5, 0.5), color=(0.0, 1.0, 0.0)),
    Vertex(pos=(-0.5, 0.5), color=(0.0, 0.0, 1.0)),
]

QUAD_VERTICES = [
    Vertex(pos=(-0.5, -0.5), color=(1.0, 0.0, 0.0)),  # top-left
    Vertex(pos=(0.5, -0.5), color=(0.0, 1.0, 0.0)),   # top-right
    Vertex(pos=(0.5, 0.5), color=(0.0, 0.0, 1.0)),    # bottom-right
    Vertex(pos=(-0.5, 0.5), color=(1.0, 1.0, 1.0)),   # bottom-left
]
QUAD_INDICES = [0, 1, 2, 2, 3, 0]  # two triangles sharing an edge

MAX_FRAMES_IN_FLIGHT = 2


class UniformBufferObject(ctypes.Structure):
    _fields_ = [
        ("model", ctypes.c_float * 16),
        ("view", ctypes.c_float * 16),
        ("proj", ctypes.c_float * 16),
    ]


def main():
    window = Window(1280, 720, "Engine Test")
    print("Window created")

    instance = Instance(app_name="EngineTest", enable_validation=True)
    print("Instance created")

    surface = Surface(instance, window)
    print("Surface created")

    device = Device(instance, surface)
    print(f"Device created - graphics_family={device.graphics_family}, present_family={device.present_family}")

    swapchain = Swapchain(instance, surface, device, window)
    print(f"Swapchain created - {len(swapchain.images)} images, extent={swapchain.extent.width}x{swapchain.extent.height}")

    command_pool = CommandPool(device)
    print("Command pool created")

    vertex_array = (Vertex * len(QUAD_VERTICES))(*QUAD_VERTICES)
    vertex_buffer = VertexBuffer(device, command_pool, vertex_array)
    print(f"Vertex buffer created - {vertex_buffer.count} vertices")

    index_array = (ctypes.c_uint32 * len(QUAD_INDICES))(*QUAD_INDICES)
    index_buffer = IndexBuffer(device, command_pool, index_array)
    print(f"Index buffer created - {index_buffer.count} indices")

    pipeline = GraphicsPipeline(
        device,
        color_format=swapchain.format,
        vert_spirv_path="shaders/triangle.vert.spv",
        frag_spirv_path="shaders/triangle.frag.spv",
        vertex_binding=Vertex.binding_description(),
        vertex_attributes=Vertex.attribute_descriptions(),
        descriptor_bindings=[
            vk.VkDescriptorSetLayoutBinding(
                binding=0,
                descriptorType=vk.VkDescriptorType.VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                descriptorCount=1,
                stageFlags=vk.VkShaderStageFlagBits.VK_SHADER_STAGE_VERTEX_BIT,
            ),
        ],
        cull_mode=vk.VkCullModeFlagBits.VK_CULL_MODE_NONE,  # still off - see winding-order note below
        # no depth_format - no depth testing yet
    )
    print("Graphics pipeline created")

    ubo_size = ctypes.sizeof(UniformBufferObject)
    uniform_buffers = [UniformBuffer(device, ubo_size) for _ in range(MAX_FRAMES_IN_FLIGHT)]
    descriptor_sets = DescriptorSets(device, pipeline.descriptor_set_layout, uniform_buffers, ubo_size)
    print(f"{len(uniform_buffers)} uniform buffers + descriptor sets created")

    frame_loop = FrameLoop(device, swapchain, command_pool, max_frames_in_flight=MAX_FRAMES_IN_FLIGHT)
    print("Frame loop ready")

    start_time = time.perf_counter()

    print("\nAll RHI objects created successfully. Rendering (close the window to exit)...\n")

    try:
        while not window.should_close:
            window.poll_events()

            result = frame_loop.begin_frame()
            if result is None:
                continue  # swapchain was recreated, skip this frame

            cmd, image_index = result
            frame_loop.begin_rendering(cmd, image_index)
            device.dispatch.vkCmdBindPipeline(cmd, vk.VkPipelineBindPoint.VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline.raw)

            # -- update this frame's uniform buffer with a rotating MVP matrix --
            elapsed = time.perf_counter() - start_time
            model = pyrr.matrix44.create_from_z_rotation(elapsed * np.deg2rad(45), dtype=np.float32)
            view = pyrr.matrix44.create_look_at(
                eye=np.array([0.0, 0.0, 2.0], dtype=np.float32),
                target=np.array([0.0, 0.0, 0.0], dtype=np.float32),
                up=np.array([0.0, 1.0, 0.0], dtype=np.float32),
            )
            aspect = swapchain.extent.width / swapchain.extent.height
            proj = pyrr.matrix44.create_perspective_projection(fovy=45, aspect=aspect, near=0.1, far=10.0, dtype=np.float32)
            proj[1][1] *= -1  # Vulkan clip space Y points down, unlike OpenGL

            ubo = UniformBufferObject()
            ubo.model = (ctypes.c_float * 16)(*np.ascontiguousarray(model).flatten())
            ubo.view = (ctypes.c_float * 16)(*np.ascontiguousarray(view).flatten())
            ubo.proj = (ctypes.c_float * 16)(*np.ascontiguousarray(proj).flatten())
            uniform_buffers[frame_loop.frame_index].update(ctypes.addressof(ubo), ctypes.sizeof(ubo))

            vbuf_arr = (vk.VkBuffer * 1)(vertex_buffer.raw)
            offsets = (ctypes.c_uint64 * 1)(0)
            device.dispatch.vkCmdBindVertexBuffers(cmd, 0, 1, vbuf_arr, offsets)
            device.dispatch.vkCmdBindIndexBuffer(cmd, index_buffer.raw, 0, index_buffer.index_type)
            descriptor_sets.bind(cmd, pipeline.layout, frame_loop.frame_index)
            device.dispatch.vkCmdDrawIndexed(cmd, index_buffer.count, 1, 0, 0, 0)

            frame_loop.end_frame(cmd, image_index)
    finally:
        device.wait_idle()
        frame_loop.destroy()
        descriptor_sets.destroy()
        for ubo_buf in uniform_buffers:
            ubo_buf.destroy()
        index_buffer.destroy()
        vertex_buffer.destroy()
        pipeline.destroy()
        command_pool.destroy()
        swapchain.destroy()
        device.destroy()
        surface.destroy()
        instance.destroy()
        window.close()
        print("Cleaned up successfully")


if __name__ == "__main__":
    main()