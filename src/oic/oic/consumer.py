#!/usr/bin/env python
import logging

__author__ = 'rohe0002'

import time
import os.path
#import httplib2

from hashlib import md5

from oic.utils import http_util

#from oic.oic.base import Client
#from oic.oic.base import ENDPOINTS
from oic.oic import Client
from oic.oic import ENDPOINTS


from oic.oic.message import Claims
from oic.oic.message import AuthorizationRequest
from oic.oic.message import AuthorizationResponse
from oic.oic.message import UserInfoClaim
from oic.oic.message import AccessTokenResponse

from oic.oauth2 import Grant
from oic.oauth2 import rndstr

from oic.oauth2.consumer import TokenError
from oic.oauth2.consumer import AuthzError
from oic.oauth2.consumer import UnknownState


logger = logging.getLogger(__name__)

def stateID(url, seed):
    """The hash of the time + server path + a seed makes an unique
    SID for each session.

    :param url: The base URL for this site
    :return: The hex version of the digest
    """
    ident = md5()
    ident.update(repr(time.time()))
    ident.update(url)
    ident.update(seed)
    return ident.hexdigest()

def factory(kaka, sdb, config):
    """
    Return the right Consumer instance dependent on what's in the cookie

    :param kaka: The cookie
    :param sdb: The session database
    :param config: The common Consumer configuration
    :return: Consumer instance or None
    """
    part = http_util.cookie_parts(config["name"], kaka)
    if part is None:
        return None

    cons = Consumer(sdb, config=config)
    cons.restore(part[0])
    http_util.parse_cookie(config["name"], cons.seed, kaka)
    return cons

def build_userinfo_claims(claims, sformat="signed", locale="us-en"):
    """
    config example:
    "userinfo_claims":{
        "format": "signed",
        "locale": "sv-se",
        "claims": {
             "name": {"essential": true},
             "nickname": null,
             "email": {"essential": true},
             "email_verified": {"essential": true},
             "picture": null
        }
    }
    """
    claim = Claims(**claims)

    return UserInfoClaim(claims=claim, format=sformat, locale=locale)


#def construct_openid_request(arq, keys, algorithm=DEF_SIGN_ALG, iss=None,
#                             aud=None):
#    """
#    Construct the specification of what I want returned.
#    The request will be signed
#    """
#
#    # Should be configurable !!
#    claim = Claims(name={"essential": true}, nickname=None,
#                 email={"essential": true},
#                 email_verified={"essential": true},
#                 picture=None)
#
#    uic = UserInfoClaim(claim, format="signed", locale="us-en")
#
#    id_token = IDTokenClaim(max_age=86400)
#    ava = {}
#    for attr in ["response_type", "scope", "prompt"]:
#        _tmp = arq[attr]
#        if _tmp:
#            ava[attr] = " ".join(_tmp)
#        else:
#            ava[attr] = _tmp
#
#    oir = OpenIDRequest(ava["response_type"], arq.client_id, arq.redirect_uri,
#                        ava["scope"], arq.state, user_info=uic,
#                        prompt=ava["prompt"], id_token=id_token, iss=iss,
#                        aud=aud)
#
#    return oir.get_jwt(key=keys, algorithm=algorithm)

def clean_response(aresp):
    """
    Creates a new instance with only the standard attributes

    :param aresp: The original AccessTokenResponse
    :return: An AccessTokenResponse instance
    """
    atr = AccessTokenResponse()
    for prop in atr.parameters():
        try:
            atr[prop] = aresp[prop]
        except KeyError:
            pass

    return atr



IGNORE = ["request2endpoint", "response2error", "grant_class", "token_class"]

CONSUMER_PREF_ARGS =[
    "token_endpoint_auth_type",
    "subject_type",
    "require_signed_request_object",
    "userinfo_signed_response_algs",
    "userinfo_encrypted_response_alg",
    "userinfo_encrypted_response_enc",
    "userinfo_encrypted_response_int",
    "id_token_signed_response_algs",
    "id_token_encrypted_response_alg",
    "id_token_encrypted_response_enc",
    "id_token_encrypted_response_int",
    "default_max_age",
    "require_auth_time",
    "default_acr"
]

