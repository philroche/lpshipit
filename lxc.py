import contextlib
import os
import subprocess
import time


class LxcContainer:
    def __init__(self, environment, name):
        self.name = name
        image='ubuntu:{}'.format(environment)
        subprocess.check_output('lxc launch {} {}'.format(image,name), 
                                stdin=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                shell=True) 
        self.wait_for_networking()
        self.user = subprocess.check_output('lxc exec {} -- whoami'.format(self.name),
                                            stdin=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            shell=True).decode('utf-8').strip()
        self.home = subprocess.check_output('lxc exec {} -- pwd'.format(self.name),
                                             stdin=subprocess.PIPE,
                                             stderr=subprocess.STDOUT,
                                             shell=True).decode('utf-8').strip()

    def wait_for_networking(self):
        for _ in range(10):
            if self.run_command('sh -c "curl -s --head http://archive.ubuntu.com > /dev/null"') == 0:
                return  # We have networking, exit out
            time.sleep(6)
        raise Exception('Networking did not come up in 60 seconds')
    
    def setup_code_directory(self, tmp_directory):
        subprocess.check_call('lxc file push -rp {} {}'.format(tmp_directory,
                                                               self.name + '/tmp'),
                               stdin=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               shell=True)
        subprocess.check_call('lxc file push {} -rp {}'.format( 
                                                       os.environ['HOME'] + '/.ssh', 
                                                       self.name + self.home),
                               stdin=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               shell=True)
        subprocess.check_call('lxc file push {} -rp {}'.format( 
                                                       os.environ['HOME'] + '/.gitconfig', 
                                                       self.name + self.home),
                               stdin=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               shell=True)
        # need to change ownership for ssh to work
        self.run_command('chown -R {0}:{0} {1}'.format(self.user, self.home))



    def run_command(self, cmd):
        lxc_command = 'lxc exec {} -- {}'.format(self.name, cmd)
        print("Running {}".format(lxc_command))
        process = subprocess.Popen(lxc_command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        shell=True)
        while process.poll() is None:
            debug_message = process.stdout.readline().decode('utf-8').rstrip()
            print(debug_message)
        return process.returncode

@contextlib.contextmanager
def lxc_container(environment, cwd):
    name = 'cpc-' + subprocess.check_output('petname',
                                            stdin=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            shell=True).decode('utf-8').strip()
    try:
        instance = LxcContainer(environment, name)
        instance.setup_code_directory(cwd)
        yield instance
    finally:
        subprocess.check_call('lxc delete --force {}'.format(name),
                              stdin=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              shell=True)
