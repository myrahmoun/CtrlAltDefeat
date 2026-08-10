"""
app.py

Entry point. Runs entirely on the main thread until app.exec() is called,
at which point Qt's event loop takes over and everything from then on
happens in response to signals (worker updates) and events (clicks) — see
main_window.py for where that reactive code lives.

TEMPORARY: game_id and player_name are collected here via simple dialogs
and passed straight to MainWindow, which joins automatically on startup.
This stands in for the real lobby screen (see widgets/lobby_widget.py for
its planned shape) until that's built.
"""
import sys
from PySide6.QtWidgets import QApplication, QInputDialog

from client.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    server_address, ok = QInputDialog.getText(
        None, "Connect to server", "Server address (e.g. localhost:50051):"
    )
    if not ok or not server_address:
        sys.exit(0)

    game_id, ok = QInputDialog.getText(
        None, "Join game", "Game ID to join (leave blank to create a new game):"
    )
    if not ok:
        sys.exit(0)

    player_name, ok = QInputDialog.getText(None, "Your name", "Player name:")
    if not ok or not player_name:
        sys.exit(0)

    window = MainWindow(server_address)
    window.show()
    window.auto_join(game_id.strip(), player_name.strip())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()