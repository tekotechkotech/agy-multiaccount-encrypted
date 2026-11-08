import argparse
import sys
from pathlib import Path

try:
    from agy_account_switch.account_switch import (
        add_account,
        list_accounts,
        switch_account,
        remove_account,
    )
except ImportError:
    from .account_switch import (
        add_account,
        list_accounts,
        switch_account,
        remove_account,
    )


def register_account_subcommand(parser_or_subparsers) -> None:
    """Register the 'account' sub-command hierarchy.

    Can be called either with an ArgumentParser or an action returned by add_subparsers().
    """
    if hasattr(parser_or_subparsers, 'add_parser'):
        account_parser = parser_or_subparsers.add_parser('account', help='Manage multiple Antigravity accounts')
    else:
        subparsers = parser_or_subparsers.add_subparsers(dest='account_cmd')
        account_parser = subparsers.add_parser('account', help='Manage multiple Antigravity accounts')

    subparsers = account_parser.add_subparsers(dest='action', required=True)

    # add
    add_parser = subparsers.add_parser('add', help='Add a new account token')
    add_parser.add_argument('name', help='Logical account name')
    add_parser.add_argument('token', help='Authentication token string')
    add_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing token')
    add_parser.add_argument('--encrypt', action='store_true', help='Encrypt the token before storing')
    add_parser.set_defaults(func=_handle_add)

    # list
    list_parser = subparsers.add_parser('list', help='List stored accounts')
    list_parser.set_defaults(func=_handle_list)

    # switch
    switch_parser = subparsers.add_parser('switch', help='Switch active account')
    switch_parser.add_argument('name', help='Account name to activate')
    switch_parser.set_defaults(func=_handle_switch)

    # remove
    remove_parser = subparsers.add_parser('remove', help='Remove a stored account')
    remove_parser.add_argument('name', help='Account name to delete')
    remove_parser.set_defaults(func=_handle_remove)


def _handle_add(args: argparse.Namespace) -> None:
    try:
        encrypt = getattr(args, 'encrypt', False)
        add_account(args.name, args.token, overwrite=args.overwrite, encrypt=encrypt)
        status = " (encrypted)" if encrypt else ""
        print(f"Account '{args.name}' added successfully{status}.")
    except Exception as e:
        print(f"Error adding account: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_list(args: argparse.Namespace) -> None:
    accounts = list_accounts()
    if accounts:
        for acct in accounts:
            print(acct)
    else:
        print('No accounts found.')


def _handle_switch(args: argparse.Namespace) -> None:
    try:
        switch_account(args.name)
        print(f"Switched to account '{args.name}'.")
    except Exception as e:
        print(f"Error switching account: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_remove(args: argparse.Namespace) -> None:
    try:
        remove_account(args.name)
        print(f"Account '{args.name}' removed.")
    except Exception as e:
        print(f"Error removing account: {e}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> None:
    """CLI entry point for agy account switcher."""
    parser = argparse.ArgumentParser(prog='agy')
    register_account_subcommand(parser)

    # Allow direct subcommand invocation like `agy_account add ...` as well as `agy_account account add ...`
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in {'add', 'list', 'switch', 'remove'}:
        args_list.insert(0, 'account')

    parsed = parser.parse_args(args_list)
    if hasattr(parsed, 'func'):
        parsed.func(parsed)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
