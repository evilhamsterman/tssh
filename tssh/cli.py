import argparse
import importlib.metadata
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TailscaleHost:
    ip: [str]
    hostname: str
    dnsname: str
    key: [str]


KNOWN_HOSTS_FILE = Path.home() / ".local" / "tailscale_known_hosts"


def parse_tailscale_status() -> [TailscaleHost]:
    """Parse the output of tailscale status --json into a list of TailscaleHost"""
    try:
        tailscale_output = json.loads(
            subprocess.run(
                ["tailscale", "status", "--json"], check=True, capture_output=True
            ).stdout
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr)
        raise e
    tailscale_hosts = []
    for tailscale_peer in tailscale_output["Peer"].values():
        if "sshHostKeys" in tailscale_peer:
            tailscale_hosts.append(
                TailscaleHost(
                    ip=tailscale_peer["TailscaleIPs"],
                    hostname=tailscale_peer["HostName"],
                    dnsname=tailscale_peer["DNSName"],
                    key=tailscale_peer["sshHostKeys"],
                )
            )
    return tailscale_hosts


def write_hostkeys(tailscale_hosts: TailscaleHost):
    """Print all hostkeys and names for a host from a list of TailScaleHost"""
    host_keys = ""
    # ensure the KNOWN_HOSTS_FILE directory exists
    KNOWN_HOSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # write the host keys to the file
    for host in tailscale_hosts:
        for key in host.key:
            host_keys += f"{host.hostname},{host.dnsname},{host.dnsname.rstrip('.')},{','.join(host.ip)} {key} \n"  # noqa: E501
    with KNOWN_HOSTS_FILE.open("w") as f:
        f.write(host_keys)


def check(args):
    """Check if a given hostname is in the output of parse_tailscale_status"""
    tailscale_hosts = parse_tailscale_status()
    write_hostkeys(tailscale_hosts)
    for host in tailscale_hosts:
        if args.host in [host.hostname, host.dnsname, host.dnsname.rstrip(".")]:
            sys.exit(0)
    sys.exit(1)


def ssh_config(_):
    """Generate a ssh config to use this tool for match and knownhostscommand"""
    ssh_config = f"""
    # Use tssh to check if a host is in tailscale
    Match exec "tssh check %h"
        UserKnownHostsFile {KNOWN_HOSTS_FILE}
    """
    ssh_config = textwrap.dedent(ssh_config)
    print(ssh_config)


# use argparse to create the subcommands check and hostkeys
def main():
    version = importlib.metadata.version("tssh")
    parser = argparse.ArgumentParser(
        description="TSSH: Tool for integrating Tailscale SSH with ssh"
    )
    parser.add_argument("-v", "--version", action="version", version=version)
    subparsers = parser.add_subparsers(help="sub-command help")

    # create the parser for the "check" command
    parser_check = subparsers.add_parser("check", help="check help")
    parser_check.add_argument("host", help="check if host is in tailscale status")
    parser_check.set_defaults(func=check)

    # add a parser to generate a ssh config
    parser_ssh_config = subparsers.add_parser(
        "ssh-config", help="Generate a ssh_config"
    )
    parser_ssh_config.set_defaults(func=ssh_config)

    # if no commands are given show the help
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    args.func(args)
