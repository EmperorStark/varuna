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


HOSTFILE = '/home/ubuntu/SpotDL-DeesSpeed/aws/hostname'
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


# def get_rsync_example_cmd(ip):
#     cmd = f'rsync -q --timeout=5 -avr --delete --exclude "megatron/Megatron-LM-v1.1.5-3D_parallelism/checkpoints/*" \
#             --exclude ".git" --exclude "megatron/Megatron-LM-v1.1.5-3D_parallelism/log/*" \
#             --exclude "spotdl/checkpoints/*" --exclude "spotdl/log/*" \
#             {HOMEDIR}/SpotDL-DeesSpeed/ ubuntu@{ip}:{HOMEDIR}/SpotDL-DeesSpeed'
#     return cmd


# def sync_dataset(ip):
#     cmd = f'ssh ubuntu@{ip} "mkdir -p {HOMEDIR}/datas/cifar100-data"'
#     p = subprocess.Popen(cmd, shell=True)
#     p.wait()

#     cmd = f'rsync -q --timeout=5 -avr --delete {HOMEDIR}/datas/cifar100-data ubuntu@{ip}:{HOMEDIR}/datas/'
#     print(cmd)
#     p = subprocess.Popen(cmd, shell=True)
#     p.wait()


# def sync_code(ip_lists):
#     processes = []
#     for ip in ip_lists:
#         if ip == MASTER or ip == '.'.join(MASTER.split('-')[1:]):
#             continue

#         # sync_dataset(ip)

#         cmd = get_rsync_varuna_cmd(ip)
#         print(cmd)
#         p = subprocess.Popen(cmd, shell=True)
#         processes.append(p)

#         cmd = get_rsync_example_cmd(ip)
#         print(cmd)
#         p = subprocess.Popen(cmd, shell=True)
#         processes.append(p)

#     for p in processes:
#         p.wait()


def sync_varuna(hosts, init=False):
    processes = []
    for ip in hosts:
        if ip == MASTER:
            continue
        cmd = get_rsync_varuna_cmd(ip)
        print(cmd)
        p = subprocess.Popen(cmd, shell=True)
        if init:
            p.wait()

            cmd = f'ssh ubuntu@{ip} "ls {HOMEDIR}/spotdl/build "'
            p = subprocess.Popen(cmd, shell=True)
            p.wait()
            if p.returncode != 0:
                cmd = f'ssh ubuntu@{ip} "DS_BUILD_CPU_ADAM=1 DS_BUILD_UTILS=1 /opt/conda/envs/pytorch/bin/pip install -e {HOMEDIR}/spotdl/ "'
                print(cmd)
                p = subprocess.Popen(cmd, shell=True)

        processes.append(p)

    for p in processes:
        p.wait()


# def sync_example(hosts):
#     processes = []
#     for ip in hosts:
#         if ip == MASTER:
#             continue
#         cmd = get_rsync_example_cmd(ip)
#         print(cmd)
#         p = subprocess.Popen(cmd, shell=True)
#         processes.append(p)

#     for p in processes:
#         p.wait()


if __name__ == '__main__':
    args = parse_args()

    hosts = get_hosts()
    sync_varuna(hosts, args.init)
    # sync_example(hosts)
