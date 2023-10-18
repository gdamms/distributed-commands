import requests
import subprocess
import time


REQUEST_DELAY = 0.3
NB_PENDING_DOTS = 4


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
        response = request.json()
        command = response['command']
        command_id = response['id']

        # Run the command.
        print(f'Running command `{command}`')
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        exit_code = process.returncode

        # Send the result.
        result = {
            'id': command_id,
            'exit_code': exit_code,
            'stdout': stdout.decode(),
            'stderr': stderr.decode(),
        }
        try:
            request = requests.post(url, json=result)
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f'Cannot reach {url}.')

        if request.status_code != 204:
            raise RuntimeError(f'Failed to send result: {request.text}')


if __name__ == '__main__':
    raise RuntimeError('This module is not meant to be executed directly')
