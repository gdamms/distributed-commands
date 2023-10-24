import time
import json

from lazython.line import Line


class Command:
    """A command to run on a slave.

    Attributes:
        ID (int): The ID of the next command.
    """
    ID: int = 0

    def __init__(
            self: 'Command',
            id: int = None,
            command: str = '',
            exit_code: int = None,
            stdout: str = None,
            stderr: str = None,
            start_time: float = None,
            end_time: float = None,
    ) -> None:
        """Constructor.

        Args:
            command (str): The command to run.
        """
        self.command: str = command
        self.exit_code: int = exit_code
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.start_time: float = start_time
        self.end_time: float = end_time
        self.line: 'Line | None' = None
        self.id: int = id
        if self.id is None:
            self.id = Command.ID
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
        result += f'\x1b[1mID:\x1b[0m {self.id}\n'
        result += f'\x1b[1mCommand:\x1b[0m\n{self.command}\n\n'
        if self.is_running():
            status = '\x1b[33mRunning 🏃\x1b[0m'
        elif self.is_ran():
            if self.exit_code != 0:
                status = '\x1b[31mFailed ❌\x1b[0m'
            else:
                status = '\x1b[32mSuccess ✔\x1b[0m'
        else:
            status = '\x1b[34mPending ⏱\x1b[0m'
        result += f'\x1b[1mStatus:\x1b[0m {status}\n'
        if self.start_time is not None:
            result += f'\x1b[1mStart time:\x1b[0m {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))}\n'
            end_time = self.end_time if self.end_time else time.time()
            elapsed_time = end_time - self.start_time
            s = int(elapsed_time % 60)
            m = int((elapsed_time // 60) % 60)
            h = int(elapsed_time // 3600)
            result += f'\x1b[1mElapsed time:\x1b[0m {h:02d}:{m:02d}:{s:02d}\n'
        if self.end_time is not None:
            result += f'\x1b[1mEnd time:\x1b[0m {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time))}\n'
        if self.exit_code is not None:
            result += f'\x1b[1mExit code:\x1b[0m \x1b[{32 if self.exit_code == 0 else 31}m{self.exit_code}\x1b[0m\n'
        return result

    def serialize(self: 'Command') -> str:
        """Serialize the command.

        Returns:
            str: The serialized command.
        """
        data = {
            'id': self.id,
            'command': self.command,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'start_time': self.start_time,
            'end_time': self.end_time,
        }
        return json.dumps(data)

    @staticmethod
    def deserialize(serialized: str) -> 'Command':
        """Deserialize a command.

        Args:
            serialized (str): The serialized command.

        Returns:
            Command: The deserialized command.
        """
        data = json.loads(serialized)
        return Command(
            id=data['id'],
            command=data['command'],
            exit_code=data['exit_code'],
            stdout=data['stdout'],
            stderr=data['stderr'],
            start_time=data['start_time'],
            end_time=data['end_time'],
        )
