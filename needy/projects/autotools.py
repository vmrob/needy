import distutils.spawn
import os
import subprocess
import logging

from .. import project
from ..cd import cd
from ..process import command_output

from .make import get_make_jobs_args


class AutotoolsProject(project.Project):

    @staticmethod
    def identifier():
        return 'autotools'

    @staticmethod
    def is_valid_project(definition, needy):
        failure_messages = []
        with cd(definition.directory):
            if os.path.isfile('configure'):
                try:
                    configure_version_info = command_output(['./configure', '--version'], logging.DEBUG)
                    if 'generated by GNU Autoconf' in configure_version_info:
                        return True, './configure script determined to be generated by GNU Autoconf'
                except subprocess.CalledProcessError:
                    pass
                except OSError:
                    pass
                failure_message.append('./configure script was not determined to be generated by GNU Autoconf')
            else:
                failure_messages.append('no ./configure script found')
            if os.path.isfile('autogen.sh') and os.path.isfile('configure.ac') and os.path.isfile('Makefile.am'):
                return True, 'autogen.sh, configure.ac, and Makefile.am all exist'
            else:
                failure_messages.append('autogen.sh, configure.ac, and Makefile.am were not all found')
        return False, failure_messages

    @staticmethod
    def missing_prerequisites(definition, needy):
        return ['make'] if distutils.spawn.find_executable('make') is None else []

    @staticmethod
    def configuration_keys():
        return project.Project.configuration_keys() | {'configure-args', 'make-targets'}

    def configure(self, output_directory):
        if not os.path.isfile(os.path.join(self.directory(), 'configure')):
            self.command('./autogen.sh')

        configure_args = self.evaluate(self.configuration('configure-args') or [])
        has_host = any([arg.startswith('--host=') or arg == '--host' for arg in configure_args])

        configure_args.append('--prefix=%s' % output_directory)

        if self.target().platform.identifier() in ['ios', 'tvos']:
            if not has_host:
                candidates = [
                    '%s-apple-darwin' % self.target().architecture, 'arm*-apple-darwin',
                    'arm-apple-darwin', 'arm*', 'arm'
                ]
                if self.target().architecture == 'arm64':
                    candidates.insert(0, 'aarch64')
                    candidates.insert(0, 'aarch64*')
                    candidates.insert(0, 'aarch64-apple-darwin')
                configure_host = self.__available_configure_host(candidates)

                if configure_host == 'arm*-apple-darwin':
                    configure_host = '%s-apple-darwin' % self.target().architecture
                elif configure_host == 'arm*':
                    configure_host = self.target().architecture
                elif configure_host == 'aarch64*':
                    configure_host = 'aarch64-apple-darwin'
                elif not configure_host:
                    configure_host = 'arm-apple-darwin'

                configure_args.append('--host=%s' % configure_host)
        elif self.target().platform.identifier() == 'android':
            toolchain = self.target().platform.toolchain_path(self.target().architecture)
            sysroot = self.target().platform.sysroot_path(self.target().architecture)

            if not has_host:
                if self.target().architecture.find('arm') >= 0:
                    candidates = [
                        'linux*android*', 'arm*', 'arm'
                    ]
                    if self.target().architecture == 'arm64':
                        candidates.insert(0, 'aarch64')
                        candidates.insert(0, 'aarch64*')
                        candidates.insert(0, 'aarch64-linux-android')
                    configure_host = self.__available_configure_host(candidates)

                    if configure_host == 'linux*android*':
                        configure_host = 'arm-linux-androideabi'
                    elif configure_host == 'arm*':
                        configure_host = self.target().architecture
                    elif configure_host == 'aarch64*':
                        configure_host = 'aarch64-linux-android'
                    elif not configure_host:
                        configure_host = 'arm-linux-androideabi'

                configure_args.append('--host=%s' % configure_host)

            configure_args.append('--with-sysroot=%s' % sysroot)

        self.command(['./configure'] + configure_args)

    def build(self, output_directory):
        make_args = get_make_jobs_args(self)
        self.command(['make'] + self.__make_targets() + make_args)
        self.command(['make', 'install'] + make_args)

    def __make_targets(self):
        return self.evaluate(self.configuration('make-targets') or [])

    def __available_configure_host(self, candidates):
        with open(os.path.join(self.directory(), 'configure'), 'r') as file:
            contents = file.read()
            for candidate in candidates:
                if contents.find(candidate) >= 0:
                    return candidate

        return None
