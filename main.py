import argparse
import rich_argparse

import src.master as master
import src.slave as slave


if __name__ == '__main__':
    # Parse command line arguments.
    parser = argparse.ArgumentParser(
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
        description="""
This program allows you to distribute tasks to multiple computers.

The `master` command starts a master, which is responsible for distributing tasks to slaves.
The master will use the `address` and `port` arguments to listen for incoming connections.
You might want to use the `--address 0.0.0.0` argument to listen on all interfaces.

The `slave` command starts a slave, which is responsible for executing tasks.
The slave will use the `address` and `port` arguments to connect to the master.
""")
    parser.set_defaults(run=lambda args: parser.print_help())

    parser.add_argument(
        '--address',
        type=str,
        default='localhost',
        dest='address',
        help='address to use',
    )

    parser.add_argument(
        '--port',
        type=int,
        default=34923,
        dest='port',
        help='port to use',
    )

    subparser = parser.add_subparsers()

    slave_parser = subparser.add_parser(
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
        name='master',
        help='starts a master',
        description="""""",
    )
    slave_parser.set_defaults(run=lambda args: master.main(address=args.address, port=args.port))

    client_parser = subparser.add_parser(
        formatter_class=rich_argparse.RawDescriptionRichHelpFormatter,
        name='slave',
        help='starts a slave',
        description="""""",
    )
    client_parser.set_defaults(run=lambda args: slave.main(address=args.address, port=args.port))

    args = parser.parse_args()
    args.run(args)
