import os

HOME = os.environ.get('HOME', '~')
XDG_DATA_HOME = os.environ.get('XDG_DATA_HOME', os.path.join(HOME, '.local', 'share'))

WORKING_DIR = os.path.join(XDG_DATA_HOME, 'distributhon')

STDOUT_DIR = os.path.join(WORKING_DIR, 'stdout')
STDERR_DIR = os.path.join(WORKING_DIR, 'stderr')
COMMANDS_FILE = os.path.join(WORKING_DIR, 'commands.json')


# Generate paths.
for path in (WORKING_DIR, STDOUT_DIR, STDERR_DIR):
    if not os.path.exists(path):
        os.makedirs(path)
