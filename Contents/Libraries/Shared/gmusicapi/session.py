#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sessions handle the details of authentication and transporting requests.
"""

import requests

from gmusicapi.exceptions import (
    AlreadyLoggedIn, NotLoggedIn, CallFailure
)
from gmusicapi.protocol.shared import ClientLogin
from gmusicapi.protocol import webclient
from gmusicapi.utils import utils

log = utils.DynamicClientLogger(__name__)


class _Base(object):
    def __init__(self):
        self._rsession = requests.Session()
        self.is_authenticated = False

    def _send_with_auth(self, req_kwargs, desired_auth, rsession):
        raise NotImplementedError

    def _send_without_auth(self, req_kwargs, rsession):
        res = rsession.request(**req_kwargs)
        rsession.close()

        return res

    def login(self, *args, **kwargs):
        if self.is_authenticated:
            raise AlreadyLoggedIn

    def logout(self):
        """
        Reset the session to an unauthenticated, default state.
        """
        self._rsession.close()
        self.__init__()

    def send(self, req_kwargs, desired_auth, rsession=None):
        """Send a request from a Call using this session's auth.

        :param req_kwargs: kwargs for requests.Session.request
        :param desired_auth: protocol.shared.AuthTypes to attach
        :param rsession: (optional) a requests.Session to use
         (default ``self._rsession`` - this is exposed for test purposes)
        """
        if not any(desired_auth):
            if rsession is None:
                # use a throwaway session to ensure it's clean
                rsession = requests.Session()

            return self._send_without_auth(req_kwargs, rsession)

        else:
            if not self.is_authenticated:
                raise NotLoggedIn

            if rsession is None:
                rsession = self._rsession

            return self._send_with_auth(req_kwargs, desired_auth, rsession)


class Webclient(_Base):
    def __init__(self):
        super(Webclient, self).__init__()
        self._authtoken = None

    def login(self, email, password, *args, **kwargs):
        """
        Perform clientlogin then retrieve webclient cookies.

        :param email:
        :param password:
        """

        super(Webclient, self).login()

        res = ClientLogin.perform(self, email, password)

        if 'SID' not in res or 'Auth' not in res:
            return False

        self._authtoken = res['Auth']

        self.is_authenticated = True

        # Get webclient cookies.
        # They're stored automatically by requests on the webclient session.
        try:
            webclient.Init.perform(self)
        except CallFailure:
            # throw away clientlogin credentials
            self.logout()

        return self.is_authenticated

    def _send_with_auth(self, req_kwargs, desired_auth, rsession):
        if desired_auth.sso:
            req_kwargs['headers'] = req_kwargs.get('headers', {})

            # does this ever expire? would we have to perform clientlogin again?
            req_kwargs['headers']['Authorization'] = \
                'GoogleLogin auth=' + self._authtoken

        if desired_auth.xt:
            req_kwargs['params'] = req_kwargs.get('params', {})
            req_kwargs['params'].update({'u': 0, 'xt': rsession.cookies['xt']})

        return rsession.request(**req_kwargs)
