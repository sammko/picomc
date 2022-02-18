import colorama
import requests
from requests.exceptions import RequestException

from picomc.errors import AuthenticationError, RefreshError, ValidationError
from picomc.logging import logger

URL_DEVICE_AUTH = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
URL_TOKEN = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
URL_XBL = "https://user.auth.xboxlive.com/user/authenticate"
URL_XSTS = "https://xsts.auth.xboxlive.com/xsts/authorize"
URL_MCS = "https://api.minecraftservices.com/authentication/login_with_xbox"
URL_MCS_PROFILE = "https://api.minecraftservices.com/minecraft/profile"

CLIENT_ID = "c52aed44-3b4d-4215-99c5-824033d2bc0f"
SCOPE = "XboxLive.signin offline_access"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


class MicrosoftAuthApi:
    def _ms_oauth(self):
        data = {"client_id": CLIENT_ID, "scope": SCOPE}

        resp = requests.post(URL_DEVICE_AUTH, data)
        resp.raise_for_status()

        j = resp.json()
        device_code = j["device_code"]

        msg = j["message"]
        user_code = j["user_code"]
        link = j["verification_uri"]

        msg = msg.replace(
            user_code, colorama.Fore.RED + user_code + colorama.Fore.RESET
        ).replace(link, colorama.Style.BRIGHT + link + colorama.Style.NORMAL)

        logger.info(msg)

        data = {"code": device_code, "grant_type": GRANT_TYPE, "client_id": CLIENT_ID}

        first = True
        while True:
            if first:
                input("Press enter to continue... ")
            else:
                input("Press enter to try again... ")
            first = False

            resp = requests.post(URL_TOKEN, data)
            if resp.status_code == 400:
                j = resp.json()
                logger.debug(j)
                if j["error"] == "authorization_pending":
                    logger.warning(j["error_description"])
                    logger.info(msg)
                    continue
                else:
                    raise AuthenticationError(j["error_description"])
            resp.raise_for_status()

            j = resp.json()
            break

        access_token = j["access_token"]
        refresh_token = j["refresh_token"]
        logger.debug("OAuth device code flow successful")
        return access_token, refresh_token

    def _ms_oauth_refresh(self, refresh_token):
        data = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
        }
        resp = requests.post(URL_TOKEN, data)
        resp.raise_for_status()

        j = resp.json()
        access_token = j["access_token"]
        refresh_token = j["refresh_token"]
        logger.debug("OAuth code flow refresh successful")
        return access_token, refresh_token

    def _xbl_auth(self, access_token):
        data = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={access_token}",
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        }
        resp = requests.post(URL_XBL, json=data)
        resp.raise_for_status()

        j = resp.json()
        logger.debug("XBL auth successful")
        return j["Token"], j["DisplayClaims"]["xui"][0]["uhs"]

    def _xsts_auth(self, xbl_token):
        data = {
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT",
        }
        resp = requests.post(URL_XSTS, json=data)
        resp.raise_for_status()

        j = resp.json()
        logger.debug("XSTS auth successful")
        return j["Token"]

    def _mcs_auth(self, uhs, xsts_token):
        data = {"identityToken": f"XBL3.0 x={uhs};{xsts_token}"}
        resp = requests.post(URL_MCS, json=data)
        resp.raise_for_status()

        j = resp.json()
        logger.debug("Minecraft services auth successful")
        return j["access_token"]

    def get_profile(self, mc_access_token):
        try:
            resp = requests.get(
                URL_MCS_PROFILE, headers={"Authorization": f"Bearer {mc_access_token}"}
            )
            resp.raise_for_status()
        except RequestException as e:
            raise AuthenticationError(e)
        return resp.json()

    def _auth_rest(self, access_token, refresh_token):
        xbl_token, uhs = self._xbl_auth(access_token)
        xsts_token = self._xsts_auth(xbl_token)
        mc_access_token = self._mcs_auth(uhs, xsts_token)
        return mc_access_token

    def authenticate(self):
        try:
            access_token, refresh_token = self._ms_oauth()
            mc_access_token = self._auth_rest(access_token, refresh_token)
            return mc_access_token, refresh_token
        except RequestException as e:
            raise AuthenticationError(e)
        except KeyError as e:
            raise AuthenticationError("Missing field in response", e)

    def validate(self, mc_access_token):
        try:
            resp = requests.get(
                URL_MCS_PROFILE, headers={"Authorization": f"Bearer {mc_access_token}"}
            )
            if resp.status_code == 401:
                return False

            resp.raise_for_status()
            profile = resp.json()

            return "id" in profile
        except RequestException as e:
            raise ValidationError(e)

    def refresh(self, refresh_token):
        try:
            access_token, new_refresh_token = self._ms_oauth_refresh(refresh_token)
            mc_access_token = self._auth_rest(access_token, refresh_token)
            return mc_access_token, new_refresh_token
        except RequestException as e:
            raise RefreshError(e)
