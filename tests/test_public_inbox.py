#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Jose Javier Merchante <jjmerchante@bitergia.com>
#

import collections
import datetime
import nntplib
import os
import shutil
import subprocess
import tempfile
import unittest.mock

from dateutil.tz import tzutc

from perceval.backend import BackendCommandArgumentParser
from perceval.backends.core.git import GitRepository
from perceval.backends.public_inbox.public_inbox import (PublicInbox,
                                                         PublicInboxCommand,
                                                         PublicInboxRepository)
from perceval.errors import RepositoryError


def read_file(filename, mode='r'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), mode) as f:
        content = f.read()
    return content


MockArticleInfo = collections.namedtuple('ArticleInfo',
                                         ['number', 'message_id', 'lines'])


class MockNNTPLib:
    """Class for mocking nntplib"""

    def __init__(self):
        self.__articles = {
            1: ('<mailman.350.1458060579.14303.dev-project-link@example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_1.txt')),
            2: ('<mailman.361.1458076505.14303.dev-project-link@example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_2.txt')),
            3: ('error', 'error'),
            4: ('<mailman.5377.1312994002.4544.community-arab-world@lists.example.com>',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/nntp/nntp_parsing_error.txt'))
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def group(self, name):
        return None, None, 1, 4, None

    def over(self, message_spec):
        first = min(message_spec[0], len(self.__articles))
        last = min(message_spec[1], len(self.__articles))
        response = [(x, {'message_id': self.__articles[x][0]})
                    for x in range(first, last + 1)]
        return None, response

    def article(self, article_id):
        a = self.__articles[article_id]
        message_id = a[0]

        if message_id == 'error':
            raise nntplib.NNTPTemporaryError('not found')

        with open(a[1], 'rb') as f:
            lines = [line.rstrip() for line in f]
        return None, MockArticleInfo(article_id, message_id, lines)

    def quit(self):
        pass


class TestPublicInboxBackend(unittest.TestCase):
    """PublicInbox backend tests"""

    tmp_path = None

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        tmp_repo_path = os.path.join(cls.tmp_path, 'repos')
        os.mkdir(tmp_repo_path)

        data_path = os.path.dirname(os.path.abspath(__file__))
        tar_path = os.path.join(data_path, 'data/public_inbox/example-repo.git.tar.gz')
        subprocess.check_call(['tar', '-xzf', tar_path, '-C', tmp_repo_path])

        cls.git_path = os.path.join(tmp_repo_path, 'example-repo.git')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_initialization(self):
        """Test whether attributes are initialized"""

        public_inbox = PublicInbox('http://example.com', self.git_path, tag='test')

        self.assertEqual(public_inbox.gitpath, self.git_path)
        self.assertEqual(public_inbox.uri, 'http://example.com')
        self.assertEqual(public_inbox.tag, 'test')

        # When tag is empty or None it will be set to
        # the value in the origin
        public_inbox = PublicInbox('http://example.com', self.git_path)
        self.assertEqual(public_inbox.uri, 'http://example.com')
        self.assertEqual(public_inbox.tag, 'http://example.com')

        public_inbox = PublicInbox('http://example.com', self.git_path, tag='')
        self.assertEqual(public_inbox.uri, 'http://example.com')
        self.assertEqual(public_inbox.tag, 'http://example.com')

    def test_has_archiving(self):
        """Test if it returns False when has_archiving is called"""

        self.assertEqual(PublicInbox.has_archiving(), False)

    def test_has_resuming(self):
        """Test if it returns True when has_resuming is called"""

        self.assertEqual(PublicInbox.has_resuming(), True)

    def test_fetch(self):
        """Test whether it fetches a set of messages"""

        backend = PublicInbox('http://example.com', self.git_path)
        messages = [m for m in backend.fetch()]

        expected = [
            ['<20100315132149.GA21127@domain3.com>', 'bb97b4295fa407bbac478fc137e72c2bd6c71058', 1268659309.0],
            ['<4B9E35A1.9080609@domain3>', 'a1733376f8a29d3ab148bc6b8da4307f8b17fb32', 1268659617.0],
            ['<randommessageid@domain4.com>', '84b2458ae5480defe2d5c83bc5921988b7106df2', 1268659835.0]
        ]

        self.assertEqual(len(messages), len(expected))

        for i, message in enumerate(messages):
            self.assertEqual(message['data']['Message-ID'], expected[i][0])
            self.assertEqual(message['origin'], 'http://example.com')
            self.assertEqual(message['uuid'], expected[i][1])
            self.assertEqual(message['updated_on'], expected[i][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com')

    def test_search_fields(self):
        """Test whether the search_fields is properly set"""

        backend = PublicInbox('http://example.com', self.git_path)
        messages = [m for m in backend.fetch()]

        for message in messages:
            self.assertEqual(backend.metadata_id(message['data']), message['search_fields']['item_id'])

    def test_fetch_from_date(self):
        """Test whether it fetches a list of messages a given date"""

        from_date = datetime.datetime(2010, 3, 15, 13, 25)

        backend = PublicInbox('http://example.com', self.git_path)
        messages = [m for m in backend.fetch(from_date=from_date)]

        expected = [
            ['<4B9E35A1.9080609@domain3>', 'a1733376f8a29d3ab148bc6b8da4307f8b17fb32', 1268659617.0],
            ['<randommessageid@domain4.com>', '84b2458ae5480defe2d5c83bc5921988b7106df2', 1268659835.0]
        ]

        self.assertEqual(len(expected), len(messages))

        for i, message in enumerate(messages):
            self.assertEqual(message['data']['Message-ID'], expected[i][0])
            self.assertEqual(message['origin'], 'http://example.com')
            self.assertEqual(message['uuid'], expected[i][1])
            self.assertEqual(message['updated_on'], expected[i][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com')

    def test_fetch_to_date(self):
        """Test whether a list of messages is returned to a given date"""

        to_date = datetime.datetime(2010, 3, 15, 13, 25)

        backend = PublicInbox('http://example.com', self.git_path)
        messages = [m for m in backend.fetch(to_date=to_date)]

        expected = [
            ['<20100315132149.GA21127@domain3.com>', 'bb97b4295fa407bbac478fc137e72c2bd6c71058', 1268659309.0]
        ]

        self.assertEqual(len(expected), len(messages))

        for i, message in enumerate(messages):
            self.assertEqual(message['data']['Message-ID'], expected[i][0])
            self.assertEqual(message['origin'], 'http://example.com')
            self.assertEqual(message['uuid'], expected[i][1])
            self.assertEqual(message['updated_on'], expected[i][2])
            self.assertEqual(message['category'], 'message')
            self.assertEqual(message['tag'], 'http://example.com')

    @unittest.mock.patch('perceval.backends.public_inbox.public_inbox.str_to_datetime')
    def test_fetch_exception(self, mock_str_to_datetime):
        """Test whether an exception is thrown when the fetch_items method fails"""

        mock_str_to_datetime.side_effect = Exception

        backend = PublicInbox('http://example.com', self.git_path)

        with self.assertRaises(Exception):
            _ = [m for m in backend.fetch()]

    def test_parse_message(self):
        """Test whether it parses a message from a commit"""

        to_date = datetime.datetime(2010, 3, 15, 13, 25)

        backend = PublicInbox('http://example.com', self.git_path)
        messages = [m for m in backend.fetch(to_date=to_date)]

        self.assertEqual(len(messages), 1)
        message = messages[0]
        # Metadata
        self.assertEqual(message['backend_name'], 'PublicInbox')
        self.assertEqual(message['origin'], 'http://example.com')
        self.assertEqual(message['uuid'], 'bb97b4295fa407bbac478fc137e72c2bd6c71058')
        self.assertEqual(message['updated_on'], 1268659309.0)
        self.assertEqual(message['category'], 'message')
        self.assertEqual(message['tag'], 'http://example.com')
        # Data
        self.assertEqual(message['data']['Message-ID'], '<20100315132149.GA21127@domain3.com>')
        self.assertEqual(message['data']['Date'], 'Mon, 15 Mar 2010 09:21:49 -0400')
        self.assertEqual(message['data']['From'], 'User Name 1 <username1@domain3.com>')
        self.assertEqual(message['data']['To'], 'User Name 2 <username2@domain4.com>')
        self.assertEqual(message['data']['Cc'], 'User Name 3 <username3@domain5.com>,\n       '
                                                'User Name 4 <username4@domain4.com>')
        self.assertEqual(message['data']['Subject'], 'Re: [PATCH] block: commit headline')
        self.assertEqual(message['data']['References'], '<4B9DA6F5.3070606@domain4.com>')
        self.assertEqual(message['data']['In-Reply-To'], '<4B9DA6F5.3070606@domain4.com>')
        expected_body = ('On Mon, Mar 15, 2010 at 11:18:13AM +0800, User Name 2'
            ' wrote:\n> Make the config visible, so we can choose from CONFIG_B'
            'LK_CGROUP=y\n> and CONFIG_BLK_CGROUP=m when CONFIG_IOSCHED_CFQ=m.'
            '\n> \n> Signed-off-by: User Name 2 <username2@domain4.com>\n> ---'
            '\n>  block/Kconfig |    5 +++--\n>  1 files changed, 3 insertions'
            '(+), 2 deletions(-)\n> \n> diff --git a/block/Kconfig b/block/Kco'
            'nfig\n> index 62a5921..906950c 100644\n> --- a/block/Kconfig\n> +'
            '++ b/block/Kconfig\n> @@ -78,8 +78,9 @@ config BLK_DEV_INTEGRITY'
            '\n>  \tProtection.  If in doubt, say N.\n>  \n>  config BLK_CGROU'
            'P\n> -\ttristate\n> +\ttristate "Block cgroup support"\n>  \tdepe'
            'nds on CGROUPS\n> +\tdepends on CFQ_GROUP_IOSCHED\n>  \tdefault n'
            '\n\nHi XXX,\n\nThis part makes sense. If need to give user an opt'
            'ion to keep BLK_CGROUP=y\neven if CFQ=m.\n\n>  \t---help---\n>  '
            '\tGeneric block IO controller cgroup interface. This is the commo'
            'n\n> @@ -91,7 +92,7 @@ config BLK_CGROUP\n>  \tto such task group'
            's.\n>  \n>  config DEBUG_BLK_CGROUP\n> -\tbool\n> +\tbool "Block '
            'cgroup debugging help"\n\n\nWhy are you making DEBUG_BLK_CGROUP t'
            'his as a user visible/configurable\noption? This is already contr'
            'olled by DEBUG_CFQ_IOSCHED. If you don\'t want\nthe DEBUG overhea'
            'd, just set DEBUG_CFQ_IOSCHED=n and DEBUG_BLK_CGROUP will\nnot be'
            ' selected? Making it user visible does not seem to be buying us\n'
            'anything?\n\nThanks\nBBBB\n')
        self.assertIn(expected_body, message['data']['body']['plain'])


class TestPublicInboxCommand(unittest.TestCase):
    """Tests for PublicInboxCommand class"""

    def test_backend_class(self):
        """Test if the backend class is PublicInbox"""

        self.assertIs(PublicInboxCommand.BACKEND, PublicInbox)

    def test_setup_cmd_parser(self):
        """Test if the parser object is correctly initialized"""

        parser = PublicInboxCommand.setup_cmd_parser()
        self.assertIsInstance(parser, BackendCommandArgumentParser)
        self.assertEqual(parser._backend, PublicInbox)

        args = ['http://example.com/',
                '/tmp/example.git/',
                '--tag', 'test',
                '--from-date', '2020-01-01']

        parsed_args = parser.parse(*args)
        self.assertEqual(parsed_args.uri, 'http://example.com/')
        self.assertEqual(parsed_args.gitpath, '/tmp/example.git/')
        self.assertEqual(parsed_args.tag, 'test')
        self.assertEqual(parsed_args.from_date, datetime.datetime(2020, 1, 1, tzinfo=tzutc()))


class TestPublicInboxRepository(unittest.TestCase):

    tmp_path = None

    def setUp(self):
        patcher = unittest.mock.patch('os.getenv')
        self.addCleanup(patcher.stop)
        self.mock_getenv = patcher.start()
        self.mock_getenv.return_value = ''

    @classmethod
    def setUpClass(cls):
        cls.tmp_path = tempfile.mkdtemp(prefix='perceval_')
        tmp_repo_path = os.path.join(cls.tmp_path, 'repos')
        os.mkdir(tmp_repo_path)

        data_path = os.path.dirname(os.path.abspath(__file__))
        tar_path = os.path.join(data_path, 'data/public_inbox/example-repo.git.tar.gz')
        subprocess.check_call(['tar', '-xzf', tar_path, '-C', tmp_repo_path])

        cls.git_path = os.path.join(tmp_repo_path, 'example-repo.git')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_path)

    def test_init(self):
        """Test initialization"""

        repo = PublicInboxRepository('http://example.git', self.git_path)

        self.assertIsInstance(repo, PublicInboxRepository)
        self.assertIsInstance(repo, GitRepository)
        self.assertEqual(repo.uri, 'http://example.git')
        self.assertEqual(repo.dirpath, self.git_path)

        # Check command environment variables
        expected = {
            'LANG': 'C',
            'PAGER': '',
            'HTTP_PROXY': '',
            'HTTPS_PROXY': '',
            'NO_PROXY': '',
            'HOME': ''
        }
        self.assertDictEqual(repo.gitenv, expected)

    def test_ls_tree(self):
        """Test if the command ls-tree is executed correctly"""

        repo = PublicInboxRepository('http://example.git', self.git_path)
        outs = repo.ls_tree('1dabd24990de94716628f3daf5249df416dfaef9', 'm')

        self.assertEqual(outs, '100644 blob d65422239eafa7a4d75e0bd94a0faf0318b9415d	m')

    def test_fail_ls_tree(self):
        """Test if the command ls-tree fails when the commit is not found"""

        repo = PublicInboxRepository('http://example.git', self.git_path)
        expected = "git command - fatal: Not a valid object name aaa"
        with self.assertRaisesRegex(RepositoryError, expected):
            repo.ls_tree('aaa', 'm')

    def test_cat_file(self):
        """Test if the contents of a file are retrieved"""

        repo = PublicInboxRepository('http://example.git', self.git_path)
        contents = repo.cat_file('d65422239eafa7a4d75e0bd94a0faf0318b9415d')
        
        partial_expected = ('Date: Mon, 15 Mar 2010 09:21:49 -0400\n'
                            'From: User Name 1 <username1@domain3.com>\n'
                            'To: User Name 2 <username2@domain4.com>\n'
                            'Cc: User Name 3 <username3@domain5.com>,\n'
                            '       User Name 4 <username4@domain4.com>\n'
                            'Subject: Re: [PATCH] block: commit headline\n'
                            'Message-ID: <20100315132149.GA21127@domain3.com>\n'
                            'References: <4B9DA6F5.3070606@domain4.com>')
        self.assertIn(partial_expected, contents)


if __name__ == "__main__":
    unittest.main(warnings='ignore')
