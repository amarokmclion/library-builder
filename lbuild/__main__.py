#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2017, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import sys
import argparse
import textwrap
import traceback

import lbuild.parser
import lbuild.logger
import lbuild.vcs.common


def get_modules(parser, repo_options, config_options, selected_modules=None):
    if selected_modules is None:
        selected_modules = [":**"]
    modules = parser.prepare_repositories(repo_options)
    build_modules = parser.resolve_dependencies(modules, selected_modules)
    module_options = parser.merge_module_options(build_modules, config_options)

    return build_modules, module_options

def is_repository_option(option_name):
    parts = option_name.split(":")
    if len(parts) < 2:
        raise lbuild.exception.BlobOptionFormatException(option_name)
    elif len(parts) == 2:
        return True
    else:
        return False

def prepare_argument_parser():
    """
    Set up the argument parser for the different commands.

    Return:
    Configured ArgumentParser object.
    """
    argument_parser = argparse.ArgumentParser(
        description='Build source code libraries from modules.')
    argument_parser.add_argument('-r', '--repository',
        metavar="REPO",
        dest='repositories',
        action='append',
        default=[],
        help="Repository file(s) which should be available for the current library. "
             "The loading of repository files from a VCS is only supported through "
             "the library configuration file.")
    argument_parser.add_argument('-c', '--config',
        dest='config',
        default='project.xml',
        help="Project/library configuration file. "
             "Specifies the used repositories, modules and options "
             "(default: '%(default)s').")
    argument_parser.add_argument('-p', '--path',
        dest='path',
        default='.',
        help="Path in which the library will be generated (default: '%(default)s').")
    argument_parser.add_argument('-D', '--option',
        metavar='OPTION',
        dest='options',
        action='append',
        type=str,
        default=[],
        help="Additional options. Options given here will be merged with options "
             "from the configuration file and will overwrite the configuration "
             "file definitions. "
             "Use a single colon to specify repository options and multiple "
             "colons to specify (sub)module options.")
    argument_parser.add_argument('-v', '--verbose',
        action='count',
        default=0,
        dest='verbose')

    subparsers = argument_parser.add_subparsers(title="Actions",
        dest="action")

    parser_init = subparsers.add_parser("init",
        help="Load remote repositories into the cache folder.")
    parser_update = subparsers.add_parser("update",
        help="Update the content of remote repositories in the cache folder.")
    parser_discover_repo = subparsers.add_parser("discover-repository",
        aliases=['repo'],
        help="Display the repository options of all selected repositories.")
    parser_discover_modules = subparsers.add_parser("discover-modules",
        aliases=['modules'],
        help="Inspect all available modules with the given repository options. "
             "All repository options must be defined.")
    parser_dependecies = subparsers.add_parser("dependencies",
        help="Generate a grahpviz representation of the module dependencies.")
    parser_discover_module_options = subparsers.add_parser("discover-module-options",
        aliases=['options'],
        help="Inspect the module options of one or more modules (if specified "
             "through the module option(s)) or all available modules (if no "
             "module is specified).")
    parser_discover_module_options.add_argument("-m", "--module",
        dest="modules",
        type=str,
        action="append",
        default=[],
        help="Select a specific module.")

    parser_discover_option = subparsers.add_parser("discover-option",
        aliases=['option'],
        help="Print the description and values of one option.")
    parser_discover_option.add_argument("-o", "--option-name",
        dest="option_name",
        required=True,
        help="Select a specific module")

    parser_discover_option_values = subparsers.add_parser("discover-option-values",
        aliases=['option-values'],
        help="Print the values of one option.")
    parser_discover_option_values.add_argument("-o", "--option-name",
        dest="option_name",
        required=True,
        help="Select a specific module")

    parser_build = subparsers.add_parser("build",
        help="Generate the library source code blob with the given options.")
    parser_build.add_argument("-m", "--module",
        dest="modules",
        type=str,
        action="append",
        default=[],
        help="Select a specific module.")
    parser_build.add_argument("--no-log",
        dest="buildlog",
        action="store_false",
        default=True,
        help="Do not create a build log. This log contains all files being "
             "generated, their source files and the module which generated "
             "the file.")

    return argument_parser

def run(args):
    config = lbuild.config.Configuration.parse_configuration(args.config)

    if args.action == 'init':
        lbuild.vcs.common.initialize(config)
    elif args.action == 'update':
        lbuild.vcs.common.update(config)
    else:
        parser = lbuild.parser.Parser()
        parser.load_repositories(config, args.repositories)

        commandline_options = config.format_commandline_options(args.options)
        repo_options = parser.merge_repository_options(config.options, commandline_options)

        if args.action in ['discover-repository', 'repo']:
            for option in sorted(list(repo_options.values())):
                print(option.format())
        elif args.action in ['discover-modules', 'modules']:
            modules = parser.prepare_repositories(repo_options)
            for module in sorted(list(modules.values())):
                print(module)
        elif args.action in ['dependencies']:
            modules = parser.prepare_repositories(repo_options)
            dot_file = lbuild.builder.dependency.graphviz(parser.repositories)

            print(dot_file)
        elif args.action in ['discover-module-options', 'options']:
            if len(args.modules) == 0 and len(config.selected_modules) == 0:
                config.selected_modules.extend([":**"])
            else:
                config.selected_modules.extend(args.modules)
            _, options = get_modules(parser, repo_options, config.options, config.selected_modules)

            for option in sorted(list(options.values())):
                print(option.format())

                if option.short_description:
                    print()
                    print(textwrap.indent(option.short_description, "  "))
                    print()
        elif args.action in ['discover-option', 'option']:
            option_name = args.option_name
            if is_repository_option(option_name):
                option = parser.find_module(repo_options, option_name)
            else:
                _, options = get_modules(parser, repo_options, config.options)
                option = parser.find_module(options, option_name)

            print(option.factsheet())
            print()
        elif args.action in ['discover-option-values', 'option-values']:
            option_name = args.option_name
            if is_repository_option(option_name):
                option = parser.find_module(repo_options, option_name)
            else:
                _, options = get_modules(parser, repo_options, config.options)
                option = parser.find_module(options, option_name)

            for value in lbuild.utils.listify(option.values):
                print(value)
        elif args.action == 'build':
            log = lbuild.buildlog.BuildLog()

            config.selected_modules.extend(args.modules)
            build_modules, module_options = get_modules(parser, repo_options, config.options, config.selected_modules)
            parser.build_modules(args.path, build_modules, repo_options, module_options, log)

            if args.buildlog:
                configfilename = args.config
                logfilename = configfilename + ".log"
                with open(logfilename, "wb") as logfile:
                    logfile.write(log.to_xml(to_string=True))
        else:
            raise lbuild.exception.BlobArgumentException("Unknown command-line "
                                                         "option '{}'".format(args.action))

def main():
    """
    Main entry point of lbuild.
    """
    argument_parser = prepare_argument_parser()
    args = argument_parser.parse_args(sys.argv[1:])

    lbuild.logger.configure_logger(args.verbose)
    try:
        run(args)
    except lbuild.exception.BlobArgumentException as error:
        argument_parser.print_help()
        print(error)
        sys.exit(2)
    except lbuild.exception.BlobTemplateException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        traceback.print_exc()
        sys.exit(3)
    except lbuild.exception.BlobException as error:
        sys.stderr.write('\nERROR: %s\n' % error)
        if args.verbose >= 2:
            traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()