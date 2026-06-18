from google_auth_oauthlib.flow import (
    InstalledAppFlow,
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]


def generate_token() -> None:
    flow = (
        InstalledAppFlow
        .from_client_secrets_file(
            "secrets/credentials.json",
            SCOPES,
        )
    )

    credentials = (
        flow.run_local_server(
            port=0,
        )
    )

    with open(
        "secrets/token.json",
        "w",
        encoding="utf-8",
    ) as token_file:
        token_file.write(
            credentials.to_json(),
        )


if __name__ == "__main__":
    generate_token()