import fnmatch
import json
import os
import multiprocessing
import sys

from collections import OrderedDict

try:
    from colorama import Fore
    from colorama import Style
except ImportError:
    class EmptyStringAttributes:
        def __getattr__(self, name):
            return ''
    Fore = EmptyStringAttributes()
    Style = EmptyStringAttributes()

from .process import command_output
from .library import Library
from .platform import available_platforms, host_platform
from .generator import available_generators
from .target import Target
from .cd import current_directory


class Needy:
    def __init__(self, path, parameters):
        self.__path = path if os.path.isabs(path) else os.path.normpath(os.path.join(current_directory(), path))
        self.__parameters = parameters

        with open(os.path.join(self.__path, 'needs.json'), 'r') as needs_file:
            self.needs = json.load(needs_file, object_pairs_hook=OrderedDict)

        self.__needs_directory = os.path.join(self.__path, 'needs')

        directory = self.__path
        while directory:
            if os.path.exists(os.path.join(directory, 'needs.json')):
                self.__needs_directory = os.path.join(directory, 'needs')
            directory = os.path.dirname(directory)
            if directory == os.sep:
                break

    def path(self):
        return self.__path

    def needs_directory(self):
        return self.__needs_directory

    def parameters(self):
        return self.__parameters

    def build_concurrency(self):
        if self.parameters().concurrency > 0:
            return self.parameters().concurrency
        return multiprocessing.cpu_count()

    def platform(self, identifier):
        platform = host_platform() if identifier == 'host' else available_platforms().get(identifier, None)
        if platform is not None:
            return platform(self.__parameters)

        raise ValueError('unknown platform (%s)' % identifier)

    def target(self, identifier):
        parts = identifier.split(':')
        platform = self.platform(parts[0])
        return Target(platform, parts[1] if len(parts) > 1 else platform.default_architecture())

    def recursive(self, path):
        return Needy(path, self.parameters()) if os.path.isfile(os.path.join(path, 'needs.json')) else None

    def libraries_to_build(self, filters=None):
        if 'libraries' not in self.needs:
            return []

        names = []

        for name, library_configuration in self.needs['libraries'].iteritems():
            if filters:
                match = False
                for filter in filters:
                    if fnmatch.fnmatchcase(name, filter):
                        match = True
                        break
                if not match:
                    continue
            names.append(name)

        graph = {}
        libraries = {}

        while len(names):
            name = names.pop()
            directory = os.path.join(self.__needs_directory, name)
            library = Library(self.needs['libraries'][name], directory, self)
            libraries[name] = library
            if 'dependencies' not in library.configuration():
                graph[name] = set()
                continue
            str_or_list = library.configuration()['dependencies']
            dependencies = str_or_list if isinstance(str_or_list, list) else [str_or_list]
            graph[name] = set(dependencies)
            for dependency in dependencies:
                if dependency not in graph:
                    names.append(dependency)

        s = []

        for name, dependencies in graph.iteritems():
            if len(dependencies) == 0:
                s.append(name)

        ret = []

        while len(s):
            name = s.pop()
            ret.append((name, libraries[name]))
            for n, deps in graph.iteritems():
                if name not in deps:
                    continue
                deps.remove(name)
                if len(deps) == 0:
                    s.append(n)

        for name, deps in graph.iteritems():
            if len(deps):
                raise ValueError('circular dependency detected')

        return ret

    def include_paths(self, target):
        ret = []
        for n, l in self.libraries_to_build():
            if not l.should_build(target):
                continue
            if os.path.isdir(l.include_path(target)):
                ret.append(l.include_path(target))
            needy = self.recursive(l.source_directory())
            if needy:
                ret.extend(needy.include_paths(target))
        return ret

    def library_paths(self, target_or_universal_binary):
        ret = []
        for n, l in self.libraries_to_build():
            if isinstance(target_or_universal_binary, Target):
                if not l.should_build(target_or_universal_binary):
                    continue
                if os.path.isdir(l.library_path(target_or_universal_binary)):
                    ret.append(l.library_path(target_or_universal_binary))
            else:
                ret.append(l.library_path(target_or_universal_binary))
            needy = self.recursive(l.source_directory())
            if needy:
                ret.extend(needy.library_paths(target_or_universal_binary))
        return ret

    def build_directory(self, library, target_or_universal_binary):
        directory = os.path.join(self.__needs_directory, library)
        l = Library(self.needs['libraries'][library], directory, self)
        return l.build_directory(target_or_universal_binary)

    def satisfy_target(self, target, filters=None):
        if 'libraries' not in self.needs:
            return

        print('Satisfying needs in %s' % self.path())

        try:
            for name, library in self.libraries_to_build(filters):
                if library.has_up_to_date_build(target):
                    self.__print_status(Fore.GREEN, 'UP-TO-DATE', name)
                else:
                    self.__print_status(Fore.CYAN, 'OUT-OF-DATE', name)
                    library.build(target)
                    self.__print_status(Fore.GREEN, 'SUCCESS', name)
        except Exception as e:
            self.__print_status(Fore.RED, 'ERROR')
            print(e)
            raise

    def satisfy_universal_binary(self, universal_binary, filters=None):
        try:
            print('Satisfying universal binary %s in %s' % (universal_binary, self.path()))

            if 'universal-binaries' not in self.needs:
                raise ValueError('no universal binaries defined')

            if universal_binary not in self.needs['universal-binaries']:
                raise ValueError('unknown universal binary ({})'.format(universal_binary))

            if 'libraries' not in self.needs:
                return

            configuration = self.needs['universal-binaries'][universal_binary]

            for name, library in self.libraries_to_build(filters):
                if library.has_up_to_date_universal_binary(universal_binary, configuration):
                    self.__print_status(Fore.GREEN, 'UP-TO-DATE', name)
                else:
                    self.__print_status(Fore.CYAN, 'OUT-OF-DATE', name)
                    library.build_universal_binary(universal_binary, configuration)
                    self.__print_status(Fore.GREEN, 'SUCCESS', name)
        except Exception as e:
            self.__print_status(Fore.RED, 'ERROR')
            print(e)
            raise

    def __print_status(self, color, status, name=None):
        print(color + Style.BRIGHT + '[' + status + ']' + Style.RESET_ALL + Fore.RESET + (' %s' % name if name else ''))

    def create_universal_binary(self, inputs, output):
        name, extension = os.path.splitext(output)
        if extension not in ['.a', '.so', '.dylib']:
            return False

        command_output(['lipo', '-create'] + inputs + ['-output', output])
        return True

    def generate(self, files):
        if not os.path.exists(self.needs_directory()):
            os.makedirs(self.needs_directory())
        for generator in available_generators():
            if generator.identifier() in files:
                generator().generate(self)
