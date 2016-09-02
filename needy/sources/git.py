import os
import logging
import distutils.spawn
import subprocess

from ..source import Source
from ..cd import cd
from ..process import command, command_output


class GitRepository(Source):
    def __init__(self, directory, repository, commit):
        Source.__init__(self, directory)
        self.repository = repository
        self.commit = commit

    @classmethod
    def identifier(cls):
        return 'git'

    def clean(self):
        GitRepository.__assert_git_availability()

        if not os.path.exists(os.path.join(self.source_directory(), '.git')):
            self.__fetch()

        with cd(self.source_directory()):
            command(['git', 'clean', '-xffd'], logging.DEBUG)
            try:
                command(['git', 'fetch'], logging.DEBUG)
            except subprocess.CalledProcessError:
                # we should be okay with this to enable offline builds
                logging.warn('git fetch failed for {}'.format(self.source_directory()))
                pass
            command(['git', 'reset', 'HEAD', '--hard'], logging.DEBUG)
            command(['git', 'checkout', '--force', self.commit], logging.DEBUG)
            command(['git', 'submodule', 'update', '--init', '--recursive'], logging.DEBUG)

    def synchronize(self):
        GitRepository.__assert_git_availability()

        if not os.path.exists(os.path.join(self.source_directory(), '.git')):
            self.__fetch(verbosity=logging.INFO)

        with cd(self.source_directory()):
            command(['git', 'fetch'])
            command(['git', 'checkout', self.commit])
            command(['git', 'submodule', 'update', '--init', '--recursive'])

    def __fetch(self, verbosity=logging.DEBUG):
        GitRepository.__assert_git_availability()

        if not os.path.exists(os.path.dirname(self.source_directory())):
            os.makedirs(os.path.dirname(self.source_directory()))

        with cd(os.path.dirname(self.source_directory())):
            command(['git', 'clone', self.repository, os.path.basename(self.source_directory())], verbosity)

        with cd(self.source_directory()):
            command(['git', 'submodule', 'update', '--init', '--recursive'], verbosity)

    @classmethod
    def __assert_git_availability(cls):
        if not distutils.spawn.find_executable('git'):
            raise RuntimeError('No git binary is present')

    def status(self):
        head = ''
        with cd(self.source_directory()):
            head = command_output(['git', 'rev-parse', 'HEAD'], verbosity=logging.DEBUG).strip()
        return 'git: {}'.format(head)
