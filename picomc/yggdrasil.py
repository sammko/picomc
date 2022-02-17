from urllib.error import HTTPError
from urllib.parse import urljoin

import requests
from requests.exceptions import RequestException

from picomc.errors import AuthenticationError, RefreshError


class MojangYggdrasil:
    BASE_URL = "https://authserver.mojang.com"

    def __init__(self, client_token):
        self.client_token = client_token

    def authenticate(self, username, password):
        ep = urljoin(self.BASE_URL, "/authenticate")

        try:
            resp = requests.post(
                ep,
                json={
                    "agent": {"name": "Minecraft", "version": 1},
                    "username": username,
                    "password": password,
                    "clientToken": self.client_token,
                    "requestUser": True,
                },
            )
            j = resp.json()
            if not resp.ok and "errorMessage" in j:
                raise AuthenticationError("Server response: " + j["errorMessage"])
            resp.raise_for_status()
        except RequestException as e:
            raise AuthenticationError(e)

        try:
            access_token = j["accessToken"]
            uuid = j["selectedProfile"]["id"]
            name = j["selectedProfile"]["name"]
            return (access_token, uuid, name)
        except KeyError as e:
            raise AuthenticationError("Missing field in response", e)

    def refresh(self, access_token):
        ep = urljoin(self.BASE_URL, "/refresh")
        try:
            resp = requests.post(
                ep,
                json={
                    "accessToken": access_token,
                    "clientToken": self.client_token,
                    "requestUser": True,
                },
            )
            j = resp.json()
            if not resp.ok and "errorMessage" in j:
                raise RefreshError(j["errorMessage"])
            resp.raise_for_status()
        except RequestException as e:
            raise RefreshError("Failed to refresh", e)

        try:
            access_token = j["accessToken"]
            uuid = j["selectedProfile"]["id"]
            name = j["selectedProfile"]["name"]
            return (access_token, uuid, name)
        except KeyError:
            raise RefreshError("Missing field in response", e)

    def validate(self, access_token):
        ep = urljoin(self.BASE_URL, "/validate")
        resp = requests.post(
            ep, json={"accessToken": access_token, "clientToken": self.client_token}
        )
        return resp.status_code == 204
