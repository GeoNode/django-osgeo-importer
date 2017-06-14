import os
import subprocess


def get_version(version=None):
    "Returns a version number with commit id if the git repo is present"
    if version is None:
        from osgeo_importer import __version__ as version
    version = '.'.join(str(x) for x in version)
    commit = None
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _commit = subprocess.Popen(
        'git rev-parse --short HEAD',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
        universal_newlines=True
    )
    commit = _commit.communicate()[0].partition('\n')[0]
    if commit:
        version = "%s.%s" % (version, commit)
    return version
