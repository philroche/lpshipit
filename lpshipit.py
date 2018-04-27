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
import urwid

from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import UnencryptedFileCredentialStore


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

            description = '' if not mp.description else mp.description
            commit_message = description if not mp.commit_message \
                else mp.commit_message

            short_commit_message = '' if not commit_message \
                else commit_message.splitlines()[0]

            mp_summary = {
                'author': mp.registrant.name,
                'commit_message': commit_message,
                'short_commit_message': short_commit_message,
                'reviewers': sorted(review_vote_parts),
                'approval_count': approval_count,
                'web': mp.web_link,
                'target_branch': target_branch,
                'source_branch': source_branch,
                'target_repo': target_repo.display_name,
                'source_repo': source_repo.display_name,
                'date_created': mp.date_created
            }

            summary = "{source_repo}/{source_branch}" \
                      "\n->{target_repo}/{target_branch}" \
                      "\n    {short_commit_message}" \
                      "\n    {approval_count} approvals ({str_reviewers})" \
                      "\n    {date_created} - {web}" \
                .format(**mp_summary, str_reviewers=","
                        .join(mp_summary['reviewers']))

            mp_summary['summary'] = summary

            mp_content.append(mp_summary)

    sorted_mps = sorted(mp_content,
                        key=lambda k: k['date_created'],
                        reverse=True)
    return sorted_mps


def build_commit_msg(author, reviewers, source_branch, target_branch,
                     commit_message, mp_web_link):
    """Builds the agreed convention merge commit message"""
    return "Merge {} into {} [a={}] [r={}]\n\n{}\n\nMP: {}".format(
        source_branch, target_branch, author,
        reviewers, commit_message, mp_web_link)


@click.command()
@click.option('--directory', default=None, help='Path to local directory')
@click.option('--source-branch', help='Source branch name')
@click.option('--target-branch', help='Target Branch name')
@click.option('--mp-owner', help='LP username of the owner of the MP '
                                 '(Defaults to system configured user)',
              default=None)
