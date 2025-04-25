import urllib.request
import re
import os
from packaging import version
from pathlib import Path


VERSIONS_URL = "https://downloads.gtnewhorizons.com/ServerPacks/?raw"
VERSION_PATTERN = re.compile(
    r'^http://downloads\.gtnewhorizons\.com/ServerPacks/'
    r'GT_New_Horizons_'
    r'(\d+\.\d+\.\d+)'
    r'_Server_Java_17-21\.zip$'
)
WORKING_DIR = os.path.realpath(".")
DOWNLOAD_DIR = os.path.join(WORKING_DIR, "downloaded_versions")
SERVER_FILES_DIR = os.path.join(WORKING_DIR, "gtnh-server-files")
DOCKER_COMPOSE_FILE = os.path.join(WORKING_DIR, "docker-compose.yaml")


def get_available_versions(min_ver: str="0.0.0") -> tuple[version.Version, str]:
    min_ver = version.parse(min_ver)
    try:
        with urllib.request.urlopen(VERSIONS_URL) as response:
            content = response.read().decode('utf-8')
    except urllib.error.URLError as e:
        raise ValueError(f"Connection error: {e.reason}")
    
    filtered_links = list(url for url in content.splitlines() if VERSION_PATTERN.fullmatch(url))

    versions = []
    for link in filtered_links:
        ver = version.parse(VERSION_PATTERN.search(link).group(1))
        if ver > min_ver:
            versions.append((ver, link))

    return sorted(versions)


def download_version(ver, url):
    filename = os.path.basename(url)
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    print(f"Downloading server pack version {ver} from {url} into {filepath}")
    if os.path.exists(filepath):
        print("Version has already been downloaded. Skipping...")
    else:
        urllib.request.urlretrieve(url, filepath)
        print(f"Version {ver} was downloaded successfully")

    return filepath


def generate_docker_compose(
    whitelist: list,
    ops: list,
    modpack_archive: str,
    game_port: str="25565",
    memory: str="8G",
) -> None:
    try:
        template = Path("docker-compose.template.yaml").read_text(encoding='utf-8')
        
        replacements = {
            '{GAME_PORT}': game_port,
            '{MEMORY}': memory,
            '{MODPACK_ARCHIVE}': modpack_archive,
            '{WHITELIST}': '\n        '.join(whitelist),
            '{OPS}': '\n        '.join(ops),
        }
        
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
            
        Path(DOCKER_COMPOSE_FILE).write_text(template, encoding='utf-8')
        
    except Exception as e:
        raise RuntimeError(f"Generation failed: {str(e)}") from e


if __name__ == "__main__":
    ver_path = download_version(*get_available_versions("2.7.0")[-1])
    generate_docker_compose(["VaSeWS",], ["VaSeWS",], ver_path)
