import logging
import pkg_resources

from flask import Flask, request, Response
from lintreview.config import load_config
from lintreview.github import get_repository
from lintreview.github import get_lintrc
from lintreview import gitlab_lr
from lintreview.tasks import process_pull_request
from lintreview.tasks import cleanup_pull_request

config = load_config()
app = Flask("lintreview")
app.config.update(config)

log = logging.getLogger(__name__)
version = pkg_resources.get_distribution('lintreview').version


@app.route("/ping")
def ping():
    return "lint-review: %s pong\n" % (version,)


@app.route("/review/start", methods=["POST"])
def start_review():
    if not any(host_header in request.headers for host_header in ('X-GitHub-Event', 'X-GitLab-Event')):
        return Response(status=400)

    if 'X-GitHub-Event' in request.headers:
        return handle_github_hook()
    else:
        return handle_gitlab_hook()


def handle_gitlab_hook():
    try:
        object_attributes = request.json["object_attributes"]
        action = object_attributes["action"]
        number = object_attributes["iid"]
        base_repo_url = object_attributes["target"]["url"]
        head_repo_url = object_attributes["source"]["url"]
        head_repo_ref = object_attributes["source_branch"]
        user = object_attributes["target"]["namespace"]
        head_user = object_attributes["source"]["namespace"]
        repo = object_attributes["target"]["name"]
        head_repo = object_attributes["source"]["name"]

    except Exception as e:
        log.error("Got an invalid JSON body. '%s'", e)
        return Response(status=403,
                        response="You must provide a valid JSON body\n")

    log.info("Received GitLab merge request notification for "
             "%s %s, (%s) from: %s",
             base_repo_url, number, action, head_repo_url)

    if action not in ("open", "reopen", "close"):
        log.info("Ignored '%s' action." % action)
        return Response(status=204)

    if action == "close":
        return close_review(user, repo, pull_request) # FIXME

    gl = gitlab.get_repository(app.config, head_user, head_repo)
    try:
        lintrc = gitlab.get_lintrc(gl, head_repo_ref)
        log.debug("lintrc file contents '%s'", lintrc)
    except Exception as e:
        log.warn("Cannot download .lintrc file for '%s', "
                 "skipping lint checks.", base_repo_url)
        log.warn(e)
        return Response(status=204)
    try:
        log.info("Scheduling pull request for %s/%s %s", user, repo, number)
        process_pull_request.delay(user, repo, number, lintrc)  # FIXME
    except:
        log.error('Could not publish job to celery. Make sure its running.')
        return Response(status=500)
    return Response(status=204)


def handle_github_hook():
    event = request.headers.get('X-Gitlab-Event')
    if event == 'ping':
        return Response(status=200)

    try:
        action = request.json["action"]
        pull_request = request.json["pull_request"]
        number = pull_request["number"]
        base_repo_url = pull_request["base"]["repo"]["git_url"]
        head_repo_url = pull_request["head"]["repo"]["git_url"]
        head_repo_ref = pull_request["head"]["ref"]
        user = pull_request["base"]["repo"]["owner"]["login"]
        head_user = pull_request["head"]["repo"]["owner"]["login"]
        repo = pull_request["base"]["repo"]["name"]
        head_repo = pull_request["head"]["repo"]["name"]
    except Exception as e:
        log.error("Got an invalid JSON body. '%s'", e)
        return Response(status=403,
                        response="You must provide a valid JSON body\n")

    log.info("Received GitHub pull request notification for "
             "%s %s, (%s) from: %s",
             base_repo_url, number, action, head_repo_url)

    if action not in ("opened", "synchronize", "reopened", "closed"):
        log.info("Ignored '%s' action." % action)
        return Response(status=204)

    if action == "closed":
        return close_review(user, repo, pull_request)

    gh = get_repository(app.config, head_user, head_repo)
    try:
        lintrc = get_lintrc(gh, head_repo_ref)
        log.debug("lintrc file contents '%s'", lintrc)
    except Exception as e:
        log.warn("Cannot download .lintrc file for '%s', "
                 "skipping lint checks.", base_repo_url)
        log.warn(e)
        return Response(status=204)
    try:
        log.info("Scheduling pull request for %s/%s %s", user, repo, number)
        process_pull_request.delay(user, repo, number, lintrc)
    except:
        log.error('Could not publish job to celery. Make sure its running.')
        return Response(status=500)
    return Response(status=204)


def close_review(user, repo, pull_request):
    try:
        log.info("Scheduling cleanup for %s/%s", user, repo)
        cleanup_pull_request.delay(user, repo, pull_request['number'])
    except:
        log.error('Could not publish job to celery. '
                  'Make sure its running.')
    return Response(status=204)
