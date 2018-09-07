#!/usr/bin/env python
"""
lpmpmessage script will display the formatted merge commit message for the
chosen merge proposal

lpmpmessage depends on ``launchpadlib``, which isn't
necessarily up-to-date in PyPI, so we install it from the archive::

`sudo apt-get install python-launchpadlib` OR

`sudo apt-get install python3-launchpadlib` OR

As we're using ``launchpadlib`` from the archive (which is therefore
installed in the system), you'll need to create your virtualenvs
with the ``--system-site-packages`` option.

Activate your virtualenv and install the requirements::

`pip install -r requirements.txt`

"""
import click
import urwid

from lpshipit import (
    build_commit_msg,
    _format_git_branch_name,
    _get_launchpad_client,
    _set_urwid_widget,
)
# Global var to store the chosen MP's commit message
MP_MESSAGE_OUTPUT = None


def summarize_all_mps(mps):
    mp_content = []
    for mp in mps:
        review_vote_parts = []
        approval_count = 0
        for vote in mp.votes:
            if not vote.is_pending:
                review_vote_parts.append(vote.reviewer.name)
                if vote.comment.vote == 'Approve':
                    approval_count += 1

        description = '' if not mp.description else mp.description
        commit_message = description if not mp.commit_message \
            else mp.commit_message

        short_commit_message = '' if not commit_message \
            else commit_message.splitlines()[0]

        if getattr(mp, 'source_git_repository', None):
            source_repo = '{}/'.format(mp.source_git_repository.display_name)
            target_repo = '{}/'.format(mp.target_git_repository.display_name)
            source_branch = _format_git_branch_name(mp.source_git_path)
            target_branch = _format_git_branch_name(mp.target_git_path)
        else:
            source_repo = ''
            target_repo = ''
            source_branch = mp.source_branch.display_name
            target_branch = mp.target_branch.display_name

        mp_summary = {
            'author': mp.registrant.name,
            'commit_message': commit_message,
            'short_commit_message': short_commit_message,
            'reviewers': sorted(review_vote_parts),
            'approval_count': approval_count,
            'web': mp.web_link,
            'target_branch': target_branch,
            'source_branch': source_branch,
            'target_repo': target_repo,
            'source_repo': source_repo,
            'date_created': mp.date_created
        }

        summary = "{source_repo}{source_branch}" \
                  "\n->{target_repo}{target_branch}" \
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


@click.command()
@click.option('--mp-owner', help='LP username of the owner of the MP '
                                 '(Defaults to system configured user)',
              default=None)
@click.option('--debug/--no-debug', default=False)
def lpmpmessage(mp_owner, debug):
    lp = _get_launchpad_client()
    lp_user = lp.me

    loop = None  # Set the default value for loop used by Urwid UI

    print('Retrieving Merge Proposals from Launchpad...')
    person = lp.people[lp_user.name if mp_owner is None else mp_owner]
    mps = person.getMergeProposals(status=['Needs review', 'Approved'])
    if debug:
        print('Debug: Launchad returned {} merge proposals'.format(len(mps)))
    mp_summaries = summarize_all_mps(mps)
    if mp_summaries:
        def urwid_exit_on_q(key):
            if key in ('q', 'Q'):
                raise urwid.ExitMainLoop()

        def mp_chosen(button, chosen_mp):
            global MP_MESSAGE_OUTPUT
            MP_MESSAGE_OUTPUT = build_commit_msg(
                    author=chosen_mp['author'],
                    reviewers=",".join(
                            chosen_mp['reviewers']),
                    source_branch=chosen_mp['source_branch'],
                    target_branch=chosen_mp['target_branch'],
                    commit_message=chosen_mp[
                        'commit_message'],
                    mp_web_link=chosen_mp['web']
            )
            raise urwid.ExitMainLoop()

        listwalker = urwid.SimpleFocusListWalker(list())
        listwalker.append(urwid.Text(u'Merge Proposal to Merge'))
        listwalker.append(urwid.Divider())

        for mp in mp_summaries:
            button = urwid.Button(mp['summary'])
            urwid.connect_signal(button, 'click', mp_chosen, mp)
            listwalker.append(button)
        mp_box = urwid.ListBox(listwalker)
        try:
            _set_urwid_widget(loop, mp_box, urwid_exit_on_q)
        finally:
            if MP_MESSAGE_OUTPUT:
                print(MP_MESSAGE_OUTPUT)

    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpmpmessage()
