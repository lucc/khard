"""Command line parsing and configuration logic for khard"""

import argparse
import logging
import sys
from typing import List, Tuple

from .actions import Actions
from .carddav_object import CarddavObject
from .config import Config, ConfigError
from .version import version as khard_version


logger = logging.getLogger(__name__)


def field_argument(orignal: str) -> List[str]:
    """Ensure the fields specified for `ls -F` are proper field names.
    Nested attribute names are not checked.

    :param orignal: the value from the command line
    :returns: the orignal value split at "," if the fields are spelled correctly
    :throws: argparse.ArgumentTypeError
    """
    special_fields = ['index', 'name', 'phone', 'email']
    properties = [name for name in dir(CarddavObject)
                  if isinstance(getattr(CarddavObject, name), property)]
    choices = sorted(special_fields + properties)
    ret = []
    for candidate in orignal.split(','):
        candidate = candidate.lower()
        field = candidate.split('.')[0]
        if field in choices:
            ret.append(candidate)
        else:
            raise argparse.ArgumentTypeError(
                '"{}" is not an accepted field. Accepted fields are {}.'.format(
                    field, ', '.join('"{}"'.format(c) for c in choices)))
    return ret


def create_parsers() -> Tuple[argparse.ArgumentParser,
                              argparse.ArgumentParser]:
    """Create two argument parsers.

    The first parser is manly used to find the config file which can than be
    used to set some default values on the second parser.  The second parser
    can parse the remainder of the command line with the subcommand and all
    further options and arguments.

    :returns: the two parsers for the first and the second parsing pass
    :rtype: (argparse.ArgumentParser, argparse.ArgumentParser)
    """
    # Create the base argument parser.  It will be reused for the first and
    # second round of argument parsing.
    base = argparse.ArgumentParser(
        description="Khard is a carddav address book for the console",
        formatter_class=argparse.RawTextHelpFormatter, add_help=False)
    base.add_argument("-c", "--config", help="config file to use")
    base.add_argument("--debug", action="store_true",
                      help="enable debug output")
    base.add_argument("--skip-unparsable", action="store_true",
                      help="skip unparsable vcard files")
    base.add_argument("-v", "--version", action="version",
                      version="Khard version {}".format(khard_version))

    # Create the first argument parser.  Its main job is to set the correct
    # config file.  The config file is needed to get the default command if no
    # subcommand is given on the command line.  This parser will ignore most
    # arguments, as they will be parsed by the second parser.
    first_parser = argparse.ArgumentParser(parents=[base])
    first_parser.add_argument('remainder', nargs=argparse.REMAINDER)

    # Create the main argument parser.  It will handle the complete command
    # line only ignoring the config and debug options as these have already
    # been set.
    parser = argparse.ArgumentParser(parents=[base])

    # create address book subparsers with different help texts
    default_addressbook_parser = argparse.ArgumentParser(add_help=False)
    default_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of contacts")
    new_addressbook_parser = argparse.ArgumentParser(add_help=False)
    new_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify address book in which to create the new contact")
    copy_move_addressbook_parser = argparse.ArgumentParser(add_help=False)
    copy_move_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of contacts")
    copy_move_addressbook_parser.add_argument(
        "-A", "--target-addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify target address book in which to copy / move the "
        "selected contact")
    merge_addressbook_parser = argparse.ArgumentParser(add_help=False)
    merge_addressbook_parser.add_argument(
        "-a", "--addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of source contacts")
    merge_addressbook_parser.add_argument(
        "-A", "--target-addressbook", default=[],
        type=lambda x: [y.strip() for y in x.split(",")],
        help="Specify one or several comma separated address book names to "
        "narrow the list of target contacts")

    # create input file subparsers with different help texts
    email_header_input_file_parser = argparse.ArgumentParser(add_help=False)
    email_header_input_file_parser.add_argument(
        "-i", "--input-file", default="-",
        help="Specify input email header file name or use stdin by default")
    template_input_file_parser = argparse.ArgumentParser(add_help=False)
    template_input_file_parser.add_argument(
        "-i", "--input-file", default="-",
        help="Specify input template file name or use stdin by default")
    template_input_file_parser.add_argument(
        "--open-editor", "--edit", action="store_true", help="Open the "
        "default text editor after successful creation of new contact")

    # create sort subparser
    sort_parser = argparse.ArgumentParser(add_help=False)
    sort_parser.add_argument(
        "-d", "--display",
        choices=("first_name", "last_name", "formatted_name"),
        help="Display names in contact table by first or last name")
    sort_parser.add_argument(
        "-g", "--group-by-addressbook", action="store_true",
        help="Group contact table by address book")
    sort_parser.add_argument(
        "-r", "--reverse", action="store_true",
        help="Reverse order of contact table")
    sort_parser.add_argument(
        "-s", "--sort", choices=("first_name", "last_name", "formatted_name"),
        help="Sort contact table by first or last name")

    # create search subparsers
    default_search_parser = argparse.ArgumentParser(add_help=False)
    default_search_parser.add_argument(
        "-f", "--search-in-source-files", action="store_true",
        help="Look into source vcf files to speed up search queries in "
        "large address books. Beware that this option could lead "
        "to incomplete results.")
    default_search_parser.add_argument(
        "-e", "--strict-search", action="store_true",
        help="narrow contact search to name field")
    default_search_parser.add_argument(
        "-u", "--uid", default="", help="select contact by uid")
    default_search_parser.add_argument(
        "search_terms", nargs="*", metavar="search terms",
        help="search in all fields to find matching contact")
    merge_search_parser = argparse.ArgumentParser(add_help=False)
    merge_search_parser.add_argument(
        "-f", "--search-in-source-files", action="store_true",
        help="Look into source vcf files to speed up search queries in "
        "large address books. Beware that this option could lead "
        "to incomplete results.")
    merge_search_parser.add_argument(
        "-e", "--strict-search", action="store_true",
        help="narrow contact search to name fields")
    merge_search_parser.add_argument(
        "-t", "--target-contact", "--target", default="",
        help="search in all fields to find matching target contact")
    merge_search_parser.add_argument(
        "-u", "--uid", default="", help="select source contact by uid")
    merge_search_parser.add_argument(
        "-U", "--target-uid", default="", help="select target contact by uid")
    merge_search_parser.add_argument(
        "source_search_terms", nargs="*", metavar="source",
        help="search in all fields to find matching source contact")

    # create subparsers for actions
    subparsers = parser.add_subparsers(dest="action")
    list_parser = subparsers.add_parser(
        "list",
        aliases=Actions.get_aliases("list"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list all (selected) contacts",
        help="list all (selected) contacts")
    list_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: uid\\tcontact_name\\taddress_book_name")
    list_parser.add_argument(
        "-F", "--fields", default=[], type=field_argument,
        help="Comma separated list of fields to show")
    show_parser = subparsers.add_parser(
        "show",
        aliases=Actions.get_aliases("show"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="display detailed information about one contact",
        help="display detailed information about one contact")
    show_parser.add_argument(
        "--format", choices=("pretty", "yaml", "vcard"), default="pretty",
        help="select the output format")
    show_parser.add_argument(
        "-o", "--output-file", default=sys.stdout,
        type=argparse.FileType("w"),
        help="Specify output template file name or use stdout by default")
    subparsers.add_parser("template", help="print an empty yaml template")
    export_parser = subparsers.add_parser(
        "export",
        aliases=Actions.get_aliases("export"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="DEPRECATED (an alias for 'show --format=yaml')",
        help="DEPRECATED (an alias for 'show --format=yaml')")
    export_parser.add_argument(
        "-o", "--output-file", default=sys.stdout,
        type=argparse.FileType("w"),
        help="Specify output template file name or use stdout by default")
    birthdays_parser = subparsers.add_parser(
        "birthdays",
        aliases=Actions.get_aliases("birthdays"),
        parents=[default_addressbook_parser, default_search_parser],
        description="list birthdays (sorted by month and day)",
        help="list birthdays (sorted by month and day)")
    birthdays_parser.add_argument(
        "-d", "--display",
        choices=("first_name", "last_name", "formatted_name"),
        help="Display names in birthdays table by first or last name")
    birthdays_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: name\\tdate")
    email_parser = subparsers.add_parser(
        "email",
        aliases=Actions.get_aliases("email"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list email addresses",
        help="list email addresses")
    email_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: address\\tname\\ttype")
    email_parser.add_argument(
        "--remove-first-line", action="store_true",
        help="remove \"searching for '' ...\" line from parsable output "
        "(that line is required by mutt)")
    phone_parser = subparsers.add_parser(
        "phone",
        aliases=Actions.get_aliases("phone"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list phone numbers",
        help="list phone numbers")
    phone_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: number\\tname\\ttype")
    post_address_parser = subparsers.add_parser(
        "postaddress",
        aliases=Actions.get_aliases("postaddress"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list postal addresses",
        help="list postal addresses")
    post_address_parser.add_argument(
        "-p", "--parsable", action="store_true",
        help="Machine readable format: address\\tname\\ttype")
    subparsers.add_parser(
        "source",
        aliases=Actions.get_aliases("source"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="DEPRECATED (an alias for 'edit --format=vcard')",
        help="DEPRECATED (an alias for 'edit --format=vcard')")
    new_parser = subparsers.add_parser(
        "new",
        aliases=Actions.get_aliases("new"),
        parents=[new_addressbook_parser, template_input_file_parser],
        description="create a new contact",
        help="create a new contact")
    new_parser.add_argument(
        "--vcard-version", choices=("3.0", "4.0"), dest='preferred_version',
        help="Select preferred vcard version for new contact")
    add_email_parser = subparsers.add_parser(
        "add-email",
        aliases=Actions.get_aliases("add-email"),
        parents=[default_addressbook_parser, email_header_input_file_parser,
                 default_search_parser, sort_parser],
        description="Extract email address from the \"From:\" field of an "
        "email header and add to an existing contact or create a new one",
        help="Extract email address from the \"From:\" field of an email "
        "header and add to an existing contact or create a new one")
    add_email_parser.add_argument(
        "--vcard-version", choices=("3.0", "4.0"), dest='preferred_version',
        help="Select preferred vcard version for new contact")
    subparsers.add_parser(
        "merge",
        aliases=Actions.get_aliases("merge"),
        parents=[merge_addressbook_parser, merge_search_parser, sort_parser],
        description="merge two contacts",
        help="merge two contacts")
    edit_parser = subparsers.add_parser(
        "edit",
        aliases=Actions.get_aliases("edit"),
        parents=[default_addressbook_parser, template_input_file_parser,
                 default_search_parser, sort_parser],
        description="edit the data of a contact",
        help="edit the data of a contact")
    edit_parser.add_argument(
        "--format", choices=("yaml", "vcard"), default="yaml",
        help="specify the file format to use when editing")
    subparsers.add_parser(
        "copy",
        aliases=Actions.get_aliases("copy"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="copy a contact to a different addressbook",
        help="copy a contact to a different addressbook")
    subparsers.add_parser(
        "move",
        aliases=Actions.get_aliases("move"),
        parents=[copy_move_addressbook_parser, default_search_parser,
                 sort_parser],
        description="move a contact to a different addressbook",
        help="move a contact to a different addressbook")
    remove_parser = subparsers.add_parser(
        "remove",
        aliases=Actions.get_aliases("remove"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="remove a contact",
        help="remove a contact")
    remove_parser.add_argument(
        "--force", action="store_true",
        help="Remove contact without confirmation")
    subparsers.add_parser(
        "addressbooks",
        aliases=Actions.get_aliases("addressbooks"),
        description="list addressbooks",
        help="list addressbooks")
    subparsers.add_parser(
        "filename",
        aliases=Actions.get_aliases("filename"),
        parents=[default_addressbook_parser, default_search_parser,
                 sort_parser],
        description="list filenames of all matching contacts",
        help="list filenames of all matching contacts")

    # Replace the print_help method of the first parser with the print_help
    # method of the main parser.  This makes it possible to have the first
    # parser handle the help option so that command line help can be printed
    # without parsing the config file first (which is a problem if there are
    # errors in the config file).  The config file will still be parsed before
    # the full command line is parsed so errors in the config file might be
    # reported before command line syntax errors.
    first_parser.print_help = parser.print_help  # type: ignore

    return first_parser, parser


def parse_args(argv: List[str]) -> Tuple[argparse.Namespace, Config]:
    """Parse the command line arguments and return the namespace that was
    creates by argparse.ArgumentParser.parse_args().

    :param argv: the command line arguments
    :returns: the namespace parsed from the command line
    """
    first_parser, parser = create_parsers()
    # Parese the command line with the first argument parser.  It will handle
    # the config option (its main job) and also the help, version and debug
    # options as these do not depend on anything else.
    args = first_parser.parse_args(argv)
    remainder = args.remainder

    # Set the loglevel to debug if given on the command line.  This is done
    # before parsing the config file to make it possible to debug the parsing
    # of the config file.
    if "debug" in args and args.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Create the config instance.
    try:
        config = Config(args.config)
    except ConfigError as err:
        parser.exit(3, "Error in config file: {}\n".format(err))
    logger.debug("Finished parsing config=%s", vars(config))

    # Check the log level again and merge the value from the command line with
    # the config file.
    if ("debug" in args and args.debug) or config.debug:
        logging.basicConfig(level=logging.DEBUG)
    logger.debug("first args=%s", args)
    logger.debug("remainder=%s", remainder)

    # Set the default command from the config file if none was given on the
    # command line.
    if not remainder or remainder[0] not in Actions.get_all():
        if config.default_action is None:
            parser.error("Missing subcommand on command line or default action"
                         " parameter in config.")
        remainder.insert(0, config.default_action)
        logger.debug("updated remainder=%s", remainder)

    # Save the last option that needs to be carried from the first parser run
    # to the second.
    skip = args.skip_unparsable

    # Parse the remainder of the command line.  All options from the previous
    # run have already been processed and are not needed any more.
    args = parser.parse_args(remainder)

    # Restore settings that are left from the first parser run.
    args.skip_unparsable = skip
    logger.debug("second args=%s", args)

    # An integrity check for some options.
    if "uid" in args and args.uid and (
            ("search_terms" in args and args.search_terms) or
            ("source_search_terms" in args and args.source_search_terms)):
        # If an uid was given we require that no search terms where given.
        parser.error("You can not give arbitrary search terms and --uid at the"
                     " same time.")

    # Normalize all deprecated subcommands and emit warnings.
    if args.action == "export":
        logger.warning("Deprecated subcommand: use 'show --format=yaml'.")
        args.action = "show"
        args.format = "yaml"
    elif args.action == "source":
        logger.warning("Deprecated subcommand: use 'edit --format=vcard'.")
        args.action = "edit"
        args.format = "vcard"

    return args, config


def merge_args_into_config(args: argparse.Namespace, config: Config) -> Config:
    """Merge the parsed arguments from argparse into the config object.

    :param args: the parsed command line arguments
    :param config: the parsed config file
    :returns: the merged config object
    """
    config.merge_args(args)
    # Now we can savely initialize the address books as all command line
    # options have been incorporated into the config object.
    config.init_address_books()
    # If the user could but did not specify address books on the command line
    # it means they want to use all address books in that place.
    if "addressbook" in args and not args.addressbook:
        args.addressbook = [abook.name for abook in config.abooks]
    if "target_addressbook" in args and not args.target_addressbook:
        args.target_addressbook = [abook.name for abook in config.abooks]
    return config


def init(argv: List[str]) -> Tuple[argparse.Namespace, Config]:
    """Initialize khard by parsing the command line and reading the config file

    :param argv: the command line arguments
    :returns: the parsed command line and the fully initialized config
    """
    args, conf = parse_args(argv)

    # if args.action isn't one of the defined actions, it must be an alias
    if args.action not in Actions.get_actions():
        # convert alias to corresponding action
        # example: "ls" --> "list"
        args.action = Actions.get_action(args.action)

    return args, merge_args_into_config(args, conf)
