import logging
import gitlab
from functools import partial

log = logging.getLogger(__name__)



def get_client(config):
    """
    Factory for the Github client
    """
    return gitlab.Gitlab('https://gitlab.com', config['GITHUB_OAUTH_TOKEN'])


def get_repository(config, user, repo):
    gl = get_client(config)
    return gl.projects.get('{}/{}'.format(user, repo))


def get_lintrc(repo, ref):
    """
    Download the .lintrc from a repo
    """
    log.info('Fetching lintrc file')
    response = repo.repository_blob(ref, '.lintrc')
    return response
