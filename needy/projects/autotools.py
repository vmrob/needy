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
        with cd(definition.directory):
            if os.path.isfile('configure'):
                try:
                    configure_version_info = command_output(['./configure', '--version'], logging.DEBUG)
                    if 'generated by GNU Autoconf' in configure_version_info:
                        return True
                except subprocess.CalledProcessError:
                    pass
                except OSError:
                    pass
            if os.path.isfile('autogen.sh') and os.path.isfile('configure.ac') and os.path.isfile('Makefile.am'):
                return True
        return False

    @staticmethod
    def configuration_keys():
        return ['configure-args']

    def configure(self, output_directory):
        if not os.path.isfile(os.path.join(self.directory(), 'configure')):
            self.command('./autogen.sh')

        configure_args = self.evaluate(self.configuration('configure-args') or [])
        has_host = any([arg.startswith('--host=') or arg.startswith('--host=') for arg in configure_args])

        configure_args.append('--prefix=%s' % output_directory)

        linkage = self.configuration('linkage')

        if self.target().platform.identifier() in ['ios', 'tvos']:
            if not linkage:
                linkage = 'static'

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

        if linkage:
            if linkage == 'static':
                configure_args.append('--disable-shared')
                configure_args.append('--enable-static')
            elif linkage == 'dynamic':
                configure_args.append('--disable-static')
                configure_args.append('--enable-shared')
            else:
                raise ValueError('unknown linkage')

        self.command(['./configure'] + configure_args)

    def build(self, output_directory):
        make_args = get_make_jobs_args(self)

        binary_paths = self.target().platform.binary_paths(self.target().architecture)
        if len(binary_paths) > 0:
            make_args.append('PATH=%s:%s' % (':'.join(binary_paths), os.environ['PATH']))

        self.command(['make'] + self.project_targets() + make_args)
        self.command(['make', 'install'] + make_args)

    def __available_configure_host(self, candidates):
        with open(os.path.join(self.directory(), 'configure'), 'r') as file:
            contents = file.read()
            for candidate in candidates:
                if contents.find(candidate) >= 0:
                    return candidate

        return None
