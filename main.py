
# This scripts sole purpose is to test the engine and its features.

# Engine specific import
from engine import Engine

def main():

    app = Engine("Test Engine", (1280, 720), False)

    while not app.window.should_close():
        app.update()

if __name__ == "__main__":
    main()