promethiite
===========

Promethiite ingests [Prometheus] metrics, converts them to [Graphite] metrics, and sends them to a configured Graphite server over TCP

Requires Python 3.6+

# Installation

You can install with [pip]:

```sh
python3 -m pip install promethiite
```

Or install from source:

```sh
git clone <url>
pip install promethiite
```

# Usage

Promethiite is intended to be run at an interval, via e.g. cron or Systemd timers. There is no daemon mode.

```
usage: promethiite [-h] [--file FILE_PATH] --prefix PREFIX --server SERVER [--port PORT] [--proto {tcp,udp}] [--verbose]

        Ingests Prometheus metrics, converts them to Graphite metrics, and
        sends them to a configured Graphite server over TCP


options:
  -h, --help            show this help message and exit
  --file FILE_PATH, -f FILE_PATH
                        A file path from which to get the stats. By defaults expects STDIN
  --prefix PREFIX, -p PREFIX
                        Value to prepend to the value name on send to Graphite
  --server SERVER, -s SERVER
                        Graphite server
  --port PORT, -o PORT  Graphite server port
  --proto {tcp,udp}, -r {tcp,udp}
                        Protocol to use to reach the Graphite server
  --verbose, -v         Set output verbosity (-v=warning, -vv=debug)

examples:

        promethiite <args>
```

# Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

To run the test suite:

```bash
# Dependent targets create venv and install dependencies
make
```

Please make sure to update tests along with any changes.

# License

License :: OSI Approved :: MIT License


[Graphite]: https://graphite.readthedocs.io/en/latest/overview.html
[Prometheus]: https://prometheus.io/docs/introduction/overview/
[pip]: https://pip.pypa.io/en/stable/
