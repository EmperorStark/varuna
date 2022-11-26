import os
import argparse
import subprocess
import socket

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=1)
    parser.add_argument('--hostfile', type=str, default='hostname', help='Hostfile')
    parser.add_argument('--init', action='store_true')
    parser.add_argument('--update-env', action='store_true')
    args = parser.parse_args()
    global NNodes, HOSTFILE
    NNodes = args.n
    HOSTFILE = args.hostfile
    return args


HOMEDIR = '/home/ubuntu'
MASTER = ['ip-172-31-28-108', '172.31.28.108']

global NNodes, HOSTFILE
NNodes = None
HOSTFILE = '/home/ubuntu/varuna/aws/hosts/hostname'


def poll_aws_instances(exclude_master=False):
    cmd = f'/opt/conda/envs/varuna/bin/python /home/ubuntu/spotdl/aws/aws_poll_instances.py \
           --hostfile {HOSTFILE} --master spot-1'
    if exclude_master:
        cmd += ' --exclude-master'
    os.system(cmd)


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

def get_rsync_example_bert_cmd(ip):
    cmd = f'rsync -q --timeout=5 -avr --delete --exclude "checkpoints/*" \
            --exclude ".git" --exclude "log/*" \
            {HOMEDIR}/varuna_examples/DeepLearningExamples/ ubuntu@{ip}:{HOMEDIR}/varuna_examples/DeepLearningExamples'
    return cmd


def run_cmd(cmd, hosts):
    processes = []
    for ip in hosts:
        if ip in MASTER:
            continue
        print(cmd.format(ip))
        p = subprocess.Popen(cmd.format(ip), shell=True)
        processes.append(p)

    for p in processes:
        p.wait()


def update_instance_env(hosts):
    # apex
    cmd = 'scp /home/ubuntu/varuna_apex/apex/amp/_process_optimizer.py ubuntu@{}:/home/ubuntu/varuna_apex/apex/amp/_process_optimizer.py'
    run_cmd(cmd, hosts)

    cmd = 'ssh ubuntu@{} "sudo /opt/conda/envs/varuna/bin/pip install -v --disable-pip-version-check --no-cache-dir --global-option="--cpp_ext" --global-option="--cuda_ext" /home/ubuntu/varuna_apex/"'
    run_cmd(cmd, hosts)

    cmd = 'ssh ubuntu@{} "sudo /opt/conda/envs/varuna/bin/pip install six pybind11 regex numpy tqdm boto3 requests ipdb h5py nltk"'
    run_cmd(cmd, hosts)


def sync_varuna(hosts, init=False):
    processes = []
    for ip in hosts:
        if ip in MASTER:
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
        if ip in MASTER:
            continue
        cmd = get_rsync_example_cmd(ip)
        print(cmd)
        p = subprocess.Popen(cmd, shell=True)
        processes.append(p)

        cmd = get_rsync_example_bert_cmd(ip)
        print(cmd)
        p = subprocess.Popen(cmd, shell=True)
        processes.append(p)

    for p in processes:
        p.wait()


if __name__ == '__main__':
    args = parse_args()

    # poll_aws_instances()

    hosts = get_hosts()
    if args.update_env:
        update_instance_env(hosts)

    sync_varuna(hosts, args.init)
    sync_example(hosts)
