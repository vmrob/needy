#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess
import sys

TESTS_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

def test(directory, needy_args, run_dirty=False):
    print 'Running test in %s: %s' % (directory, ' '.join(needy_args))
    os.chdir(directory)
    if not run_dirty and os.path.exists('needs'):
        shutil.rmtree('needs')
    env = os.environ.copy()
    env['PYTHONPATH'] = '../'
    subprocess.check_call(['python', '-m', 'needy'] + needy_args, env=env)

def main(args):
    parser = argparse.ArgumentParser(description='Tests Needy.')
    parser.add_argument('--run-dirty', default=False, action='store_true', help='run without cleaning first (useful for saving time while debugging)')
    parameters, needy_args = parser.parse_known_args(args[1:])
    
    for entry in os.listdir(TESTS_DIRECTORY):
        test_directory = os.path.join(TESTS_DIRECTORY, entry)
        if os.path.isfile(os.path.join(test_directory, 'needs.json')):
            test(test_directory, needy_args, parameters.run_dirty)

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print '[ERROR]', e
        raise