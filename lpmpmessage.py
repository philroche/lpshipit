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
from rich import box
from rich.style import Style
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from textual.app import App
from textual.events import Click, MouseDown
from textual.reactive import Reactive
from textual import events
from textual.widget import Widget
from textual.widgets import Header, Footer, Placeholder, ScrollView
from textual.widgets import Button
from typing import Optional

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


class Label(Widget):

    label: Reactive[str] = Reactive('')

    def __init__(self, label: str, name: Optional[str] = None):
        super().__init__(name=name)
        self.label = label

    def render(self) -> Panel:
        return Panel(self.label, box=box.SQUARE)

    def on_click(self, event: Click) -> None:
        event.prevent_default().stop()
        self.label += 'clicked'


class LPMPMessageApp(App):

    async def on_load(self, event: events.Load) -> None:
        """Bind keys with the app loads (but before entering application mode)"""
        await self.bind("q", "quit", "Quit")

    async def on_mount(self) -> None:
        """Create and dock the widgets."""

        # A scrollview to contain the markdown file
        self.body = body = ScrollView(auto_width=True)

        # Header / footer / dock
        await self.view.dock(Footer(), edge="bottom")
        await self.view.dock(body)

        async def add_content():
            table = Table(title="Choose Merge Proposal", box=box.ASCII, show_header=True, expand=True,
                          row_styles=[Style(frame=True, bgcolor='red'), Style(frame=True, bgcolor='blue')])
            table.add_column("[cyan]author",
                             justify="left",
                             no_wrap=True,)
            table.add_column("[blue]repo",
                             justify="left",
                             no_wrap=False, )
            table.add_column("[blue]button",
                             justify="left",
                             no_wrap=False, )
            for i in range(19):

                table.add_row("repo", "test label in table", Panel("Choose"))

            await body.update(table)

        await self.call_later(add_content)


@click.command()
@click.option('--mp-owner', help='LP username of the owner of the MP '
                                 '(Defaults to system configured user)',
              default=None)
@click.option('--debug/--no-debug', default=False)
def lpmpmessage(mp_owner, debug):
    LPMPMessageApp.run(log="textual.log")

    lp = _get_launchpad_client()
    lp_user = lp.me

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
            _set_urwid_widget(mp_box, urwid_exit_on_q)
        finally:
            if MP_MESSAGE_OUTPUT:
                print(MP_MESSAGE_OUTPUT)

    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpmpmessage()





