from urllib.parse import urljoin

import requests


class AuthenticationError(Exception):
    pass


class RefreshError(AuthenticationError):
    pass


class MojangYggdrasil:
    BASE_URL = "https://authserver.mojang.com"

    def __init__(self, client_token):
        self.client_token = client_token

    def authenticate(self, username, password):
        ep = urljoin(self.BASE_URL, "/authenticate")
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
        if resp.status_code == 403:
            raise AuthenticationError("Failed to authenticate", j["errorMessage"])
        access_token = j["accessToken"]
        uuid = j["selectedProfile"]["id"]
        name = j["selectedProfile"]["name"]
        return (access_token, uuid, name)

    def refresh(self, access_token):
        ep = urljoin(self.BASE_URL, "/refresh")
        resp = requests.post(
            ep,
            json={
                "accessToken": access_token,
                "clientToken": self.client_token,
                "requestUser": True,
            },
        )
        j = resp.json()
        if resp.status_code == 403:
            raise RefreshError("Failed to refresh", j["errorMessage"])
        access_token = j["accessToken"]
        uuid = j["selectedProfile"]["id"]
        name = j["selectedProfile"]["name"]
        return (access_token, uuid, name)

    def validate(self, access_token):
        ep = urljoin(self.BASE_URL, "/validate")
        resp = requests.post(
            ep, json={"accessToken": access_token, "clientToken": self.client_token}
        )
        return resp.status_code == 204
