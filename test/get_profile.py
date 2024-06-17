import configparser
import os

def print_aws_profiles():
    config = configparser.ConfigParser()

    config_path = os.path.expanduser("~/.aws/config")
    credentials_path = os.path.expanduser("~/.aws/credentials")

    print("Checking AWS Config Profiles...")
    if os.path.exists(config_path):
        config.read(config_path)
        for section in config.sections():
            print(f"[{section}]")
            for key, value in config.items(section):
                print(f"{key} = {value}")
            print()
    else:
        print(f"No config file found at {config_path}")

    print("Checking AWS Credentials Profiles...")
    if os.path.exists(credentials_path):
        config.read(credentials_path)
        for section in config.sections():
            print(f"[{section}]")
            for key, value in config.items(section):
                print(f"{key} = {value}")
            print()
    else:
        print(f"No credentials file found at {credentials_path}")

if __name__ == "__main__":
    print_aws_profiles()
