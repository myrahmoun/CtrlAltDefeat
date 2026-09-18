"""
app.py

Entry point. Runs entirely on the main thread until app.exec() is called,
at which point Qt's event loop takes over and everything from then on
happens in response to signals (worker updates) and events (clicks) — see
main_window.py for where that reactive code lives.

Connecting, creating or joining a game, and starting it are all handled by
the lobby screen (client/widgets/lobby_widgets.py), which MainWindow shows
first — so there's nothing to collect here.
"""
import sys
from PySide6.QtWidgets import QApplication

from client.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
