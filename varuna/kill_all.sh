ip_file=$1
machines=($(cat $ip_file))
nservers=${#machines[@]}

i=0
while [ $i -lt $nservers ]
do
    echo $i ${machines[i]}
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${machines[i]} "nvidia-smi | grep 'python' | awk '{ print \$5 }' | xargs -n1 sudo kill -9" &
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ${machines[i]} "sudo pkill -f varuna.launcher" &
    i=$(($i+1))
done

sleep 3
