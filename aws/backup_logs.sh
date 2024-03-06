DIRNAME=$1
# DIRNAME=log_vgg19/trace_hl_15_25_logs

mkdir -p $DIRNAME

FROMDIR="/home/ubuntu/varuna_examples/Megatron-LM"
# FROMDIR="/home/ubuntu/varuna_examples/DeepLearningExamples/PyTorch/LanguageModeling/BERT"
# FROMDIR="/home/ubuntu/varuna_examples/ResNet"

cp log/train_test.log $DIRNAME/replayer.log
cp -r $FROMDIR/ssh_logs $DIRNAME/
cp $FROMDIR/varuna_catch.err $DIRNAME/
cp $FROMDIR/varuna_catch.out $DIRNAME/
cp $FROMDIR/varuna_morph.err $DIRNAME/
cp $FROMDIR/varuna_morph.out $DIRNAME/
