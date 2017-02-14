import os

__version__ = (0, 1, 1, 'alpha', 3)

os.environ.setdefault('PGCLIENTENCODING', 'UTF-8')
os.environ.setdefault('SHAPE_ENCODING', 'UTF-8')
os.environ.setdefault('PG_USE_COPY', 'no')
