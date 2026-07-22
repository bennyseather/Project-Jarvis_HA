"""
Project Jarvis

Application entry point.
"""

from jarvis.core.application import JarvisApplication


def main():
    """
    Start Project Jarvis.
    """

    app = JarvisApplication()

    app.run()


if __name__ == "__main__":
    main()