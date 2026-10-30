"""SQL Server logins: environment variables locally, AWS Secrets Manager on AWS."""
import json
import os


def login(db: dict, admin: bool = False) -> tuple[str, str]:
    """(user, password) for the read-only pipeline login, or for the admin login (setup jobs only)."""
    secret_key = "admin_secret" if admin else "reader_secret"
    if secret_key in db:                                   # prod: secret name from config
        import boto3                                       # available on AWS Glue
        secret = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=db[secret_key])["SecretString"])
        return secret["username"], secret["password"]
    user_env, password_env = ("user_env", "password_env") if admin else ("reader_user_env", "reader_password_env")
    return os.environ[db[user_env]], os.environ[db[password_env]]
