#!/usr/bin/env python3
import argparse

from dcc.api import serve

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Data Center Commander loopback read model"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    serve(args.host, args.port)
