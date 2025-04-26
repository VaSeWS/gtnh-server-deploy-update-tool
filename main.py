import argparse
import urllib.request
import re
import os
import shutil
import subprocess
import logging
from packaging import version
from pathlib import Path


VERSIONS_URL = "https://downloads.gtnewhorizons.com/ServerPacks/?raw"
VERSION_PATTERN = re.compile(
    r"^http://downloads\.gtnewhorizons\.com/ServerPacks/"
    r"GT_New_Horizons_"
    r"(\d+\.\d+\.\d+)"
    r"_Server_Java_17-21\.zip$"
)
WORKING_DIR = os.path.realpath(os.path.expanduser("~/gtnh_server"))
DOWNLOAD_DIR = os.path.join(WORKING_DIR, "downloaded_versions")
SERVER_FILES_DIR = os.path.join(WORKING_DIR, "gtnh-server-files")
DOCKER_COMPOSE_FILE = os.path.join(WORKING_DIR, "docker-compose.yaml")


log = logging.getLogger("gtnh_server_deploy_update_tool")
log.setLevel(logging.INFO)


def get_available_versions(min_ver: str="0.0.0") -> dict[version.Version, str]:
    min_ver = version.parse(min_ver)
    try:
        with urllib.request.urlopen(VERSIONS_URL) as response:
            content = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise ValueError(f"Connection error: {e.reason}")
    
    filtered_links = list(url for url in content.splitlines() if VERSION_PATTERN.fullmatch(url))

    versions = dict()
    for link in filtered_links:
        ver = version.parse(VERSION_PATTERN.search(link).group(1))
        if ver > min_ver:
            versions[ver] = link

    return versions


def download_version(url: str) -> str:
    filename = os.path.basename(url)
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    log.info(f"Downloading server pack from {url} into {filepath}")
    if os.path.exists(filepath):
        log.info("Version has already been downloaded. Skipping...")
    else:
        urllib.request.urlretrieve(url, filepath)
        log.info(f"{url} was downloaded successfully")

    return filepath


def generate_docker_compose(
    whitelist: list[str],
    ops: list[str],
    modpack_archive: str,
    game_port: str="25565",
    memory: str="8G",
) -> None:
    try:
        template = Path("docker-compose.template.yaml").read_text(encoding="utf-8")
        
        replacements = {
            "{GAME_PORT}": game_port,
            "{MEMORY}": memory,
            "{MODPACK_ARCHIVE}": modpack_archive,
            "{WHITELIST}": "\n        ".join(whitelist),
            "{OPS}": "\n        ".join(ops),
        }
        
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
            
        Path(DOCKER_COMPOSE_FILE).write_text(template, encoding="utf-8")
        
    except Exception as e:
        raise RuntimeError(f"Generation failed: {str(e)}") from e


def prepare_version(archive_path: str):
    os.makedirs(SERVER_FILES_DIR, exist_ok=True)
    archive_name = os.path.basename(archive_path)
    shutil.move(archive_path, os.path.join(SERVER_FILES_DIR, archive_name))


def action_install(args):
    available_vers = get_available_versions()
    if args.version == "latest":
        ver_url = available_vers[max(available_vers.keys())]
    else:
        ver_url = available_vers[version.parse(args.version)]
        # TODO: Add error handling

    archive_path = download_version(ver_url)
    # TODO: Add check & backup of existing version
    prepare_version(archive_path)
    generate_docker_compose(
        whitelist=args.whitelist,
        ops=args.ops,
        modpack_archive=os.path.basename(archive_path),
        game_port=args.server_port,
        memory=args.memory,
    )


def action_run(args):
    cmd = ["docker-compose", "run", "-d", "-f", DOCKER_COMPOSE_FILE]
    subprocess.run(
            cmd,
            check=True,
    )


def main():
    parser = argparse.ArgumentParser(description="GT:NH Server deploy tool")
    parser.add_argument("-r", "--run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    install_parser = subparsers.add_parser("install-version", help="Install specific or latest version")
    install_parser.add_argument("version", type=str, help="Version to install", default="latest")
    install_parser.add_argument("--server-port", dest="server_port", type=str, help="Game-server port", default="25565")
    install_parser.add_argument("--memory", type=str, help="Amount of memory to allocate to the server", default="8G")
    install_parser.add_argument("--whitelist", nargs='+', help="List of whitelisted players", required=True)
    install_parser.add_argument("--ops", nargs='+', help="List of op'ed players", required=True)
    install_parser.set_defaults(func=action_install)

    run_parser = subparsers.add_parser("run", help="Run server")
    run_parser.set_defaults(func=action_run)

    args = parser.parse_args()
    args.command(args)

    if args.command != "run" and args.run:
        action_run(args)

if __name__ == "__main__":
    main()
