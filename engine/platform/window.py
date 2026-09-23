
import glfw

class Window:
    def __init__(self, width: int, height: int, title: str):
        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW")

        # We're not using OpenGL, so tell GLFW not to create a GL context.
        # Vulkan surface creation happens later, against this same window handle.
        glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)

        self.width = width
        self.height = height
        self.title = title

        self._handle = glfw.create_window(width, height, title, None, None)
        if not self._handle:
            glfw.terminate()
            raise RuntimeError("Failed to create GLFW window")

    @property
    def handle(self):
        """Raw GLFW window handle. RHI will need this for Vulkan surface creation."""
        return self._handle

    @property
    def should_close(self) -> bool:
        return glfw.window_should_close(self._handle)

    def poll_events(self):
        glfw.poll_events()

    def close(self):
        if self._handle:
            glfw.destroy_window(self._handle)
            self._handle = None
        glfw.terminate()