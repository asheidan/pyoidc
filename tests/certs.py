import os

RSAPUB = "../oc3/certs/mycert.key"
certs_dir = "../oc3/certs"
certs_dir_path = os.path.join(os.path.dirname(__file__),certs_dir)
path = os.path.abspath(os.path.join(os.path.dirname(__file__), RSAPUB))
uri = "file://%s" % path

def path(certificate_name):
    return os.path.join(certs_dir_path,certificate_name)

def uri(certificate_name):
    return "file://%s" % path(certificate_name)
