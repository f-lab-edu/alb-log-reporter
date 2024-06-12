import requests
def download_abuseipdb(
        url="https://raw.githubusercontent.com/borestad/blocklist-abuseipdb/main/abuseipdb-s100-30d.ipv4"):
    response = requests.get(url)
    response.raise_for_status()
    return set(response.text.splitlines())

def main():
    abuse_ip_set = download_abuseipdb()
    print(f"Downloaded {len(abuse_ip_set)} IP addresses from AbuseIPDB blocklist.")
    print(abuse_ip_set)

if __name__ == "__main__":
    main()