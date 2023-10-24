import http.server
import threading
import time
import sys
import json

from lazython import Lazython, renderer

from .command import Command


class Master(http.server.BaseHTTPRequestHandler):
    """A master.

    Attributes:
        commands (list[Command]): The commands to run.
    """

    commands: list[Command] = []
    running: bool = False
    lazython: Lazython = None
    to_call: list[callable] = []

    def do_GET(self: 'Master') -> None:
        """Handle a GET request."""

        # Choose a command to run.
        command = Master.choose_command()
        if command is None:
            # No command to run for now.
            self.send_response(204)
            self.end_headers()
            return

        # Send the command to run.
        data = command.serialize()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data.encode())

        # Update the lazython.
        Master.update_lazython()

    def do_POST(self: 'Master') -> None:
        """Handle a POST request."""

        # Read the data.
        content_length = int(self.headers['Content-Length'])
        data = self.rfile.read(content_length)

        # Send a 204 response.
        self.send_response(204)
        self.end_headers()

        # Decode the data.
        data = json.loads(data)
        command = Command.deserialize(data)

        # Update the command.
        for i, c in enumerate(Master.commands):
            if c.id == command.id:
                Master.commands[i] = command
                break

        # Update the lazython.
        Master.update_lazython()

    def log_message(self, format, *args) -> None:
        """Log a message. This is a dummy method to avoid logging."""
        return

    @staticmethod
    def start(address: str, port: int) -> None:
        """Start the master.

        Args:
            address (str): The address to listen to. (generally `localhost` or `0.0.0.0`)
            port (int): The port to listen to.
        """
        Master.running = True

        Master.lazython = Lazython()
        Master.tab = Master.lazython.new_tab(
            name='Commands',
            subtabs=['Info', 'Stdout', 'Stderr'],
        )
        Master.lazython.add_key(ord('a'), lambda: Master.request_command())
        Master.lazython.add_key(ord('A'), lambda: Master.request_file())
        Master.lazython.add_key(ord('q'), lambda: Master.stop())
        Master.lazython.add_key(27, lambda: Master.stop())  # `esc`
        Master.lazython.add_key(0, lambda: Master.stop())  # `ctrl`+`c`
        Master.lazython.add_key(4741915, lambda: Master.tab.scroll_up(-1))  # `home`
        Master.lazython.add_key(4610843, lambda: Master.tab.scroll_down(-1))  # `end`

        threading.Thread(target=Master.serve, args=(address, port)).start()
        Master.main()

    @staticmethod
    def main() -> None:
        """Main function to run a master."""
        while Master.running:
            Master.lazython.start()
            while Master.to_call:
                Master.to_call.pop(0)()

    @staticmethod
    def stop() -> None:
        """Stop the master."""
        Master.running = False
        try:
            Master.lazython.stop()
        except:
            pass

    @staticmethod
    def request_command() -> None:
        """Request a command to run."""

        def f():
            # Choose a command to run.
            sys.stdout.write('Command: ')
            command = input()
            Master.add_command(command)

        Master.to_call.append(f)
        Master.lazython.stop()

    @staticmethod
    def request_file() -> None:
        """Request a file to add commands from."""

        def f():
            # Choose a file to add commands from.
            sys.stdout.write('File: ')
            path = input()
            Master.add_commands_from_file(path)

        Master.to_call.append(f)
        Master.lazython.stop()

    @staticmethod
    def add_command(command: str | Command) -> None:
        """Add a command to the commands list.

        Args:
            command (str | Command): The command to add.
        """
        if isinstance(command, str):
            if command == '' or command.isspace():
                return
            command = Command(command=command)
        Master.commands.append(command)
        Master.update_lazython()

    @staticmethod
    def add_commands_from_file(path: str) -> None:
        """Add commands from a file to the commands list.

        Args:
            path (str): The path to the file.
        """
        with open(path, 'r') as file:
            for line in file.readlines():
                if line[-1] == '\n':
                    line = line[:-1]
                Master.add_command(line)
        Master.update_lazython()

    @staticmethod
    def choose_command() -> Command:
        """Choose a command to run.

        Returns:
            Command: The command to run.
        """
        for command in Master.commands:
            if command.is_choosable():
                command.start_time = time.time()
                return command
        return None

    @staticmethod
    def serve(address: str, port: int) -> None:
        """Serve the master.

        Args:
            address (str): The address to listen to. (generally `localhost` or `0.0.0.0`)
            port (int): The port to listen to.
        """
        httpd = http.server.HTTPServer((address, port), Master)
        httpd.timeout = 0.1
        while Master.running:
            httpd.handle_request()

    @staticmethod
    def update_lazython() -> None:
        """Update the lazython according to the commands."""
        # Check if need to auto scroll.
        tab_subtext = Master.tab.get_selected_subtext()
        tab_scroll = Master.tab.get_content_scroll()
        tab_height = Master.tab.get_content_height()
        tab_width = Master.tab.get_content_width()
        subtext_height = renderer.Renderer.get_size(tab_subtext, tab_width)[1]
        max_scroll = max(0, subtext_height - tab_height)
        auto_scroll = tab_scroll >= max_scroll

        Master.tab.clear_lines()
        for command in Master.commands:
            if command.is_running():
                command_color = '\x1b[33m'
            elif command.is_ran():
                if command.exit_code != 0:
                    command_color = '\x1b[31m'
                else:
                    command_color = '\x1b[32m'
            else:
                command_color = '\x1b[34m'
            text = command_color + command.command
            details = command.get_details()
            stdout = command.stdout if command.stdout is not None else ''
            stderr = command.stderr if command.stderr is not None else ''
            Master.tab.add_line(text=text, subtexts=[details, stdout, stderr])

        if auto_scroll:
            # Auto scroll.
            tab_subtext = Master.tab.get_selected_subtext()
            tab_scroll = Master.tab.get_content_scroll()
            tab_height = Master.tab.get_content_height()
            tab_width = Master.tab.get_content_width()
            subtext_height = renderer.Renderer.get_size(tab_subtext, tab_width)[1]
            max_scroll = max(0, subtext_height - tab_height)
            Master.tab.scroll_down(max_scroll - tab_scroll)


def main(address: str, port: int):
    """Main function to run a master.

    Args:
        address (str): The address to listen to. (generally `localhost` or `0.0.0.0`)
        port (int): The port to listen to.
    """
    Master.start(address=address, port=port)


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
