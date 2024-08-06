import os
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_settings.settings")

import django

django.setup()
# Set the Graphviz executable path explicitly by modifying PATH
os.environ["PATH"] += os.pathsep + "C:/Program Files/Graphviz/bin"

# Generate the model graph
call_command("graph_models", "-a", "-o", "models.png", "--pydot")