def lpshipit(directory, source_branch, target_branch, mp_owner):
    """Invokes the commit building with proper user inputs."""
    lp = _get_launchpad_client()
    lp_user = lp.me

    print('Retrieving Merge Proposals from Launchpad...')
    person = lp.people[lp_user.name if mp_owner is None else mp_owner]
    mps = person.getMergeProposals(status=['Needs review', 'Approved'])
    mp_summaries = summarize_mps(mps)
    if mp_summaries:

        def urwid_exit_on_q(key):
            if key in ('q', 'Q'):
                raise urwid.ExitMainLoop()

        def urwid_exit_program(button):
            raise urwid.ExitMainLoop()

        def mp_chosen(user_args, button, chosen_mp):
            source_branch, target_branch, directory, repo, checkedout_branch =\
                user_args['source_branch'], \
                user_args['target_branch'], \
                user_args['directory'], \
                user_args['repo'], \
                user_args['checkedout_branch']

            local_branches = [branch.name for branch in repo.branches]

            def source_branch_chosen(user_args, button, chosen_source_branch):
                chosen_mp, target_branch, directory, repo, checkedout_branch =\
                    user_args['chosen_mp'], \
                    user_args['target_branch'], \
                    user_args['directory'], \
                    user_args['repo'], \
                    user_args['checkedout_branch']

                def target_branch_chosen(user_args, button, target_branch):

                    source_branch, chosen_mp, directory, repo, \
                    checkedout_branch = \
                        user_args['source_branch'], \
                        user_args['chosen_mp'], \
                        user_args['directory'], \
                        user_args['repo'], \
                        user_args['checkedout_branch']

                    if target_branch != source_branch:
                        local_git = git.Git(directory)

                        commit_message = build_commit_msg(
                                author=chosen_mp['author'],
                                reviewers=",".join(
                                        chosen_mp['reviewers']),
                                source_branch=source_branch,
                                target_branch=target_branch,
                                commit_message=chosen_mp[
                                    'commit_message'],
                                mp_web_link=chosen_mp['web']
                        )

                        repo.branches[target_branch].checkout()

                        local_git.execute(
                                ["git", "merge", "--no-ff", source_branch,
                                 "-m", commit_message])

                        merge_summary = "{source_branch} has been merged " \
                                        "in to {target_branch} \nChanges " \
                                        "have _NOT_ been pushed".format(
                                        source_branch=source_branch,
                                        target_branch=target_branch
                                        )

                        merge_summary_listwalker = urwid.SimpleFocusListWalker(
                            list())
                        merge_summary_listwalker.append(
                                urwid.Text(u'Merge Summary'))
                        merge_summary_listwalker.append(
                                urwid.Divider())
                        merge_summary_listwalker.append(
                                urwid.Text(merge_summary))
                        merge_summary_listwalker.append(
                                urwid.Divider())
                        button = urwid.Button("Exit")
                        urwid.connect_signal(button,
                                             'click',
                                             urwid_exit_program)
                        merge_summary_listwalker.append(button)
                        merge_summary_box = urwid.ListBox(
                                merge_summary_listwalker)
                        loop.widget = merge_summary_box
                    else:
                        error_text = urwid.Text('Source branch and target '
                                                'branch can not be the same. '
                                                '\n\nPress Q to exit.')
                        error_box = urwid.Filler(error_text, 'top')
                        loop.unhandled_input = urwid_exit_on_q
                        loop.widget = error_box

                user_args = {'chosen_mp': chosen_mp,
                             'source_branch': chosen_source_branch,
                             'directory': directory,
                             'repo': repo,
                             'checkedout_branch': checkedout_branch}
                if not target_branch:
                    target_branch_listwalker = urwid.SimpleFocusListWalker(
                        list())
                    target_branch_listwalker.append(
                            urwid.Text(u'Target Branch'))
                    target_branch_listwalker.append(urwid.Divider())
                    focus_counter = 1
                    focus = None
                    for local_branch in local_branches:
                        focus_counter = focus_counter + 1
                        button = urwid.Button(local_branch)
                        urwid.connect_signal(button,
                                             'click',
                                             target_branch_chosen,
                                             local_branch,
                                             user_args=[user_args])
                        target_branch_listwalker.append(button)

                        if local_branch == chosen_mp['target_branch']:
                            focus = focus_counter
                        if checkedout_branch \
                                and hasattr(checkedout_branch, 'name') \
                                and local_branch == checkedout_branch.name \
                                and focus is None:
                            focus = focus_counter

                    if focus:
                        target_branch_listwalker.set_focus(focus)

                    target_branch_box = urwid.ListBox(target_branch_listwalker)
                    loop.widget = target_branch_box
                else:
                    target_branch_chosen(user_args, None, target_branch)
            user_args = {'chosen_mp': chosen_mp,
                         'target_branch': target_branch,
                         'directory': directory,
                         'repo': repo,
                         'checkedout_branch': checkedout_branch}
            if not source_branch:
                source_branch_listwalker = urwid.SimpleFocusListWalker(list())
                source_branch_listwalker.append(urwid.Text(u'Source Branch'))
                source_branch_listwalker.append(urwid.Divider())
                focus_counter = 1
                focus = None
                for local_branch in local_branches:
                    focus_counter = focus_counter + 1
                    button = urwid.Button(local_branch)
                    urwid.connect_signal(button, 'click',
                                         source_branch_chosen,
                                         local_branch,
                                         user_args=[user_args])
                    source_branch_listwalker.append(button)
                    if local_branch == chosen_mp['source_branch']:
                        focus = focus_counter
                    if checkedout_branch \
                            and hasattr(checkedout_branch, 'name') \
                            and local_branch == checkedout_branch.name \
                            and focus is None:
                        focus = focus_counter

                if focus:
                    source_branch_listwalker.set_focus(focus)

                source_branch_box = urwid.ListBox(source_branch_listwalker)
                loop.widget = source_branch_box
            else:
                source_branch_chosen(user_args, None, source_branch)

        def directory_chosen(directory):
            repo = git.Repo(directory)
            checkedout_branch = None
            try:
                checkedout_branch = repo.active_branch
            except TypeError:
                # This is OK, it more than likely means a detached HEAD
                pass
            listwalker = urwid.SimpleFocusListWalker(list())
            listwalker.append(urwid.Text(u'Merge Proposal to Merge'))
            listwalker.append(urwid.Divider())
            user_args = {'source_branch': source_branch,
                         'target_branch': target_branch,
                         'directory': directory,
                         'repo': repo,
                         'checkedout_branch': checkedout_branch
                         }

            for mp in mp_summaries:
                button = urwid.Button(mp['summary'])
                urwid.connect_signal(button, 'click', mp_chosen, mp,
                                     user_args=[user_args])
                listwalker.append(button)
            mp_box = urwid.ListBox(listwalker)
            loop.unhandled_input = urwid_exit_on_q
            loop.widget = mp_box

        if not directory:
            class GetDirectoryBox(urwid.Filler):
                def keypress(self, size, key):
                    if key != 'enter':
                        return super(GetDirectoryBox, self).keypress(size, key)
                    chosen_directory = directory_q.edit_text.strip()
                    if chosen_directory == '':
                        chosen_directory = os.getcwd()
                    if os.path.isdir(chosen_directory):
                        directory_chosen(chosen_directory)
                    else:
                        error_text = urwid.Text('{} is not a valid directory. '
                                                '\n\nPress Q to exit.'
                                                .format(chosen_directory))
                        error_box = urwid.Filler(error_text, 'top')
                        loop.unhandled_input = urwid_exit_on_q
                        loop.widget = error_box

            directory_q = urwid.Edit(
                    u"Which directory [{current_directory}]?\n".format(
                            current_directory=os.getcwd()
                    ))
            fill = GetDirectoryBox(directory_q, 'top')
            loop = urwid.MainLoop(fill, unhandled_input=urwid_exit_on_q)
            loop.run()


    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpshipit()