class Consumer(Client):
    """ An OpenID Connect consumer implementation

    """
    #noinspection PyUnusedLocal
    def __init__(self, session_db, config, client_config=None,
                 server_info=None, debug=False, client_prefs=None):
        """ Initializes a Consumer instance.

        :param session_db: Where info are kept about sessions
        :param config: Configuration of the consumer
        :param client_config: Client configuration
        :param server_info: Information about the server
        :param client_prefs: Run time preferences, which are chosen
            depends on what the server can do.
        """
        if client_config is None:
            client_config = {}

        Client.__init__(self, **client_config)

        self.config = config
        if config:
            try:
                self.debug = config["debug"]
            except KeyError:
                self.debug = 0

        if server_info:
            for endpoint in ENDPOINTS:
                try:
                    setattr(self, endpoint, server_info[endpoint])
                except KeyError:
                    setattr(self, endpoint, "")


        self.sdb = session_db
        self.debug = debug
        self.seed = ""
        self.nonce = ""
        self.request_filename=""
        self.user_info = None
        self.registration_expires_at = 0
        self.secret_type = "Bearer"

    def update(self, sid):
        """ Updates the instance variables from something stored in the
        session database. Will not overwrite something that's already there.
        Except for the grant dictionary !!

        :param sid: Session identifier
        """
        for key, val in self.sdb[sid].items():
            _val = getattr(self, key)
            if not _val and val:
                setattr(self, key, val)
            elif key == "grant" and val:
                val.update(_val)
                setattr(self, key, val)

    def restore(self, sid):
        """ Restores the instance variables from something stored in the
        session database.

        :param sid: Session identifier
        """
        for key, val in self.sdb[sid].items():
            setattr(self, key, val)

    def dictionary(self):
        return dict([(k, v) for k, v in
                     self.__dict__.items() if k not in IGNORE])

    def _backup(self, sid):
        """ Stores instance variable values in the session store under a
        session identifier.

        :param sid: Session identifier
        """
        self.sdb[sid] = self.dictionary()

    #noinspection PyUnusedLocal,PyArgumentEqualDefault
    def begin(self, environ, start_response, scope="",
              response_type="", use_nonce=False):
        """ Begin the OAuth2 flow

        :param environ: The WSGI environment
        :param start_response: The function to start the response process
        :param scope: Defines which user info claims is wanted
        :param response_type: Controls the parameters returned in the
            response from the Authorization Endpoint
        :param use_nonce: If not implicit flow nonce is optional.
            This defines if it should be used anyway.
        :return: A URL to which the user should be redirected
        """
        _log_info = logger.info

        if self.debug:
            _log_info("- begin -")

        _path = http_util.geturl(environ, False, False)
        _page = self.config["authz_page"]
        if not _path.endswith("/"):
            if _page.startswith("/"):
                self.redirect_uris = [_path + _page]
            else:
                self.redirect_uris = ["%s/%s" % (_path, _page)]
        else:
            if _page.startswith("/"):
                self.redirect_uris = [_path + _page[1:]]
            else:
                self.redirect_uris = ["%s/%s" % (_path, _page)]

        # Put myself in the dictionary of sessions, keyed on session-id
        if not self.seed:
            self.seed = rndstr()

        if not scope:
            scope = self.config["scope"]
        if not response_type:
            response_type = self.config["response_type"]

        sid = stateID(_path, self.seed)
        self.state = sid
        self.grant[sid] = Grant(seed=self.seed)

        self._backup(sid)
        self.sdb["seed:%s" % self.seed] = sid

        # Store the request and the redirect uri used
        self._request = http_util.geturl(environ)

        args = {
            "client_id": self.client_id,
            "state":sid,
            "response_type":response_type,
            "scope": scope,
            }

    # nonce is REQUIRED in implicit flow,
        # OPTIONAL on code flow.
        if "token" in response_type or use_nonce:
            self.nonce = rndstr(12)
            args["nonce"] = self.nonce

        if "max_age" in self.config:
            args["idtoken_claims"] = {"max_age": self.config["max_age"]}

        if "user_info" in self.config:
            args["userinfo_claims"] = self.config["user_info"]

        if "request_method" in self.config:
            areq = self.construct_AuthorizationRequest(request_args=args,
                                                 extra_args=None)

            if self.config["request_method"] == "file":
                id_request = areq["request"]
                del areq["request"]
                _filedir = self.config["temp_dir"]
                _webpath = self.config["temp_path"]
                _name = rndstr(10)
                filename = os.path.join(_filedir, _name)
                while os.path.exists(filename):
                    _name = rndstr(10)
                    filename = os.path.join(_filedir, _name)
                fid = open(filename, mode="w")
                fid.write(id_request)
                fid.close()
                _webname = "%s%s%s" % (_path,_webpath,_name)
                areq["request_uri"] = _webname
                self.request_uri = _webname
                self._backup(sid)
        else:
            if "userinfo_claims" in args: # can only be carried in an IDRequest
                raise Exception("Need a request method")

            areq = self.construct_AuthorizationRequest(AuthorizationRequest,
                                                       request_args=args)

        location = areq.request(self.authorization_endpoint)

        if self.debug:
            _log_info("Redirecting to: %s" % location)

        return location

    #noinspection PyUnusedLocal
    def parse_authz(self, environ, start_response):
        """
        This is where we get redirect back to after authorization at the
        authorization server has happened.

        :param environ: The WSGI environment
        :param start_response: The function to start the response process
        :return: A AccessTokenResponse instance
        """

        _log_info = logger.info
        if self.debug:
            _log_info("- authorization -")
            _log_info("environ: %s" % environ)

        if environ.get("REQUEST_METHOD") == "GET":
            _query = environ.get("QUERY_STRING")
