import sys

from frontend.app import create_app


def main():
    app, window = create_app("dark")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()