from rq import Worker, Queue, Connection
from redis import Redis


def main() -> None:
    conn = Redis()
    with Connection(conn):
        w = Worker(["default"])
        w.work()


if __name__ == "__main__":
    main()


