import argparse
import logging
import socket
import os
import json
import time
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument('--trace', type=str, required=True, help='Trace file to replay')
parser.add_argument('--n', type=int, default=32, help='Number of nodes')
parser.add_argument('--hostfile', type=str, default='hostname', help='Hostfile')
parser.add_argument('--dry-run', action='store_true', help='Dry run the trace')
parser.add_argument('--replayer-log', type=str, default='log/replayer.log', help='The logfile of replayer')
parser.add_argument('--train-script', type=str)
args = parser.parse_args()


# logging.basicConfig(filename=args.replayer_log,
#                     filemode='w',
#                     format='[%(asctime)s] %(message)s',
#                     level=logging.INFO,)
# logger = logging.getLogger()

class FakeLogging:
    pass

def myprint(msg):
    print(msg, flush=True)

logger = FakeLogging()
logger.info = myprint



HOSTFILE = args.hostfile
GRACE_PERIOD = 10_000 # ms
AVAILABLE_MACHINE_FILE = '/home/ubuntu/varuna/aws/hosts/available_machines.out'
TRAIN_SCRIPT = args.train_script
MANAGER_IP = '172.31.28.108'
MANAGER_PORT = 4200


def poll_aws_instances(exclude_master=False):
    cmd = f'python /home/ubuntu/spotdl/aws/aws_poll_instances.py \
           --hostfile {HOSTFILE} --master spot-1'
    if exclude_master:
        cmd += ' --exclude-master'
    os.system(cmd)


def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))


class TraceEvent:
    def __init__(self, trace_file, n=32, dry_run=False):
        self.trace_file = trace_file
        self.n = n
        self.dry_run = dry_run

        # poll_aws_instances()
        self.read_trace(trace_file)

    def read_trace(self, trace_file):
        self.hosts = {}
        with open(HOSTFILE, 'r') as f:
            for i, line in enumerate(f.readlines()):
                if self.dry_run:
                    ip = line.strip()
                else:
                    ip = socket.gethostbyname(line.strip())
                self.hosts[i] = ip
                if len(self.hosts) == self.n:
                    break

        # map from node id to host
        self.trace = []
        remain_nodes = list(self.hosts.keys())
        node_map = {}
        with open(trace_file, 'r') as f:
            for line in f:
                # self-defined comment for trace file
                if line.startswith('#'):
                    continue
                event = json.loads(line)
                nodes = []
                if event[1] == 'add':
                    for node_id in event[2]['nodes']:
                        host_id = remain_nodes.pop(0)
                        node_map[node_id] = host_id
                        nodes.append(self.hosts[host_id])
                else:
                    for node_id in event[2]['nodes']:
                        host_id = node_map[node_id]
                        nodes.append(self.hosts[host_id])
                        remain_nodes.append(host_id)
                event[2]['nodes'] = nodes
                self.trace.append(event)

    def get_machine_list(self, event):
        if event[1] == 'add':
            self.cur_machine_list.extend(event[2]['nodes'])
        elif event[1] == 'remove':
            for node in event[2]['nodes']:
                self.cur_machine_list.remove(node)
        logger.info(f'>>> [{self.timer()/1000:.3f}]      node to be {event[1]}: {event[2]["nodes"]}')
        return self.cur_machine_list

    def sleep(self, sec):
        if self.dry_run:
            return
        time.sleep(sec)

    def timer(self, init=False):
        if init:
            self.start_time = time.time()
        cur_time_stamp = (time.time() - self.start_time) * 1000
        return cur_time_stamp

    def write_machine_list(self, machine_list):
        with open(AVAILABLE_MACHINE_FILE, 'w') as of:
            for m in machine_list:
                of.write(f'{m}\n')

    def init_start_training(self):
        cmd = f'bash {TRAIN_SCRIPT}'
        self.root_process = subprocess.Popen(cmd, shell=True)

    def replay(self):
        self.cur_machine_list = []
        self.timer(init=True)
        logger.info(f'Begin to replay trace {self.trace_file}')
        for event in self.trace:
            tstamp, operation, _ = event

            logger.info(f'>>> [{self.timer()/1000:.3f}] next_event: {operation} at {tstamp}')
            if operation == 'remove':
                cur_time_stamp = self.timer()
                if cur_time_stamp < tstamp - GRACE_PERIOD:
                    self.sleep((tstamp - cur_time_stamp) / 1000)
            else:
                cur_time_stamp = self.timer()
                if cur_time_stamp < tstamp:
                    self.sleep((tstamp - cur_time_stamp) / 1000)

            if operation == 'no-op':
                logger.info(f'>>> [{self.timer()/1000:.3f}] nnodes: {len(self.cur_machine_list)}, no morph')
            else:
                # update machine list
                machine_list = self.get_machine_list(event)
                self.write_machine_list(machine_list)
                message = ''
                if not self.dry_run:
                    if tstamp == 0:
                        # start training
                        self.init_start_training()
                    else:
                        if operation == 'add':
                            message = 'morph'
                        else:
                            message = f'preempt {self.timer()/1000}'
                        client(MANAGER_IP, MANAGER_PORT, message)
                logger.info(f'>>> [{self.timer()/1000:.3f}] nnodes: {len(self.cur_machine_list)}, message: {message}')
                logger.info(f'               remain nodes: {self.cur_machine_list}')

        # final, clean all machines
        final_event = self.trace[-1]
        final_timestamp = final_event[0] + final_event[2]['duration']
        self.sleep((final_timestamp - self.timer()) / 1000)
        self.write_machine_list('')

        # kill all
        message = f'preempt {self.timer()/1000}'
        if not self.dry_run:
            client(MANAGER_IP, MANAGER_PORT, message)
        logger.info(f'>>> [{self.timer()/1000:.3f}] nnodes: {len(self.cur_machine_list)}, message: {message}')
        logger.info(f'          Finally kill all')
        os.system('bash kill_all.sh')


if __name__ == "__main__":
    trace_events = TraceEvent(args.trace, args.n, args.dry_run)
    trace_events.replay()
