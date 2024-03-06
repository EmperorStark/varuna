import boto3, os

def list_files(dirname):
    if dirname.startswith('s3://'):
        s3_client = boto3.client('s3')
        bucket_name, dirname = dirname[5:].split('/', 1)
        if dirname[-1] != '/':
            dirname += '/'
        
        paginator = s3_client.get_paginator('list_objects_v2')
        response = paginator.paginate(Bucket=bucket_name, Prefix=dirname)
        dirs = []
        for page in response:
            for content in page.get('Contents', []):
                key = content.get('Key')
                # print(key)
                dirs.append(key[len(dirname):])
                
        # response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=dirname, Delimiter='/', MaxKeys=2000)
        # dirs = []
        # for content in response.get('Contents', []):
        #     key = content.get('Key')
        #     dirs.append(key[len(dirname):])
        return dirs
    else:
        return os.listdir(dirname)

sr = 's3://spot-checkpoints/resnet/varuna_ckpt_174'
print(len(list_files(sr)))


for k in list_files(sr):
    if k.startswith('opt-state-9_'):
        print(k)
