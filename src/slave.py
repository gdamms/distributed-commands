import requests
import subprocess
import time
import threading
import select

from .command import Command


REQUEST_DELAY = 0.3
NB_PENDING_DOTS = 4


def sender(address: str, port: int, command: Command) -> None:
    """Send a command to the master.

    Args:
        address (str): The address of the master.
        port (int): The port of the master.
        command (Command): The command to send.
    """
    while command.is_running():
        data = command.serialize()
        try:
            request = requests.post(f'http://{address}:{port}', json=data)
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f'Cannot reach {address}:{port}.')

        if request.status_code != 204:
            raise RuntimeError(f'Failed to send command: {request.text}')

        time.sleep(REQUEST_DELAY)


def main(address: str, port: int):
    """Main function to run the slave.

    Args:
        address (str): The address of the master.
        port (int): The port of the master.

    Raises:
        RuntimeError: If the master is unreachable when retruning commands results.
        RuntimeError: If the master does not return a 204 status code when asking for a command.
    """
    url = f'http://{address}:{port}'

    connection_failed = False
    no_command_found = False
    loop_count = 0

    running = True
    while running:
        loop_count += 1

        # Get a command.
        try:
            request = requests.get(url)
        except requests.exceptions.ConnectionError:
            if not connection_failed:
                print(
                    f'\n' +
                    f'Cannot reach {url}.\n' +
                    f'Make sure a master is running on the targeted address with port {port}.\n' +
                    f'Keep in mind that the master address must be reachable from here.\n',
                )
                connection_failed = True
                no_command_found = False

            nb_dots = loop_count % NB_PENDING_DOTS + 1
            dots = nb_dots * '.' + (NB_PENDING_DOTS - nb_dots) * ' '
            print(f'\rRetrying{dots}', end='')

            time.sleep(REQUEST_DELAY)
            continue

        connection_failed = False

        # If the master is out of command, wait.
        if request.status_code == 204:
            if not no_command_found:
                print(
                    f'\n' +
                    f'Master is out of command.\n'
                )
                no_command_found = True

            nb_dots = loop_count % NB_PENDING_DOTS + 1
            dots = nb_dots * '.' + (NB_PENDING_DOTS - nb_dots) * ' '
            print(f'\rWaiting for orders{dots}', end='')

            time.sleep(REQUEST_DELAY)
            continue

        no_command_found = False

        # Parse the response.
        data = request.content.decode()
        command = Command.deserialize(data)

        # Run the command.
        print(f'Running command `{command.command}`')
        process = subprocess.Popen(command.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Send updates.
        command_thread = threading.Thread(target=sender, args=(address, port, command))
        command_thread.start()

        # Read stdout and stderr to update the command in real time.
        while process.poll() is None:
            ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
            for stream in ready:
                line = stream.readline()
                if line:
                    if stream == process.stdout:
                        if command.stdout is None:
                            command.stdout = ''
                        command.stdout += line.decode()
                    else:
                        if command.stderr is None:
                            command.stderr = ''
                        command.stderr += line.decode()

        # Update the command.
        command.exit_code = process.returncode
        command.end_time = time.time()
        command_thread.join()

        # Send the final result.
        data = command.serialize()
        try:
            request = requests.post(url, json=data)
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f'Cannot reach {url}.')

        if request.status_code != 204:
            raise RuntimeError(f'Failed to send result: {request.text}')


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
