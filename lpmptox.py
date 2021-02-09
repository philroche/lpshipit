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
import os
import subprocess
from tempfile import TemporaryDirectory
import urwid

from lpshipit import (
    _get_launchpad_client,
    _set_urwid_widget,
    summarize_git_mps,
)
from lxc import lxc_container

# Global var to store the chosen MP
CHOSEN_MP = None

def _write_debug(output_file, message):
    output_file.write('{}\n'.format(message))
    output_file.flush()
    print(message)


def runtox(source_repo, source_branch,
           tox_command='tox --recreate --parallel auto',
           output_filepath=os.devnull,
           environment=None):
    with open(output_filepath, "a") as output_file, TemporaryDirectory() as local_repo:
        _write_debug(output_file, 'Cloning {} (branch {}) in to tmp directory {} ...'.format(
            source_repo,
            source_branch,
            local_repo))
        repo = git.Repo.clone_from(
            source_repo,
            local_repo,
            depth=1,
            single_branch=True,
            branch=source_branch
        )
        _write_debug(output_file, '{} {}'.format(
            repo.head.object.hexsha,
            repo.head.object.summary
        ))

        if environment is not None:
            _write_debug(output_file, 'Running `{}` in {} lxc environment ...'.format(tox_command, environment))
            return _run_tox_in_lxc(environment, local_repo, tox_command, output_file)
        else:
           _write_debug(output_file, 'Running `{}` in {} ...'.format(tox_command, local_repo))
           return _run_tox_locally(local_repo, tox_command, output_file)

def _run_tox_in_lxc(environment, local_repo, tox_command, output_file):
    with lxc_container(environment, local_repo) as container:
        container.run_command('sudo --preserve-env="http_proxy,https_proxy" apt-get update')
        container.run_command('sudo --preserve-env="http_proxy,https_proxy" apt-get install -y python3-pip')
        pip_proxy = "--proxy {}"\
            .format(container.proxy_netloc) if container.proxy_netloc else ""
        pip_proxy = ""
        container.run_command('sudo --preserve-env="http_proxy,https_proxy" pip3 {} install tox'.format(pip_proxy))
        # local_repo is same path in the container
        return container.run_command(tox_command + ' -c ' + local_repo)

def _run_tox_locally(local_repo, tox_command, output_file):
    process = subprocess.Popen(tox_command,
                            stdout=subprocess.PIPE,
                            shell=True,
                            cwd=local_repo)
    while process.poll() is None:
        _write_debug(output_file, process.stdout.readline().decode('utf-8').rstrip())
    return process.returncode


@click.command()
@click.option('--mp-owner', help='LP username of the owner of the MP '
                                 '(Defaults to system configured user)',
              default=None)
@click.option('--debug/--no-debug', default=False)
@click.option('--environment', default=None, help = 'release (16.04, 18.04, etc) to run tox in')
def lpmptox(mp_owner, debug, environment):
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
                runtox(source_repo, source_branch, environment=environment)
    else:
        print("You have no Merge Proposals in either "
              "'Needs review' or 'Approved' state")


if __name__ == "__main__":
    lpmptox()
