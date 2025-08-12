""" End-to-end tests """

import filecmp
import multiprocessing
import os
import socket
import subprocess
import tempfile
from typing import List

import pytest  # type:ignore

TEST_DATA_FILE_PATH: str = "tests/prometheus_stats.txt"
REFERENCE_GRAPHITE_DATA_PATH: str = "tests/graphite_stats.txt"
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


def validate_stats(*, graphite_data_path) -> bool:
    """
    Compare the generated Graphite states against the manually-created
    known-good reference
    """
    return filecmp.cmp(graphite_data_path, REFERENCE_GRAPHITE_DATA_PATH)


@pytest.fixture(scope="session")
def mock_graphite_server():
    """Blindly accepts some tcp traffic"""
    tcp_proc = multiprocessing.Process(target=tcp_listener)
    udp_proc = multiprocessing.Process(target=udp_listener)
    tcp_proc.start()
    udp_proc.start()
    yield True
    tcp_proc.terminate()
    udp_proc.terminate()


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
                "-vv",
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
                "-vv",
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
                "-vv",
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
    command: List[str] = ["python3", "-m", "promethiite", "-vv"] + [
        str(x) for x in test_input
    ]

    if "--file" not in test_input:
        with open(TEST_DATA_FILE_PATH, mode="r", encoding="utf-8") as stats_f:
            res = subprocess.run(
                command, capture_output=True, check=False, text=True, stdin=stats_f
            )
    else:
        res = subprocess.run(command, capture_output=True, check=False, text=True)
    assert res.returncode == expected["returncode"]
    validate_stats(graphite_data_path=RECVD_FILE.name)
    RECVD_FILE.truncate(0)
    RECVD_FILE.seek(0)


# pylint: enable=unused-argument
# pylint: enable=redefined-outer-name


def pytest_sessionfinish(session, exitstatus):  # pylint: disable=unused-argument
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    RECVD_FILE.close()
    os.remove(RECVD_FILE.name)
