import argparse
import subprocess
import socket

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=1)
    parser.add_argument('--init', action='store_true')
    args = parser.parse_args()
    global NNodes
    NNodes = args.n
    return args


HOSTFILE = '/home/ubuntu/spotdl/aws/hostname'
HOMEDIR = '/home/ubuntu'
MASTER = 'ip-172-31-28-108'

global NNodes
NNodes = None


def get_hosts():
    global NNodes
    hosts = []
    with open(HOSTFILE, 'r') as f:
        for ip in f.readlines():
            ip = ip.split()[0].strip()
            hosts.append(ip)

            if len(hosts) == NNodes:
                break
    return hosts


def get_rsync_varuna_cmd(ip):
    cmd = f'rsync -q --timeout=5 -avr --delete --exclude ".git" \
            --exclude "*.pyc" --exclude "aws/log/" {HOMEDIR}/varuna/ ubuntu@{ip}:{HOMEDIR}/varuna'
    return cmd


def get_rsync_example_cmd(ip):
    cmd = f'rsync -q --timeout=5 -avr --delete --exclude "checkpoints/*" \
            --exclude ".git" --exclude "log/*" \
            {HOMEDIR}/varuna_examples/Megatron-LM/ ubuntu@{ip}:{HOMEDIR}/varuna_examples/Megatron-LM'
    return cmd


def sync_varuna(hosts, init=False):
    processes = []
    for ip in hosts:
        if ip == MASTER:
            continue
        cmd = get_rsync_varuna_cmd(ip)
        print(cmd)
        p = subprocess.Popen(cmd, shell=True)
        processes.append(p)

    for p in processes:
        p.wait()


def sync_example(hosts):
    processes = []
    for ip in hosts:
        if ip == MASTER:
            continue
        cmd = get_rsync_example_cmd(ip)
        print(cmd)
        p = subprocess.Popen(cmd, shell=True)
        processes.append(p)

    for p in processes:
        p.wait()


if __name__ == '__main__':
    args = parse_args()

    hosts = get_hosts()
    sync_varuna(hosts, args.init)
    sync_example(hosts)
