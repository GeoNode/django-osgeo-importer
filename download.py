import sys, os
from boto.s3.connection import S3Connection

conn = S3Connection('','')

bucket = conn.get_bucket('mapstory-data')
for key in bucket.list():
    try:
        if not os.path.exists(os.path.split(key.key)[0]):
            os.mkdir(os.path.split(key.key)[0])
        res = key.get_contents_to_filename(key.key)
    except:
        print key.name+":"+"FAILED"
        print sys.exc_info()
