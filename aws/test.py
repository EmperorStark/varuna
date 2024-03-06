import os
import boto3
import io
import torch


def list_folders(s3_client, bucket_name):
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix='', Delimiter='/')
    for content in response.get('CommonPrefixes', []):
        yield content.get('Prefix')

def list_files(dirname):
    if dirname.startswith('s3://'):
        s3_client = boto3.client('s3')
        bucket_name, dirname = dirname[5:].split('/', 1)
        if dirname[-1] != '/':
            dirname += '/'
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=dirname, Delimiter='/')
        dirs = []
        for content in response.get('Contents', []):
            key = content.get('Key')
            dirs.append(key[len(dirname):])
        return dirs
    else:
        return os.listdir(dirname)

def read_file(filename):
    if filename.startswith('s3://'):
        s3_client = boto3.client('s3')
        bucket_name, filename = filename[5:].split('/', 1)
        obj = s3_client.get_object(Bucket=bucket_name, Key=filename)
        return obj['Body'].read().decode()
    else:
        return open(filename, 'rb')

model = torch.nn.Linear(100, 100)
model.cuda()

s3 = boto3.client('s3')
# with io.BytesIO() as f:
#     torch.save(model, f)
#     s3.put_object(Bucket='spot-checkpoints', Key='gpt/varuna_ckpt_0', Body=f.getvalue())

# with io.BytesIO() as f:
#     s3.download_fileobj(Bucket='spot-checkpoints', Key='gpt/varuna_ckpt_0', Fileobj=f)
#     f.seek(0)
#     model = torch.load(f)
#     print(model)

# with io.BytesIO() as f:
#     f.write(str(5).encode())
#     s3.put_object(Bucket='spot-checkpoints', Key='gpt/markers/finish_0.txt', Body=f.getvalue())

# with io.BytesIO() as f:
#     f.write(str(6).encode())
#     s3.put_object(Bucket='spot-checkpoints', Key='gpt/markers/finish_1.txt', Body=f.getvalue())

# response = s3.list_objects_v2(Bucket='spot-checkpoints', Prefix='gpt/markers/', Delimiter='/')
dirs = list_files('s3://spot-checkpoints/gpt/markers')
print(dirs)


complete = 0
for m in dirs:
    # with open(, "r") as f:
    file = os.path.join('s3://spot-checkpoints/gpt/markers', m)
    complete += int(read_file(file))
    # with read_file(file) as f:
    #     complete += int(f.read())

print(complete)
