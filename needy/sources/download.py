from __future__ import print_function

import io
import os
import binascii
import hashlib
import socket
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

from ..source import Source


class Download(Source):
    def __init__(self, destination, url, checksum, cache_directory):
        Source.__init__(self, destination)
        self.__url = url
        self.__checksum = checksum
        self.__cache_directory = cache_directory
        self.__local_download_path = os.path.join(cache_directory, checksum)

    @classmethod
    def identifier(cls):
        return 'download'

    def clean(self):
        if not self.__checksum:
            raise ValueError('checksums are required for downloads')

        self.__fetch()

        print('Unpacking to %s' % self.source_directory())
        self.__clean_destination_dir()
        self.__unpack()
        self.__trim_lone_dirs()

    def __fetch(self):
        if not os.path.exists(self.__cache_directory):
            os.makedirs(self.__cache_directory)

        if not os.path.isfile(self.__local_download_path):
            self.get(self.__url, self.__checksum, self.__local_download_path)

    @classmethod
    def get(cls, url, checksum, destination):
        print('Downloading from %s' % url)
        download = None
        attempts = 0
        download_successful = False
        while not download_successful and attempts < 5:
            try:
                download = urllib2.urlopen(url, timeout=5)
            except urllib2.URLError as e:
                print(e)
            except socket.timeout as e:
                print(e)
            attempts = attempts + 1
            download_successful = download and download.code == 200 and 'content-length' in download.info()
            if not download_successful:
                print('Download failed. Retrying...')
            time.sleep(attempts)
        if not download_successful:
            raise IOError('unable to download library')
        size = int(download.info()['content-length'])
        progress = 0
        if sys.stdout.isatty():
            print('{:.1%}'.format(float(progress) / size), end='')
            sys.stdout.flush()

        local_file = tempfile.NamedTemporaryFile('wb', delete=False)
        try:
            chunk_size = 1024
            while True:
                chunk = download.read(chunk_size)
                progress = progress + chunk_size
                if sys.stdout.isatty():
                    print('\r{:.1%}'.format(float(progress) / size), end='')
                    sys.stdout.flush()
                if not chunk:
                    break
                local_file.write(chunk)

            local_file.close()
            if sys.stdout.isatty():
                print('\r       \r', end='')
                sys.stdout.flush()

            print('Verifying checksum...')
            if not cls.verify_checksum(local_file.name, checksum):
                raise ValueError('incorrect checksum')
            print('Checksum verified.')

            shutil.move(local_file.name, destination)
        except:
            os.unlink(local_file.name)
            raise

        del download

    @classmethod
    def verify_checksum(cls, path, expected):
        expected = binascii.unhexlify(expected)

        with open(path, 'rb') as file:
            file_contents = file.read()
            hash = None
            if len(expected) == hashlib.md5().digest_size:
                hash = hashlib.md5()
            elif len(expected) == hashlib.sha1().digest_size:
                hash = hashlib.sha1()
            else:
                raise ValueError('unknown checksum type')
            hash.update(file_contents)
            return expected == hash.digest()

    def __clean_destination_dir(self):
        if os.path.exists(self.source_directory()):
            shutil.rmtree(self.source_directory())
        os.makedirs(self.source_directory())

    def __unpack(self):
        if tarfile.is_tarfile(self.__local_download_path):
            self.__tarfile_unpack()
            return
        if zipfile.is_zipfile(self.__local_download_path):
            self.__zipfile_unpack()
            return

    def __tarfile_unpack(self):
        with open(self.__local_download_path, 'rb') as file:
            tar = tarfile.open(fileobj=file, mode='r|*')
            tar.extractall(self.source_directory() if isinstance(self.source_directory(), str) else self.source_directory().encode(sys.getfilesystemencoding()))
            del tar

    def __zipfile_unpack(self):
        with zipfile.ZipFile(self.__local_download_path, 'r') as file:
            file.extractall(self.source_directory())

    def __trim_lone_dirs(self):
        temporary_directory = os.path.join(self.__cache_directory, 'temp_')

        while True:
            destination_contents = os.listdir(self.source_directory())
            if len(destination_contents) != 1:
                break
            lone_directory = os.path.join(self.source_directory(), destination_contents[0])
            if not os.path.isdir(lone_directory):
                break
            shutil.move(lone_directory, temporary_directory)
            shutil.rmtree(self.source_directory())
            shutil.move(temporary_directory, self.source_directory())
