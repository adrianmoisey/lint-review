import lintreview.github as github
import lintreview.gitlab as gitlab
import logging

log = logging.getLogger(__name__)

class Repository(object):
    def __init__(self, config, user, repo_name):
        self.config = config
        self.user = user
        self.repo_name = repo_name


class GithubRepository(Repository):
    """Abstracting wrapper for the
    various interactions we have with github.

    This will make swapping in other hosting systems
    a tiny bit easier in the future.
    """

    def repository(self):
        """Get the underlying repository model
        """
        self.repo = github.get_repository(
            self.config,
            self.user,
            self.repo_name)
        return self.repo

    def pull_request(self, number):
        """Get a pull request by number.
        """
        pull = self.repository().pull_request(number)
        return GithubPullRequest(pull)

    def ensure_label(self, label):
        """Create label if it doesn't exist yet
        """
        repo = self.repository()
        if not repo.label(label):
            repo.create_label(
                name=label,
                color="bfe5bf",  # a nice light green
            )

    def create_status(self, sha, state, description):
        """Create a commit status
        """
        context = self.config.get('APP_NAME', 'lintreview')
        repo = self.repository()
        repo.create_status(
            sha,
            state,
            None,
            description,
            context)


class GithubPullRequest(object):
    """Abstract the underlying github models.
    This makes other code simpler, and enables
    the ability to add other hosting services later.
    """

    def __init__(self, pull_request):
        self.pull = pull_request

    @property
    def display_name(self):
        data = self.pull.as_dict()
        return u'%s#%s' % (data['head']['repo']['full_name'],
                           data['number'])

    @property
    def number(self):
        return self.pull.number

    @property
    def is_private(self):
        data = self.pull.as_dict()
        return data['head']['repo']['private']

    @property
    def head(self):
        data = self.pull.as_dict()
        return data['head']['sha']

    @property
    def clone_url(self):
        data = self.pull.as_dict()
        return data['head']['repo']['clone_url']

    @property
    def base_repo_url(self):
        data = self.pull.as_dict()
        return data['base']['repo']['clone_url']

    @property
    def target_branch(self):
        data = self.pull.as_dict()
        return data['base']['ref']

    def commits(self):
        return self.pull.commits()

    def review_comments(self):
        return self.pull.review_comments()

    def files(self):
        return list(self.pull.files())

    def remove_label(self, label_name):
        issue = self.pull.issue()
        labels = issue.labels()
        if not any(label_name == label.name for label in labels):
            return
        log.debug("Removing issue label '%s'", label_name)
        issue.remove_label(label_name)

    def add_label(self, label_name):
        issue = self.pull.issue()
        issue.add_labels(label_name)

    def create_comment(self, body):
        self.pull.create_comment(body)

    def create_review_comment(self, body, commit_id, path, position):
        self.pull.create_review_comment(body, commit_id, path, position)


class GitlabRepository(Repository):
    """Abstracting wrapper for the
    various interactions we have with gitlab

    This will make swapping in other hosting systems
    a tiny bit easier in the future.
    """

    def repository(self):
        """Get the underlying repository model
        """
        self.repo = gitlab.get_repository(
            self.config,
            self.repo_name)
        return self.repo

    def pull_request(self, number):
        """Get a pull request by number.
        """
        print "Before repo"
        repository = self.repository()
        print "before pull"
        pull = self.repository().mergerequests.get(number)
        print "before return"
        return GitlabPullRequest(config, repository, pull)

    def ensure_label(self, label):
        """Create label if it doesn't exist yet
        """
        repo = self.repository()
        if not repo.labels.get(label_name):
            repo.labels.create({
                'name': label,
                'color': "bfe5bf",  # a nice light green
            })

    def create_status(self, sha, state, description):
        """Create a commit status
        """
        context = self.config.get('APP_NAME', 'lintreview')
        repo = self.repository()
        commit = repo.commits.get(sha)
        commit.statuses.create({
            'name': 'lintreview',
            'description': description,
            'state': state,
            })

class GitlabPullRequest(object):
    """Abstract the underlying gitlab models.
    This makes other code simpler, and enables
    the ability to add other hosting services later.
    """

    def __init__(self, config, repository, pull_request):
        self.config = config
        self.project = repository
        self.pull = pull_request

    @property
    def display_name(self):
        name = self.project.as_dict()['path_with_namespace']
        number = self.pull.iid
        return u'%s#%s' % (name, number)

    @property
    def number(self):
        return self.pull.iid

    @property
    def is_private(self):
        return self.project.as_dict()['public']

    @property
    def head(self):
        return self.pull.as_dict()['sha']

    @property
    def clone_url(self):
        return self.project.as_dict()['http_url_to_repo']

    @property
    def base_repo_url(self):
        target_project_id = self.pull.as_dict()['target_project_id']
        target_branch = self.pull.as_dict()['target_branch']
        target_repo = gitlab.get_repository(self.config, target_project_id)
        return target_repo.as_dict()['ssh_url_to_repo']

    @property
    def target_branch(self):
        return self.pull.as_dict()['target_branch']

    def commits(self):
        return self.pull.commits()

    def review_comments(self):
        return self.pull.notes.list()

    def files(self):
        return self.pull.changes()['changes']

    def remove_label(self, label_name):
        if not any(label_name == label for label in self.pull.labels):
            return
        log.debug("Removing issue label '%s'", label_name)
        self.pull.labels.remove(label_name)
        self.pull.save()

    def add_label(self, label_name):
        self.pull.label.append(label_name)
        self.pull.save()

    def create_comment(self, body):
        self.pull.notes.create({
            'body': body
        })

#    def create_review_comment(self, body, commit_id, path, position):
#        self.pull.create_review_comment(body, commit_id, path, position)
# https://forum.gitlab.com/t/api-to-post-inline-comment-to-merge-request/5837
