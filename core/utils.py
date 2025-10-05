import os
import sys
import pathlib
import django

def init_django():
    BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lighthouse.settings")
    django.setup()
