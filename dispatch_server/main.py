import uvicorn


def run() -> None:
    uvicorn.run("dispatch_server.app:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    run()
