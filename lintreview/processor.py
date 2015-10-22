import logging
import lintreview.tools as tools

from lintreview.diff import DiffCollection
from lintreview.review import Problems
from lintreview.review import Review

log = logging.getLogger(__name__)


class Processor(object):

    _client = None
    _number = None
    _head = None
    _target_path = None
    _changes = None
    _problems = None
    _review = None
    _config = None

    def __init__(self, client, number, head, target_path, config=None):
        self._client = client
        self._number = number
        self._head = head
        self._target_path = target_path
        self._problems = Problems(target_path)
        self._review = Review(client, number)

        if config is None:
            config = {}
        self._config = config

    def load_changes(self):
        log.info('Loading pull request patches from github.')
        #files = [file for file in self._client.pull_request(self._number).files()]
        files = list(self._client.pull_request(self._number).files())
        self._changes = DiffCollection(files)
        self._problems.set_changes(self._changes)

    def run_tools(self, review_config):
        if self._changes is None:
            raise RuntimeError('No loaded changes, cannot run tools. '
                               'Try calling load_changes first.')
        files_to_check = self._changes.get_files(
            append_base=self._target_path,
            ignore_patterns=review_config.ignore_patterns())
        commits_to_check = self.get_commits(self._number)
        tools.run(
            review_config,
            self._problems,
            files_to_check,
            commits_to_check,
            self._target_path)

    def publish(self):
        self._problems.limit_to_changes()
        self._review.publish(
            self._problems,
            self._head,
            self._config.get('SUMMARY_THRESHOLD'))

    def get_commits(self, number):
	return self._client.pull_request(number).commits()
