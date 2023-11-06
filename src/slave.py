import requests
import subprocess
import time
import threading
import select
import sys

from .command import Command
from .vars import *


def sender(url: str, command: Command, process: subprocess.Popen) -> None:
    """Send a command to the master.

    Args:
        url (str): The URL of the master.
        command (Command): The command to send.
        process (subprocess.Popen): The process to send updates from.
    """
    while command.is_running():
        data = command.serialize()
        try:
            request = requests.post(url, json=data)
        except requests.exceptions.ConnectionError:
            # Ignore connection errors.
            time.sleep(REQUEST_DELAY)
            continue

        if request.status_code == 204:
            time.sleep(REQUEST_DELAY)
            continue

        # If the master does not return a 204 status code, stop the command.
        process.kill()
        sys.stdout.write(f'\n\n')
        sys.stdout.write(f'Failed to send updates: {request.text}\n')
        sys.stdout.flush()
        return

    # Send the final result.
    data = command.serialize()
    sent = False
    connection_failed = False
    loop_count = 0
    while not sent:
        try:
            request = requests.post(url, json=data)
            sent = True
        except requests.exceptions.ConnectionError:
            if not connection_failed:
                sys.stdout.write(f'\n\n')
                sys.stdout.write(f'Cannot reach {url} to send the final result.\n')
                sys.stdout.write(f'Make sure a master is running on the targeted address with the correct port.\n')
                sys.stdout.write(f'Keep in mind that the master address must be reachable from here.\n')

                connection_failed = True

            nb_dots = loop_count % NB_PENDING_DOTS + 1
            loop_count += 1
            dots = nb_dots * '.' + (NB_PENDING_DOTS - nb_dots) * ' '
            sys.stdout.write(f'\rRetrying{dots}')
            sys.stdout.flush()

            # Keep trying.
            time.sleep(REQUEST_DELAY)
            continue

    if request.status_code == 204:
        return

    sys.stdout.write(f'\n\n')
    sys.stdout.write(f'Failed to send the final result: {request.text}\n')
    sys.stdout.flush()


def read_output(process: subprocess.Popen, command: Command) -> None:
    """Read the output of a process.

    Args:
        process (subprocess.Popen): The process to read the output from.
        command (Command): The command to update.
    """
    while process.poll() is None and command.is_running():
        ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
        for stream in ready:
            line = stream.readline()
            if line:
                if stream == process.stdout:
                    command.stdout += line.decode()
                else:
                    command.stderr += line.decode()


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
                sys.stdout.write(f'\n\n')
                sys.stdout.write(f'Cannot reach {url}.\n')
                sys.stdout.write(f'Make sure a master is running on the targeted address with port {port}.\n')
                sys.stdout.write(f'Keep in mind that the master address must be reachable from here.\n')

                connection_failed = True
                no_command_found = False

            nb_dots = loop_count % NB_PENDING_DOTS + 1
            dots = nb_dots * '.' + (NB_PENDING_DOTS - nb_dots) * ' '
            sys.stdout.write(f'\rRetrying{dots}')
            sys.stdout.flush()

            time.sleep(REQUEST_DELAY)
            continue

        connection_failed = False

        # If the master is out of command, wait.
        if request.status_code == 204:
            if not no_command_found:
                sys.stdout.write(f'\n\n')
                sys.stdout.write(f'Master is out of command.\n')

                no_command_found = True

            nb_dots = loop_count % NB_PENDING_DOTS + 1
            dots = nb_dots * '.' + (NB_PENDING_DOTS - nb_dots) * ' '
            sys.stdout.write(f'\rWaiting for orders{dots}')

            time.sleep(REQUEST_DELAY)
            continue

        no_command_found = False

        # Parse the response.
        data = request.content.decode()
        command = Command.deserialize(data)

        # Run the command.
        sys.stdout.write(f'\n\nRunning command `{command.command}`\n')
        sys.stdout.flush()

        process = subprocess.Popen(command.command, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, preexec_fn=lambda: os.setpgrp())

        # Send updates.
        command_thread = threading.Thread(target=sender, args=(url, command, process))
        command_thread.start()

        # Read the output.
        reader_thread = threading.Thread(target=read_output, args=(process, command))
        reader_thread.start()

        # Wait for the process to end.
        while process.poll() is None:
            try:
                process.wait()
            except KeyboardInterrupt:
                sys.stdout.write('\n\n')
                sys.stdout.write('You pressed `ctrl` + `c`.\n')
                sys.stdout.write('Are you sure you want to stop the command?\n')
                sys.stdout.write('y: Yes, stop the current command and continue the next one.\n')
                sys.stdout.write('n: No, continue the command.\n')
                sys.stdout.write('w: Wait, continue the command then stop the slave.\n')
                sys.stdout.write('s: Stop, stop the command and the slave.\n')
                sys.stdout.write('Your choice [y/N/w/s]: ')
                sys.stdout.flush()

                # Wait for the user to choose.
                choice = input()
                if choice.lower() == 'y':
                    process.kill()
                elif choice.lower() == 'n':
                    pass
                elif choice.lower() == 'w':
                    running = False
                elif choice.lower() == 's':
                    process.kill()
                    running = False
                else:
                    # If the user did not choose, continue the command.
                    pass

        # Read the remaining output.
        ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0)
        for stream in ready:
            line = stream.readline()
            if line:
                if stream == process.stdout:
                    command.stdout += line.decode()
                else:
                    command.stderr += line.decode()

        # Update the command.
        command.exit_code = process.returncode
        command.end_time = time.time()

        # Make sure the threads are done.
        command_thread.join()
        reader_thread.join()
        process.wait()


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
