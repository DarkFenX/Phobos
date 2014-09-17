#===============================================================================
# Copyright (C) 2014 Anton Vorobyov
#
# This file is part of Phobos.
#
# Phobos is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Phobos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Phobos. If not, see <http://www.gnu.org/licenses/>.
#===============================================================================


import re


class FlowManager(object):
    """
    Class for handling high-level flow of script.
    """

    def __init__(self, miners, writers):
        self._miners = miners
        self._writers = writers
        self.__name_source_map = None

    def run(self, filter_string):
        processed_set = set()
        filter_set = set()
        filter_set.update(self._parse_filter(filter_string))
        # Cycle through miners in the order they were provided
        for miner in sorted(self._name_source_map, key=self._miners.index):
            miner_names_map = self._name_source_map[miner]
            # Compose set of container names to process and filter it if necessary
            miner_containers = set(miner_names_map)
            if filter_set:
                miner_containers.intersection_update(filter_set)
            # If set is empty after filtering, skip miner altogether
            if not miner_containers:
                continue
            print(u'Miner {}:'.format(type(miner).__name__))
            for modified_name in sorted(miner_containers):
                print(u'  processing {}'.format(modified_name))
                processed_set.add(modified_name)
                source_name = miner_names_map[modified_name]
                # Consume errors thrown by miners, just print a message about it
                try:
                    container_data = miner.get_data(source_name)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(u'    failed to fetch data - {}: {}'.format(type(e).__name__, e))
                else:
                    for writer in self._writers:
                        try:
                            writer.write(modified_name, container_data)
                        except KeyboardInterrupt:
                            raise
                        except Exception as e:
                            print(u'    failed to write data with {} - {}: {}'.format(type(writer).__name__, type(e).__name__, e))
        # Print info messages about requested, but unavailable containers
        if filter_set:
            missing_set = filter_set.difference(processed_set)
            if missing_set:
                print('Containers which were requested, but are not available:')
                for modified_name in sorted(missing_set):
                    print(u'  {}'.format(modified_name))

    @property
    def _name_source_map(self):
        """
        Resolve name collisions on cross-miner level by appending
        miner name to container name when necessary, and compose map
        between modified names and source miner/container name.
        """
        if self.__name_source_map is None:
            # Intermediate map
            # Format: {container name: [miners]}
            name_miner_map = {}
            for miner in self._miners:
                for source_name in miner.contname_iter():
                    miners = name_miner_map.setdefault(source_name, [])
                    miners.append(miner)
            # Format: {miner: {modified name: source name}}
            self.__name_source_map = {}
            for source_name, miners in name_miner_map.items():
                # If there're collisions, append miner name to container name
                if len(miners) > 1:
                    for miner in miners:
                        modified_name = u'{}_{}'.format(source_name, type(miner).__name__)
                        miner_containers = self.__name_source_map.setdefault(miner, {})
                        miner_containers[modified_name] = source_name
                # Do not modify name if there're no collisions
                else:
                    miner_containers = self.__name_source_map.setdefault(miners[0], {})
                    miner_containers[source_name] = source_name
        return self.__name_source_map

    def _parse_filter(self, name_filter):
        """
        Take filter string and return set of container names.
        """
        name_set = NameSet()
        # Flag which indicates if we're within parenthesis
        # (are parsing argument substring)
        inarg = False
        pos_current = 0
        # Cycle through all parenthesis and commas, split string using
        # out-of-parenthesis commas
        for match in re.finditer('[(),]', name_filter):
            pos_start = match.start()
            pos_end = match.end()
            symbol = match.group()
            if symbol == ',' and inarg is False:
                name_set.add(name_filter[pos_current:pos_start])
                pos_current = pos_end
            elif symbol == ',' and inarg is True:
                continue
            elif symbol == '(' and inarg is False:
                inarg = True
            elif symbol == ')' and inarg is True:
                inarg = False
            else:
                msg = 'unexpected character "{}" at position {}'.format(symbol, pos_start)
                raise FilterParseError(msg)
        if inarg is True:
            msg = 'parenthesis is not closed'
            raise FilterParseError(msg)
        # Add last segment of string after last seen comma
        name_set.add(name_filter[pos_current:])
        return name_set


class NameSet(set):
    """
    Set derivative, which automatically strips added
    elements and actually adds them to internal storage
    only if they still contain something meaningful.
    """

    def add(self, name):
        name = name.strip()
        if name:
            set.add(self, name)


class FilterParseError(BaseException):
    """
    When received filter string cannot be parsed,
    this exception is raised.
    """
    pass
