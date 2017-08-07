import lintreview.github as github
import lintreview.git as git
import logging

from celery import Celery
from lintreview.config import load_config, build_review_config
from lintreview.repo import GithubRepository, GitlabRepository
from lintreview.processor import Processor

config = load_config()
celery = Celery('lintreview.tasks')
celery.config_from_object(config)

log = logging.getLogger(__name__)


@celery.task(ignore_result=True)
def process_pull_request(provider, user, repo_name, number, lintrc):
    """
    Starts processing a pull request and running the various
    lint tools against it.
    """
    log.info('Starting to process lint for %s: %s/%s/%s', provider, user, repo_name, number)
    log.debug("lintrc contents '%s'", lintrc)
    review_config = build_review_config(lintrc, config)

    if len(review_config.linters()) == 0:
        log.info('No configured linters, skipping processing.')
        return

    log.info('Loading pull request data from %s. user=%s '
             'repo=%s number=%s', provider, user, repo_name, number)
    if provider == 'gitlab':
        repo = GitlabRepository(config, user, repo_name)
    else:
        repo = GithubRepository(config, user, repo_name)

    log.info("Before Pull_request %s" % number)
    pull_request = repo.pull_request(number)

    log.info("Before head_repo")
    head_repo = pull_request.clone_url

    log.info("Before private_repo")
    private_repo = pull_request.is_private
    log.info("Before pr_head")
    pr_head = pull_request.head
    log.info("Before target_branch")
    target_branch = pull_request.target_branch

    if target_branch in review_config.ignore_branches():
        log.info('Pull request into ignored branch %s, skipping processing.' %
                 target_branch)
        return

    status = config.get('PULLREQUEST_STATUS', True)
    if status:
        repo.create_status(pr_head, 'pending', 'Lintreview processing...')

    # Clone/Update repository
    target_path = git.get_repo_path(user, repo_name, number, config)
    git.clone_or_update(config, head_repo, target_path, pr_head,
                        private_repo)

    processor = Processor(repo, pull_request,
                          target_path, config)
    processor.load_changes()
    processor.run_tools(review_config)
    processor.publish()

    log.info('Completed lint processing for %s/%s/%s' % (
        user, repo, number))


@celery.task(ignore_result=True)
def cleanup_pull_request(user, repo, number):
    """
    Cleans up a pull request once its been closed.
    """
    log.info("Cleaning up pull request %s/%s/%s", user, repo, number)
    path = git.get_repo_path(user, repo, number, config)
    try:
        git.destroy(path)
    except:
        log.warning("Cannot cleanup '%s' path does not exist.", path)