#        elif environ.get("REQUEST_METHOD") == "POST":
#            _query = http_util.get_post(environ)
        else:
            resp = http_util.BadRequest("Unsupported method")
            return resp(environ, start_response)

        _log_info("response: %s" % _query)
        
        _path = http_util.geturl(environ, False, False)

        if "code" in self.config["response_type"]:
            # Might be an error response
            _log_info("Expect Authorization Response")
            aresp = self.parse_response(AuthorizationResponse,
                                        info=_query,
                                        sformat="urlencoded",
                                        keyjar=self.keyjar)
            if aresp.type() == "ErrorResponse":
                _log_info("ErrorResponse: %s" % aresp)
                raise AuthzError(aresp.error)

            _log_info("Aresp: %s" % aresp)

            _state = aresp["state"]
            try:
                self.update(_state)
            except KeyError:
                raise UnknownState(_state)

            self.redirect_uris = [self.sdb[_state]["redirect_uris"]]

            # May have token and id_token information too
            if "access_token" in aresp:
                atr = clean_response(aresp)
                self.access_token = atr
                # update the grant object
                self.get_grant(state=_state).add_token(atr)
            else:
                atr = None

            self._backup(_state)

            try:
                idt = aresp["id_token"]
            except KeyError:
                idt = None

            return aresp, atr, idt
        else: # implicit flow
            _log_info("Expect Access Token Response")
            atr = self.parse_response(AccessTokenResponse, info=_query,
                                      sformat="urlencoded",
                                      keyjar=self.keyjar)
            if atr.type() == "ErrorResponse":
                raise TokenError(atr["error"])

            idt = None
            return None, atr, idt

    def complete(self):
        """
        Do the access token request, the last step in a code flow.
        If Implicit flow was used then this method is never used.
        """
        args = {"redirect_uri": self.redirect_uris[0]}
        if "password" in self.config and self.config["password"]:
            logger.info("basic auth")
            http_args = {"password":self.config["password"]}
        elif self.client_secret:
            logger.info("request_body auth")
            http_args = {}
            args.update({"client_secret":self.client_secret,
                         "client_id": self.client_id,
                         "secret_type": self.secret_type})
        else:
            raise Exception("Nothing to authenticate with")

        resp = self.do_access_token_request(state=self.state,
                                            request_args=args,
                                            http_args=http_args)

        logger.info("Access Token Response: %s" % resp)

        if resp.type() == "ErrorResponse":
            raise TokenError(resp.error)

        #self._backup(self.sdb["seed:%s" % _cli.seed])
        self._backup(self.state)

        return resp

    def refresh_token(self):
        pass
    
    #noinspection PyUnusedLocal
    def get_user_info(self):
        uinfo = self.do_user_info_request(state=self.state, schema="openid")

        if uinfo.type() == "ErrorResponse":
            raise TokenError(uinfo.error)

        self.user_info = uinfo
        self._backup(self.state)

        return uinfo

    def refresh_session(self):
        pass

    def check_session(self):
        pass

    def end_session(self):
        pass

