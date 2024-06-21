""" End-to-end tests """

import multiprocessing
import os
import re
import socket
import subprocess
import tempfile
from typing import List

import pytest  # type:ignore
from prometheus_client.parser import text_string_to_metric_families

TEST_DATA_FILE_PATH: str = "tests/prometheus_stats.txt"
HOST: str = "localhost"
PREFIX: str = "myprefix"
# pylint: disable=consider-using-with
RECVD_FILE = tempfile.NamedTemporaryFile(delete=False)
# pylint: enable=consider-using-with


def unused_port() -> int:
    """Get an unused port that we can ignore for testing failure"""
    sock: socket.socket = socket.socket()
    sock.bind(("", 0))
    return sock.getsockname()[1]


PORT: int = unused_port()


def compare_stats(*, prometheus_data_path, graphite_data_path) -> bool:
    """
    Test whether a pair of Prometheus and Graphite stats files are effectively
    equivalent

    accounting for the added prefix and the (irrelevant) timestamp

    Graphite plaintext stats can come in two formats:
        # https://graphite.readthedocs.io/en/latest/feeding-carbon.html
        # https://graphite.readthedocs.io/en/latest/tags.html
        <metric path> <metric value> <metric timestamp>
        <metric path>;tag1=value1,tag2=value2 <metric value> <metric timestamp>

    Prometheus:
        # https://github.com/prometheus/docs/blob/main/content/docs/instrumenting/exposition_formats.md
        <metric name>{tag1="value1",tag2="value2"} <metric value> <optional timestamp>

    """
    with open(prometheus_data_path, mode="r", encoding="utf-8") as pfile:
        # Translate the prometheus stats into a dict
        pdata: List[dict] = []
        for family in text_string_to_metric_families(pfile.read()):
            for sample in family.samples:
                pdata.append(
                    {
                        "name": sample.name,
                        "labels": sample.labels,
                        "value": sample.value,
                        "timestamp": 0,
                    }
                )
    with open(graphite_data_path, mode="r", encoding="utf-8") as gfile:
        glines = [line.rstrip() for line in gfile]
    for pstat, gline in zip(pdata, glines):
        # Zero out the timestampf rot his test
        gline = re.sub(r" \d+$", " 0", gline)
        strlabels: List = sorted([f"{k}={v}" for k, v in pstat["labels"].items()])
        tags = ";".join(strlabels)
        stat_tag_joiner: str = ""
        if tags:
            stat_tag_joiner = ";"
        assert (
            f"{PREFIX}.{pstat['name']}{stat_tag_joiner}{tags} {pstat['value']} "
            f"{pstat['timestamp']}"
        ) == gline
    return True


@pytest.fixture(scope="session")
def mock_graphite_server():
    """Blindly accepts some tcp traffic"""
    proc = multiprocessing.Process(target=tcp_listener)
    proc = multiprocessing.Process(target=udp_listener)
    proc.start()
    yield True
    proc.terminate()


def udp_listener():
    """listen forever, lazily blocking for each receive"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, PORT))
        while True:
            data, _ = sock.recvfrom(1024)
            RECVD_FILE.write(data)
            RECVD_FILE.flush()


def tcp_listener():
    """listen forever, lazily blocking for each receive"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, PORT))
        sock.listen()
        while True:
            conn, _ = sock.accept()
            with conn:
                while True:
                    data = conn.recv(1024)
                    RECVD_FILE.write(data)
                    RECVD_FILE.flush()
                    if not data:
                        break


@pytest.mark.parametrize(
    "test_input,expected",
    [
        (
            # Graphite stats from STDIN
            [
                "--server",
                HOST,
                "--port",
                PORT,
                "--prefix",
                PREFIX,
            ],
            {
                "returncode": 0,
            },
        ),
        (
            # Use UDP
            [
                "--server",
                HOST,
                "--port",
                PORT,
                "--prefix",
                PREFIX,
                "--proto",
                "udp",
            ],
            {
                "returncode": 0,
            },
        ),
        (
            # Graphite stats from file
            [
                "--server",
                HOST,
                "--port",
                PORT,
                "--prefix",
                PREFIX,
                "--file",
                TEST_DATA_FILE_PATH,
            ],
            {
                "returncode": 0,
            },
        ),
    ],
)
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
def test_end_to_end(mock_graphite_server, test_input, expected):
    """Test"""
    command: List[str] = ["python3", "-m", "promethiite"] + [str(x) for x in test_input]

    if "--file" not in test_input:
        with open(TEST_DATA_FILE_PATH, mode="r", encoding="utf-8") as stats_f:
            res = subprocess.run(
                command, capture_output=True, check=False, text=True, stdin=stats_f
            )
    else:
        res = subprocess.run(command, capture_output=True, check=False, text=True)
    assert res.returncode == expected["returncode"]
    compare_stats(
        prometheus_data_path=TEST_DATA_FILE_PATH, graphite_data_path=RECVD_FILE.name
    )


# pylint: enable=unused-argument
# pylint: enable=redefined-outer-name


def pytest_sessionfinish(session, exitstatus):  # pylint: disable=unused-argument
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    RECVD_FILE.close()
    os.remove(RECVD_FILE.name)
