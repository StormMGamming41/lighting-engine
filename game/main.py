
from engine.platform.window import Window

def main():
    window = Window(1280, 720, "My Engine")

    try:
        while not window.should_close:
            window.poll_events()
    finally:
        window.close()


if __name__ == "__main__":
    main()