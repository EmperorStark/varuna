#!/bin/bash

nnode=${1:-0}
ip_file=${2:-"/home/ubuntu/varuna/aws/hosts/hostname"}
machines=$(cat $ip_file)

for node in $machines
do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${node} "sudo pkill -f varuna.launcher" &
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${node} "sudo pkill -f varuna.catch_all" &
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${node} "sudo pkill -f varuna.morph_server" &
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${node} "sudo pkill -f /opt/conda/envs/varuna/bin/python" &
    nnode=$((nnode-1))
    if [ $nnode -eq 0 ]; then
        break
    fi
done
