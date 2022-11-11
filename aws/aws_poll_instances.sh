
HOSTFILE="/home/ubuntu/varuna/aws/hosts/hostname"

/opt/conda/envs/varuna/bin/python /home/ubuntu/spotdl/aws/aws_poll_instances.py \
    --hostfile ${HOSTFILE} --master spot-1
