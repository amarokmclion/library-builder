#!/usr/bin/env python3
#
# Copyright (c) 2016, Fabian Greif
# All Rights Reserved.
#
# The file is part of the lbuild project and is released under the
# 2-clause BSD license. See the file `LICENSE.txt` for the full license
# governing this code.

import enum
import inspect
import textwrap

import lbuild.filter
from .exception import BlobException


class Option:
    """
    Base class for repository and module options.

    Can be used for string based options.
    """
    def __init__(self, name, description, default=None):
        if ":" in name:
            raise BlobException("Character ':' is not allowed in options "
                                "name '{}'".format(name))

        self.name = name
        self._description = description

        # Parent repository for this option
        self.repository = None
        # Parent module. Is set to none if the option is a repository
        # option and not a module option.
        self.module = None

        self._value = default

    @property
    def description(self):
        try:
            return self._description.read()
        except AttributeError:
            return self._description

    @property
    def split_description(self, wrap=True):
        """
        Returns the wrapped first paragraph of the description as a title and
        the remaing part of the description that is not covered by the
        title as the descriptio body.

        A paragraph is defined by non-whitespace text followed by an empty
        line.
        """
        description = self.description
        if description is None:
            title = None
            body = None
        else:
            title_found = False
            title_list = []
            body_list = []
            for line in description.splitlines():
                line = line.rstrip()
                if not title_found:
                    if line == "":
                        if len(title_list) > 0:
                            title_found = True
                    else:
                        title_list.append(line)
                else:
                    body_list.append(line)

            body = "\n".join(body_list).strip()

            if wrap:
                title = "\n".join(textwrap.wrap("\n".join(title_list), 80))
            else:
                title = " ".join(title_list)

        return title, body

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @property
    def values(self):
        return "String"

    def values_hint(self):
        return self.values

    def format(self):
        values = self.values_hint()
        if self.value is None:
            return "{} = [{}]".format(self.fullname, values)
        else:
            return "{} = {}  [{}]".format(self.fullname, self._value, values)

    @property
    def fullname(self):
        name = []
        if self.module is not None:
            name.append(self.module.fullname)
        elif self.repository is not None:
            name.append(self.repository.name)

        name.append(self.name)
        return ':'.join(name)

    def __lt__(self, other):
        return self.fullname.__lt__(other.fullname)

    def __str__(self):
        return self.fullname

    def factsheet(self):
        output = []
        output.append("# {}\n".format(self.fullname))
        if self.value is not None:
            output.append("Current value: {}  ".format(self.value))
        output.append("Possible values: {}".format(self.values_hint()))

        title, body = self.split_description
        if title:
            output.append("\n## {}\n".format(title))
        if body:
            output.append(body)
        return "\n".join(output)


class BooleanOption(Option):

    def __init__(self, name, description, default=False):
        Option.__init__(self, name, description)
        if default is not None:
            self.value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.as_boolean(value)

    @property
    def values(self):
        return "True, False"

    @staticmethod
    def as_boolean(value):
        if value is None:
            return value
        elif isinstance(value, bool):
            return value
        elif str(value).lower() in ['true', 'yes', '1']:
            return True
        elif str(value).lower() in ['false', 'no', '0']:
            return False

        raise BlobException("Value '%s' (%s) must be boolean" %
                            (value, type(value).__name__))


class NumericOption(Option):

    def __init__(self, name, description, minimum=None, maximum=None, default=None):
        Option.__init__(self, name, description)

        self.minimum = minimum
        self.maximum = maximum

        if default is not None:
            self.value = default

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        numeric_value = self.as_numeric_value(value)
        if self.minimum is not None and numeric_value < self.minimum:
            BlobException("Value '{}' must be smaller than '{}'".format(self.name, self.minimum))
        if self.maximum is not None and numeric_value < self.maximum:
            BlobException("Value '{}' must be greater than '{}'".format(self.name, self.maximum))
        self._value = numeric_value

    @property
    def values(self):
        return "{} ... {}".format("-Inf" if self.minimum is None else str(self.minimum),
                                  "+Inf" if self.maximum is None else str(self.maximum))

    @staticmethod
    def as_numeric_value(value):
        if value is None:
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return int(value, 0)
            except:
                pass

        raise BlobException("Value '%s' (%s) must be numeric" %
                            (value, type(value).__name__))


class EnumerationOption(Option):

    LINEWITH = 120

    def __init__(self, name, description, enumeration, default=None):
        Option.__init__(self, name, description)
        if inspect.isclass(enumeration) and issubclass(enumeration, enum.Enum):
            self._enumeration = enumeration
        elif (isinstance(enumeration, list) or isinstance(enumeration, tuple)) and \
                len(enumeration) == len(set(enumeration)):
            # If the argument is a list and the items in the list are unqiue,
            # convert it so that the value of the enum equals its name.
            self._enumeration = enum.Enum(name, dict(zip(enumeration, enumeration)))
        else:
            self._enumeration = enum.Enum(name, enumeration)
        if default is not None:
            self.value = default

    @property
    def value(self):
        if self._value is None:
            return None
        else:
            return self._value.value

    @value.setter
    def value(self, value):
        self._value = self.as_enumeration(value)

    @property
    def values(self):
        values = []
        for value in self._enumeration:
            values.append(value.name)
        values.sort()
        return values

    def values_hint(self):
        return ", ".join(self.values)

    def format(self):
        name = self.fullname + " = "
        if self._value is None:
            values = self.values_hint()
            # This +1 is for the first square brackets
            output = lbuild.filter.indent(lbuild.filter.wordwrap(values,
                                                                 self.LINEWITH - len(name) - 1),
                                          len(name) + 1)
            return "{}[{}]".format(name, output)
        else:
            values = self.values_hint()
            # The +4 is for the spacing and the two square brackets
            overhead = len(name) + 4
            if len(values) + overhead > self.LINEWITH:
                mark = " ..."
                max_length = self.LINEWITH - overhead - len(mark)
                values = values[0:max_length] + mark
            return "{}{}  [{}]".format(name, self._value.value, values)

    def as_enumeration(self, value):
        try:
            # Try to access 'value' as if it where an enum
            return self._enumeration[value.name]
        except AttributeError:
            return self._enumeration[value]

