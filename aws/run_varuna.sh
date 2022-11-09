export PYTHONPATH=/home/ubuntu/varuna:$PYTHONPATH

mkdir -p log

TRAIN_SCRIPT='/home/ubuntu/varuna_examples/Megatron-LM/pretrain_gpt2_varuna.sh'

nnode=$1
tracefile=$2
HOSTFILE="/home/ubuntu/spotdl/aws/hostname"
logtag=${3:-"test"}
DRY_RUN="--dry-run"


logfile="train_${logtag}.log"
replayer_logfile="replayer_${logtag}.log"

cmd="python spot_client.py --trace ${tracefile} \
    --n ${nnode} --hostfile ${HOSTFILE} ${DRY_RUN} \
    --replayer-log log/${replayer_logfile} \
    --train-script ${TRAIN_SCRIPT}
    2>&1 | tee log/${logfile} \
"

echo ${cmd}
eval ${cmd}
