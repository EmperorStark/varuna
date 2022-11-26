RET=$( nvidia-smi | grep python )
if [[ -n ${RET} ]]; then
    nvidia-smi | grep python | awk "{ print \$5 }" | xargs -n1 sudo kill -9
fi
sudo pkill -f varuna.launcher
