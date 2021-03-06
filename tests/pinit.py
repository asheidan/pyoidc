import sys
from oic.utils.keyio import KeyBundle
from oic.utils.keyio import KeyJar

__author__ = 'rohe0002'

import StringIO
import urllib

from oic.oic.message import OpenIDSchema
from oic.utils.sdb import SessionDB
from oic.oic.provider import Provider
from oic.oauth2.provider import AuthnFailure
from oic.utils import http_util

CLIENT_CONFIG = {
    "client_id": "number5",
    "ca_certs": "/usr/local/etc/oic/ca_certs.txt",
    "client_timeout":0
}

CONSUMER_CONFIG = {
    "authz_page": "/authz",
    #"password": args.passwd,
    "scope": ["openid"],
    "response_type": ["code"],
    #"expire_in": 600,
    "user_info": {
        "claims": {
            "name": None,
            "email": None,
            "nickname": None
        }
    },
    "request_method": "param"
}

SERVER_INFO ={
    "version":"3.0",
    "issuer":"https://connect-op.heroku.com",
    "authorization_endpoint":"http://localhost:8088/authorization",
    "token_endpoint":"http://localhost:8088/token",
    #"userinfo_endpoint":"http://localhost:8088/user_info",
    #"check_id_endpoint":"http://localhost:8088/id_token",
    #"registration_endpoint":"https://connect-op.heroku.com/connect/client",
    #"scopes_supported":["openid","profile","email","address","PPID"],
    "flows_supported":["code","token","code token"],
    #"identifiers_supported":["public","ppid"],
    #"x509_url":"https://connect-op.heroku.com/cert.pem"
}

BASE_ENVIRON = {'SERVER_PROTOCOL': 'HTTP/1.1',
                'REQUEST_METHOD': 'GET',
                'QUERY_STRING': '',
                'HTTP_CONNECTION': 'keep-alive',
                'REMOTE_ADDR': '127.0.0.1',
                'wsgi.url_scheme': 'http',
                'SERVER_PORT': '8087',
                'PATH_INFO': '/register',
                'HTTP_HOST': 'localhost:8087',
                'HTTP_ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'HTTP_ACCEPT_LANGUAGE': 'sv-se',
                'CONTENT_TYPE': 'text/plain',
                'REMOTE_HOST': '1.0.0.127.in-addr.arpa',
                'HTTP_ACCEPT_ENCODING': 'gzip, deflate',
                'COMMAND_MODE': 'unix2003'}

CLIENT_SECRET = "abcdefghijklmnop"
CLIENT_ID = "client_1"

KC_HMAC = KeyBundle({"hmac": CLIENT_SECRET}, usage=["ver", "sig"])
KC_HMAC2 = KeyBundle({"hmac": "drickyoughurt"}, usage=["ver", "sig"])
KC_RSA = KeyBundle(source="file://../oc3/certs/mycert.key", type="rsa",
                  usage=["sig", "ver"])
KEYJAR = KeyJar()
KEYJAR[CLIENT_ID] = [KC_HMAC, KC_RSA]
KEYJAR["number5"] = [KC_HMAC2, KC_RSA]
KEYJAR[""] = KC_RSA

#SIGN_KEY = {"hmac": ["abcdefghijklmnop"]}

CDB = {
    "number5": {
        "password": "hemligt",
        "client_secret": "drickyoughurt",
        #"jwk_key": CONSUMER_CONFIG["key"],
        "redirect_uris": [("http://localhost:8087/authz", None)]
    },
    "a1b2c3":{
        "redirect_uris": [("http://localhost:8087/authz", None)]
    },
    "client0":{
        "redirect_uris": [("http://www.example.org/authz", None)]
    },
    CLIENT_ID: {
        "client_secret": CLIENT_SECRET,
        }

}

#noinspection PyUnusedLocal
def start_response(status, headers=None):
    return

#noinspection PyUnusedLocal
def do_authentication(environ, start_response, bsid, cookie):
    resp = http_util.Response("<form>%s</form>" % bsid)
    return resp(environ, start_response)

#noinspection PyUnusedLocal
def do_authorization(user, session=None):
    if user == "user":
        return "ALL"
    else:
        raise Exception("No Authorization defined")

def verify_username_and_password(dic):
    try:
        user = dic["login"][0]
    except KeyError:
        raise AuthnFailure("Authentication failed")

    if user == "user":
        return True, user
    elif user == "hannibal":
        raise AuthnFailure("Not allowed to use this service (%s)" % user)
    else:
        if user:
            return False, user
        else:
            raise AuthnFailure("Missing user name")


#noinspection PyUnusedLocal
def verify_client(environ, areq, cdb):
    identity = areq["client_id"]
    secret = areq["client_secret"]
    if identity:
        if identity == CLIENT_ID and secret == CLIENT_SECRET:
            return True
        else:
            return False

    return False

def create_return_form_env(user, password, sid):
    _dict = {
        "login": user,
        "password": password,
        "sid": sid
    }

    environ = BASE_ENVIRON.copy()
    environ["REQUEST_METHOD"] = "POST"

    str = urllib.urlencode(_dict)
    environ["CONTENT_LENGTH"] = len(str)

    fil = StringIO.StringIO(buf=str)
    environ["wsgi.input"] = fil

    return environ

#noinspection PyUnusedLocal
def user_info(oicsrv, userdb, user_id, client_id, user_info):
    identity = userdb[user_id]
    result = {}
    for key, restr in user_info["claims"].items():
        try:
            result[key] = identity[key]
        except KeyError:
            if restr == {"essential": True}:
                raise Exception("Missing property '%s'" % key)

    return OpenIDSchema(**result)

FUNCTIONS = {
    "authenticate": do_authentication,
    "authorize": do_authorization,
    "verify_user": verify_username_and_password,
    "verify_client": verify_client,
    "userinfo": user_info,
    }

USERDB = {
    "user":{
        "name": "Hans Granberg",
        "nickname": "Hasse",
        "email": "hans@example.org",
        "verified": False,
        "user_id": "user"
    }
}

URLMAP = {"client1": ["https://example.com/authz"]}

class LOG():
    def info(self, txt):
        print >> sys.stdout, "INFO: %s" % txt

    def error(self, txt):
        print >> sys.stdout, "ERROR: %s" % txt

    def debug(self, txt):
        print >> sys.stdout, "DEBUG: %s" % txt

provider_init = Provider("pyoicserv", SessionDB(), CDB, FUNCTIONS,
                         userdb=USERDB, urlmap=URLMAP, keyjar=KEYJAR)
