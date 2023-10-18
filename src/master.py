import http.server
import json
import threading
import time
import sys

from lazython import Lazython


class Command:
    """A command to run on a slave.

    Attributes:
        ID (int): The ID of the next command.
    """
    ID: int = 0

    def __init__(self: 'Command', command: str) -> None:
        """Constructor.

        Args:
            command (str): The command to run.
        """
        self.command: str = command
        self.exit_code: int = None
        self.stdout: str = None
        self.stderr: str = None
        self.start_time: float = None
        self.end_time: float = None
        self.id: int = Command.ID
        Command.ID += 1

    def is_running(self: 'Command') -> bool:
        """Whether the command is running.

        Returns:
            bool: Whether the command is running.
        """
        return self.start_time is not None and self.end_time is None

    def is_ran(self: 'Command') -> bool:
        """Whether the command has been runned.

        Returns:
            bool: Whether the command has been runned.
        """
        return self.end_time is not None

    def is_choosable(self: 'Command') -> bool:
        """Whether the command is chosable.

        Returns:
            bool: Whether the command is chosable.
        """
        return not self.is_running() and not self.is_ran()

    def start(self: 'Command') -> None:
        """Start the command."""
        self.start_time = time.time()
        Master.update_lazython()

    def stop(self: 'Command', exit_code: int, stdout: str, stderr: str) -> None:
        """Stop the command.

        Args:
            exit_code (int): The exit code of the command.
            stdout (str): The stdout of the command.
            stderr (str): The stderr of the command.
        """
        self.end_time = time.time()
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        Master.update_lazython()

    def __str__(self: 'Command') -> str:
        """Get a string representation of the command.

        Returns:
            str: A string representation of the command.
        """
        return f'{self.command}'

    def get_details(self: 'Command') -> str:
        """Get a string representation of the command details.

        Returns:
            str: A string representation of the command details.
        """
        result = ''
        result += f'ID: {self.id}\n'
        result += f'Command: {self.command}\n'
        if self.start_time is not None:
            result += f'Start time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))}\n'
        if self.end_time is not None:
            result += f'End time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time))}\n'
        if self.exit_code is not None:
            result += f'Exit code: {self.exit_code}\n'
        return result


class Master(http.server.BaseHTTPRequestHandler):
    """A master.

    Attributes:
        commands (list[Command]): The commands to run.
    """

    commands: list[Command] = []
    running: bool = False

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
        response = {
            'id': command.id,
            'command': command.command,
        }
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self: 'Master') -> None:
        """Handle a POST request."""

        # Read the data.
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Send a 204 response.
        self.send_response(204)
        self.end_headers()

        # Decode the data.
        post_data = post_data.decode()
        post_data = json.loads(post_data)

        command_id = post_data['id']
        exit_code = post_data['exit_code']
        stdout = post_data['stdout']
        stderr = post_data['stderr']

        # Stop the command.
        command = [command for command in Master.commands if command.id == command_id][0]
        command.stop(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

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

        threading.Thread(target=lambda: Master.serve(address=address, port=port)).start()
        Master.lazython.start()
        Master.stop()

    @staticmethod
    def stop() -> None:
        """Stop the master."""
        Master.running = False

    @staticmethod
    def request_command() -> None:
        """Request a command to run."""
        Master.lazython.stop()

        # Choose a command to run.
        sys.stdout.write('Command: ')
        try:
            command = input()
            Master.add_command(command)
        except KeyboardInterrupt:
            pass

        Master.lazython.start()

    @staticmethod
    def request_file() -> None:
        """Request a file to add commands from."""
        Master.lazython.stop()

        # Choose a file to add commands from.
        sys.stdout.write('File: ')
        try:
            path = input()
            Master.add_commands_from_file(path)
        except KeyboardInterrupt:
            pass

        Master.lazython.start()

    @staticmethod
    def add_command(command: str | Command) -> None:
        """Add a command to the commands list.

        Args:
            command (str | Command): The command to add.
        """
        if isinstance(command, str):
            if command == '' or command.isspace():
                return
            command = Command(command)
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
                Master.add_command(line[:-1])
        Master.update_lazython()

    @staticmethod
    def choose_command() -> Command:
        """Choose a command to run.

        Returns:
            Command: The command to run.
        """
        for command in Master.commands:
            if command.is_choosable():
                command.start()
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
        Master.tab.clear_lines()
        for command in Master.commands:
            text = command.command
            details = command.get_details()
            stdout = command.stdout if command.stdout is not None else ''
            stderr = command.stderr if command.stderr is not None else ''
            Master.tab.add_line(text=text, subtexts=[details, stdout, stderr])


def main(address: str, port: int):
    """Main function to run a master.

    Args:
        address (str): The address to listen to. (generally `localhost` or `0.0.0.0`)
        port (int): The port to listen to.
    """
    Master.start(address=address, port=port)


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
