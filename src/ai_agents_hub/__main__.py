from __future__ import annotations

import uvicorn

from ai_agents_hub.config import load_config


def main() -> None:
    config = load_config()
    uvicorn.run(
        "ai_agents_hub.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
