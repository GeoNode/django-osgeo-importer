import sys, os
from boto.s3.connection import S3Connection

conn = S3Connection(os.environ['AWS_ACCESS_KEY_ID'],os.environ['AWS_SECRET_ACCESS_KEY'])
bucket = conn.get_bucket('mapstory-data')
for key in bucket.list():
    try:
        if not os.path.exists(os.path.split(key.key)[0]):
            os.mkdir(os.path.split(key.key)[0])
        key.get_contents_to_filename(key.key)
        file = os.path.abspath(key.key) 
        print file
    except:
        print key.name+":"+"FAILED"
        print sys.exc_info()
