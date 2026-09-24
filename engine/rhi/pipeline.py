
import ctypes
from ctypes import byref, c_int32, c_uint32, c_void_p, cast, pointer, POINTER
import vulkan_py as vk


def _check(result, op: str):
    if result != vk.VkResult.VK_SUCCESS:
        raise RuntimeError(f"Vulkan operation '{op}' failed: VkResult {result}")


def _load_shader_module(device, spirv_path: str):
    with open(spirv_path, "rb") as f:
        code = f.read()

    word_count = len(code) // 4
    buf = (c_uint32 * word_count).from_buffer_copy(code)

    create_info = vk.VkShaderModuleCreateInfo(
        codeSize=len(code),
        pCode=cast(buf, POINTER(c_uint32)),
    )
    module = vk.VkShaderModule()
    _check(
        device.dispatch.vkCreateShaderModule(create_info, None, byref(module)),
        "vkCreateShaderModule",
    )
    return module


class GraphicsPipeline:
    """RHI wrapper around descriptor set layout + pipeline layout + the graphics
    pipeline object itself. Uses dynamic rendering (no VkRenderPass/VkFramebuffer)
    and dynamic viewport/scissor, matching how the Device/Swapchain were set up.

    vertex_binding / vertex_attributes: your mesh format's own binding + attribute
    descriptions (built wherever your Vertex type lives, e.g. core/ or renderer/).
    descriptor_bindings: list of VkDescriptorSetLayoutBinding, or None/[] if the
    shaders don't use any descriptors yet.
    depth_format: pass the depth format if using a depth buffer, else None.
    """

    def __init__(
        self,
        device,
        color_format,
        vert_spirv_path: str,
        frag_spirv_path: str,
        vertex_binding=None,
        vertex_attributes=None,
        descriptor_bindings=None,
        depth_format=None,
        cull_mode=None,
        front_face=None,
    ):
        self.device = device
        self.color_format = color_format
        self.depth_format = depth_format
        # default: no culling until winding order is deliberately accounted for
        # (e.g. once a projection matrix flips Y for Vulkan's clip space)
        self.cull_mode = cull_mode if cull_mode is not None else vk.VkCullModeFlagBits.VK_CULL_MODE_NONE
        self.front_face = front_face if front_face is not None else vk.VkFrontFace.VK_FRONT_FACE_COUNTER_CLOCKWISE

        self.descriptor_set_layout = None
        self.layout = None
        self.raw = None

        self._create_descriptor_set_layout(descriptor_bindings or [])
        self._create_pipeline(vert_spirv_path, frag_spirv_path, vertex_binding, vertex_attributes)

    def _create_descriptor_set_layout(self, bindings):
        if not bindings:
            self.descriptor_set_layout = None
            return

        bindings_arr = (vk.VkDescriptorSetLayoutBinding * len(bindings))(*bindings)
        layout_info = vk.VkDescriptorSetLayoutCreateInfo(
            bindingCount=len(bindings),
            pBindings=cast(bindings_arr, POINTER(vk.VkDescriptorSetLayoutBinding)),
        )
        layout = vk.VkDescriptorSetLayout()
        _check(
            self.device.dispatch.vkCreateDescriptorSetLayout(byref(layout_info), None, byref(layout)),
            "vkCreateDescriptorSetLayout",
        )
        self.descriptor_set_layout = layout

    def _create_pipeline(self, vert_path, frag_path, vertex_binding, vertex_attributes):
        vert_module = _load_shader_module(self.device, vert_path)
        frag_module = _load_shader_module(self.device, frag_path)

        vert_stage = vk.VkPipelineShaderStageCreateInfo(
            stage=vk.VkShaderStageFlagBits.VK_SHADER_STAGE_VERTEX_BIT,
            module=vert_module,
            pName=b"main",
        )
        frag_stage = vk.VkPipelineShaderStageCreateInfo(
            stage=vk.VkShaderStageFlagBits.VK_SHADER_STAGE_FRAGMENT_BIT,
            module=frag_module,
            pName=b"main",
        )
        stages = (vk.VkPipelineShaderStageCreateInfo * 2)(vert_stage, frag_stage)

        if vertex_binding is not None:
            attr_arr = (vk.VkVertexInputAttributeDescription * len(vertex_attributes))(*vertex_attributes)
            vertex_input = vk.VkPipelineVertexInputStateCreateInfo(
                vertexBindingDescriptionCount=1,
                pVertexBindingDescriptions=pointer(vertex_binding),
                vertexAttributeDescriptionCount=len(vertex_attributes),
                pVertexAttributeDescriptions=attr_arr,
            )
        else:
            # no vertex buffers - shader generates geometry itself (e.g. via gl_VertexIndex)
            vertex_input = vk.VkPipelineVertexInputStateCreateInfo(
                vertexBindingDescriptionCount=0,
                vertexAttributeDescriptionCount=0,
            )

        input_assembly = vk.VkPipelineInputAssemblyStateCreateInfo(
            topology=vk.VkPrimitiveTopology.VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST
        )

        # viewport/scissor are set dynamically per-frame (vkCmdSetViewport/Scissor),
        # so we only need counts here, not actual values.
        viewport_state = vk.VkPipelineViewportStateCreateInfo(viewportCount=1, scissorCount=1)

        dynamic_states = [vk.VkDynamicState.VK_DYNAMIC_STATE_VIEWPORT, vk.VkDynamicState.VK_DYNAMIC_STATE_SCISSOR]
        dyn_states_arr = (c_int32 * len(dynamic_states))(*dynamic_states)
        dynamic_state = vk.VkPipelineDynamicStateCreateInfo(
            dynamicStateCount=len(dynamic_states),
            pDynamicStates=cast(dyn_states_arr, POINTER(c_int32)),
        )

        rasterizer = vk.VkPipelineRasterizationStateCreateInfo(
            polygonMode=vk.VkPolygonMode.VK_POLYGON_MODE_FILL,
            cullMode=self.cull_mode,
            frontFace=self.front_face,
            lineWidth=1.0,
        )

        multisampling = vk.VkPipelineMultisampleStateCreateInfo(
            rasterizationSamples=vk.VkSampleCountFlagBits.VK_SAMPLE_COUNT_1_BIT
        )

        color_blend_attachment = vk.VkPipelineColorBlendAttachmentState(blendEnable=0, colorWriteMask=0xF)
        color_blend = vk.VkPipelineColorBlendStateCreateInfo(
            attachmentCount=1, pAttachments=pointer(color_blend_attachment)
        )

        depth_stencil = None
        if self.depth_format is not None:
            depth_stencil = vk.VkPipelineDepthStencilStateCreateInfo(
                depthTestEnable=vk.VK_TRUE,
                depthWriteEnable=vk.VK_TRUE,
                depthCompareOp=vk.VkCompareOp.VK_COMPARE_OP_LESS,
                depthBoundsTestEnable=vk.VK_FALSE,
                stencilTestEnable=vk.VK_FALSE,
            )

        set_layouts = [self.descriptor_set_layout] if self.descriptor_set_layout is not None else []
        layout_info_kwargs = {"pushConstantRangeCount": 0}
        if set_layouts:
            layouts_arr = (vk.VkDescriptorSetLayout * len(set_layouts))(*set_layouts)
            layout_info_kwargs["setLayoutCount"] = len(set_layouts)
            layout_info_kwargs["pSetLayouts"] = cast(layouts_arr, POINTER(vk.VkDescriptorSetLayout))
        layout_info = vk.VkPipelineLayoutCreateInfo(**layout_info_kwargs)

        pipeline_layout = vk.VkPipelineLayout()
        _check(
            self.device.dispatch.vkCreatePipelineLayout(layout_info, None, byref(pipeline_layout)),
            "vkCreatePipelineLayout",
        )
        self.layout = pipeline_layout

        color_format_c = c_int32(self.color_format)
        rendering_info_kwargs = {
            "colorAttachmentCount": 1,
            "pColorAttachmentFormats": pointer(color_format_c),
        }
        if self.depth_format is not None:
            rendering_info_kwargs["depthAttachmentFormat"] = self.depth_format
        rendering_create_info = vk.VkPipelineRenderingCreateInfo(**rendering_info_kwargs)

        pipeline_info_kwargs = dict(
            pNext=cast(pointer(rendering_create_info), c_void_p),
            stageCount=2,
            pStages=cast(stages, POINTER(vk.VkPipelineShaderStageCreateInfo)),
            pVertexInputState=pointer(vertex_input),
            pInputAssemblyState=pointer(input_assembly),
            pViewportState=pointer(viewport_state),
            pDynamicState=pointer(dynamic_state),
            pRasterizationState=pointer(rasterizer),
            pMultisampleState=pointer(multisampling),
            pColorBlendState=pointer(color_blend),
            layout=pipeline_layout,
        )
        if depth_stencil is not None:
            pipeline_info_kwargs["pDepthStencilState"] = pointer(depth_stencil)

        pipeline_info = vk.VkGraphicsPipelineCreateInfo(**pipeline_info_kwargs)

        pipeline = vk.VkPipeline()
        _check(
            self.device.dispatch.vkCreateGraphicsPipelines(
                vk.VkPipelineCache(0), 1, byref(pipeline_info), None, byref(pipeline)
            ),
            "vkCreateGraphicsPipelines",
        )
        self.raw = pipeline

        # shader modules are only needed during pipeline creation, not after
        self.device.dispatch.vkDestroyShaderModule(vert_module, None)
        self.device.dispatch.vkDestroyShaderModule(frag_module, None)

    def destroy(self):
        if self.raw is not None:
            self.device.dispatch.vkDestroyPipeline(self.raw, None)
            self.raw = None
        if self.layout is not None:
            self.device.dispatch.vkDestroyPipelineLayout(self.layout, None)
            self.layout = None
        if self.descriptor_set_layout is not None:
            self.device.dispatch.vkDestroyDescriptorSetLayout(self.descriptor_set_layout, None)
            self.descriptor_set_layout = None