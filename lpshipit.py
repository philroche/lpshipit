#!/usr/bin/env python
"""
LPShipit script will merge all commits from a given feature branch
as a single non fast forward merge, while adding the proper agreed upon
commit message formatting.

Once run in the directory of your cloned repo it will prompt which branches
to merge. This does not push any changes.

lpshipit depend on ``launchpadlib``, which isn't
necessarily up-to-date in PyPI, so we install it from the archive::

`sudo apt-get install python-launchpadlib` OR

`sudo apt-get install python3-launchpadlib` OR

As we're using ``launchpadlib`` from the archive (which is therefore
installed in the system), you'll need to create your virtualenvs
with the ``--system-site-packages`` option.

Activate your virtualenv and install the requirements::

`pip install -r requirements.txt`


"""
import os

import click
import git

from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import UnencryptedFileCredentialStore

from picker import pick


def _get_launchpad_client():
    cred_location = os.path.expanduser('~/.lp_creds')
    credential_store = UnencryptedFileCredentialStore(cred_location)
    return Launchpad.login_with('cpc', 'production', version='devel',
                                credential_store=credential_store)


def _format_git_branch_name(branch_name):
    if branch_name.startswith('refs/heads/'):
        return branch_name[len('refs/heads/'):]
    return branch_name


def summarize_mps(mps):
    mp_content = []
    for mp in mps:
        if getattr(mp, 'source_git_repository', None):
            review_vote_parts = []
            approval_count = 0
            for vote in mp.votes:
                if not vote.is_pending:
                    review_vote_parts.append(vote.reviewer.name)
                    if vote.comment.vote == 'Approve':
                        approval_count += 1

            source_repo = mp.source_git_repository
            target_repo = mp.target_git_repository
            source_branch = _format_git_branch_name(mp.source_git_path)
            target_branch = _format_git_branch_name(mp.target_git_path)

            mp_content.append({
                'author': mp.registrant.name,
                'description': mp.description,
                'short_description': mp.description.splitlines()[0],
                'reviewers': review_vote_parts,
                'approval_count': approval_count,
                'web': mp.web_link,
                'target_branch': target_branch,
                'source_branch': source_branch,
                'target_repo': target_repo.display_name,
                'source_repo': source_repo.display_name
            })
    return mp_content


def build_commit_msg(author, reviewers, source_branch, target_branch,
                     commit_message, mp_web_link):
    """Builds the agreed convention merge commit message"""
    return "Merge {} into {} [a={}] [r={}]\n\n{}\n\nMP: {}".format(
        source_branch, target_branch, author,
        reviewers, commit_message, mp_web_link)


@click.command()
@click.option('--directory', default=os.getcwd(), prompt='Which directory',
              help='Path to local directory')
@click.option('--source-branch', help='Source branch name')
@click.option('--target-branch', help='Target Branch name')
def lpshipit(directory, source_branch, target_branch):
    """Invokes the commit building with proper user inputs."""
    lp = _get_launchpad_client()
    lp_user = lp.me
    repo = git.Repo(directory)
    local_git = git.Git(directory)
    checkedout_branch = repo.active_branch

    person = lp.people[lp_user.name]
    mps = person.getMergeProposals(status=['Needs review', 'Approved'])
    mp_summaries = summarize_mps(mps)
    if mp_summaries:
        mp_options = ["{source_repo}/{source_branch}"
                      "->{target_repo}/{target_branch}"
                      "\n\t{short_description}"
                      "\n\t{approval_count} approvals ({str_reviewers})"
                      "\n\t{web} "
                      .format(**mp, str_reviewers=",".join(mp['reviewers']))
                      for mp in mp_summaries]
        chosen_mp, chosen_mp_index = pick(
            mp_options, "Merge Proposal",
            indicator='=>',
            line_count=4)

        chosen_mp_summary = mp_summaries[chosen_mp_index]

        local_branches = [branch.name for branch in repo.branches]

        if not source_branch:
            source_branch, source_branch_index = pick(
                local_branches, "Source Branch",
                indicator='=>',
                default_index=
                local_branches.index(chosen_mp_summary['source_branch'])
                if chosen_mp_summary['source_branch'] in local_branches
                else local_branches.index(checkedout_branch.name))

        if not target_branch:
            target_branch, target_branch_index = pick(
                local_branches, "Target Branch",
                indicator='=>',
                default_index=
                local_branches.index(chosen_mp_summary['target_branch'])
                if chosen_mp_summary['target_branch'] in local_branches
                else 0)

        if target_branch != source_branch:
            commit_message = build_commit_msg(
                author=chosen_mp_summary['author'],
                reviewers=",".join(chosen_mp_summary['reviewers']),
                source_branch=source_branch,
                target_branch=target_branch,
                commit_message=chosen_mp_summary['description'],
                mp_web_link=chosen_mp_summary['web']
                )

            repo.branches[target_branch].checkout()

            local_git.execute(["git", "merge",  "--no-ff", source_branch,
                               "-m", commit_message])

            print("{source_branch} has been merged in to {target_branch} \n"
                  "Changes have _NOT_ been pushed".format(
                    source_branch=source_branch,
                    target_branch=target_branch
                    ))
    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpshipit()
