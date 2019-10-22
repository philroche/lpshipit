#!/usr/bin/env python
"""
lpmptox script will run tox on changes in a selected MP

lpmptox depends on ``launchpadlib``, which isn't
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
import git
import subprocess
from tempfile import TemporaryDirectory
import urwid

from lpshipit import (
    _get_launchpad_client,
    _set_urwid_widget,
    summarize_git_mps,
)

# Global var to store the chosen MP
CHOSEN_MP = None


def runtox(source_repo, source_branch, command='tox --recreate'):
    with TemporaryDirectory() as local_repo:
        print('Cloning {} in to tmp directory {} ...'.format(
            source_repo,
            local_repo))
        repo = git.Repo.clone_from(source_repo, local_repo)
        print('Checking out branch {} ... '.format(source_branch))
        repo.git.checkout(source_branch)
        print('Running tox in {} ...'.format(local_repo))
        process = subprocess.Popen(command,
                                   stdout=subprocess.PIPE,
                                   shell=True,
                                   cwd=local_repo)
        while process.poll() is None:
            print(process.stdout.readline().decode('utf-8').rstrip())
    return process.returncode


@click.command()
@click.option('--mp-owner', help='LP username of the owner of the MP '
                                 '(Defaults to system configured user)',
              default=None)
@click.option('--debug/--no-debug', default=False)
def lpmptox(mp_owner, debug):
    """Invokes the commit building with proper user inputs."""
    lp = _get_launchpad_client()
    lp_user = lp.me

    print('Retrieving Merge Proposals from Launchpad...')
    person = lp.people[lp_user.name if mp_owner is None else mp_owner]
    mps = person.getMergeProposals(status=['Needs review', 'Approved'])
    if debug:
        print('Debug: Launchad returned {} merge proposals'.format(len(mps)))
    mp_summaries = summarize_git_mps(mps)

    if mp_summaries:

        def urwid_exit_on_q(key):
            if key in ('q', 'Q'):
                raise urwid.ExitMainLoop()

        def mp_chosen(button, chosen_mp):
            global CHOSEN_MP
            CHOSEN_MP = chosen_mp

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
            if CHOSEN_MP:
                source_repo = CHOSEN_MP['source_repo']
                source_branch = CHOSEN_MP['source_branch']
                runtox(source_repo, source_branch)

    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpmptox()
