import http.server
import threading
import time
import sys
import json

from lazython import Lazython

from .command import Command
from .vars import *


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
        Master.save()

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
                cur_command = Master.commands[i]
                cur_command.command = command.command
                cur_command.exit_code = command.exit_code
                cur_command.stdout = command.stdout
                cur_command.stderr = command.stderr
                cur_command.start_time = command.start_time
                cur_command.end_time = command.end_time
                break

        # Update the lazython.
        Master.update_lazython()
        Master.save()
        with open(os.path.join(STDOUT_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stdout)
        with open(os.path.join(STDERR_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stderr)

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
        Master.lazython.add_key(key=ord('a'),
                                callback=lambda: Master.request_command(),
                                name='a',
                                help='Add a command')
        Master.lazython.add_key(key=ord('A'),
                                callback=lambda: Master.request_file(),
                                name='A',
                                help='Add commands from a file')
        Master.lazython.add_key(key=ord('d'),
                                callback=lambda: Master.delete_command(),
                                name='d',
                                help='Delete a command')
        Master.lazython.add_key(key=ord('r'),
                                callback=lambda: Master.restart_command(),
                                name='r',
                                help='Restart a command')
        Master.lazython.add_key(key=ord('q'),
                                callback=lambda: Master.stop())
        Master.lazython.add_key(key=27,  # `esc`
                                callback=lambda: Master.stop())
        Master.lazython.add_key(key=0,  # `ctrl`+`c`
                                callback=lambda: Master.stop())
        Master.lazython.add_key(key=4741915,  # `home`
                                callback=lambda: Master.tab.scroll_up(-1))
        Master.lazython.add_key(key=4610843,  # `end`
                                callback=lambda: Master.tab.scroll_down(-1))

        threading.Thread(target=Master.serve, args=(address, port)).start()

        Master.load()
        Master.update_lazython()

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
        Master.save()

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
        Master.save()
        with open(os.path.join(STDOUT_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stdout)
        with open(os.path.join(STDERR_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stderr)

    @staticmethod
    def add_commands_from_file(path: str) -> None:
        """Add commands from a file to the commands list.

        Args:
            path (str): The path to the file.
        """
        try:
            with open(path, 'r') as file:
                for line in file.readlines():
                    if line[-1] == '\n':
                        line = line[:-1]
                    Master.add_command(line)
        except FileNotFoundError:
            return
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
        for command in Master.commands:
            # Get command color.
            if command.is_running():
                command_color = '\x1b[33m'
            elif command.is_ran():
                if command.exit_code != 0:
                    command_color = '\x1b[31m'
                else:
                    command_color = '\x1b[32m'
            else:
                command_color = '\x1b[34m'

            # Update the command line.
            text = command_color + command.command
            details = command.get_details()
            stdout = command.stdout
            stderr = command.stderr

            if command.line is None:
                line = Master.tab.add_line(
                    text=text,
                    subtexts=[details, stdout, stderr],
                )
                command.line = line
            else:
                line = command.line
                line.set_text(text)
                line.set_subtexts([details, stdout, stderr])

    @staticmethod
    def delete_command() -> None:
        """Delete a command."""
        line = Master.tab.get_selected_line()
        command = [command for command in Master.commands if command.line == line][0]
        if command.is_running():
            return
        Master.tab.delete_line(line)
        Master.commands.remove(command)
        Master.update_lazython()
        Master.save()
        os.remove(os.path.join(STDOUT_DIR, f'{command.id}.txt'))
        os.remove(os.path.join(STDERR_DIR, f'{command.id}.txt'))

    @staticmethod
    def restart_command() -> None:
        """Restart a command."""
        line = Master.tab.get_selected_line()
        command = [command for command in Master.commands if command.line == line][0]
        if not command.is_ran():
            return
        command.exit_code = None
        command.stdout = ''
        command.stderr = ''
        command.start_time = None
        command.end_time = None
        Master.update_lazython()
        Master.save()
        with open(os.path.join(STDOUT_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stdout)
        with open(os.path.join(STDERR_DIR, f'{command.id}.txt'), 'w') as file:
            file.write(command.stderr)

    @staticmethod
    def save() -> None:
        """Save the commands."""
        data = [command.serialize(no_std=True) for command in Master.commands]
        with open(COMMANDS_FILE, 'w') as file:
            json.dump(data, file)

    @staticmethod
    def load() -> None:
        """Load the commands."""
        # Load the commands.
        try:
            with open(COMMANDS_FILE, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            return

        # Update the id.
        for d in data:
            command = Command.deserialize(d)
            Master.commands.append(command)

        # Load the stdout and stderr.
        for command in Master.commands:
            try:
                with open(os.path.join(STDOUT_DIR, f'{command.id}.txt'), 'r') as file:
                    command.stdout = file.read()
            except FileNotFoundError:
                pass
            try:
                with open(os.path.join(STDERR_DIR, f'{command.id}.txt'), 'r') as file:
                    command.stderr = file.read()
            except FileNotFoundError:
                pass


def main(address: str, port: int):
    """Main function to run a master.

    Args:
        address (str): The address to listen to. (generally `localhost` or `0.0.0.0`)
        port (int): The port to listen to.
    """
    Master.start(address=address, port=port)


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
